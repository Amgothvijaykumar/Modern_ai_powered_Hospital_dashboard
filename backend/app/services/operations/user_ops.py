from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserPermissionOverride, UserRole
from app.repositories.user_repo import AmbiguousUserError, UserRepository
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import UsersManageAccessParams, UsersReadParams
from app.services.operations.common import (
    OperationClarificationError,
    OperationDeniedError,
    OperationExecutionResult,
    OperationNotFoundError,
    OperationPreviewData,
    StalePreviewError,
    compute_snapshot_hash,
)
from app.services.permissions.engine import PermissionEngine


def _serialize_user_summary(
    user: User, perm_engine: PermissionEngine, include_permissions: bool = True
) -> Dict[str, Any]:
    roles = sorted({ur.role.name for ur in user.user_roles if ur.role is not None})
    overrides = sorted(
        [
            {
                "permission_key": ov.permission.permission_key,
                "effect": ov.effect,
            }
            for ov in user.permission_overrides
            if ov.permission is not None
        ],
        key=lambda o: (o["permission_key"], o["effect"]),
    )
    data: Dict[str, Any] = {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "is_active": user.is_active,
        "roles": roles,
        "overrides": overrides,
    }
    if include_permissions:
        eff = perm_engine.resolve_effective_permissions(user.id)
        data["effective_permissions"] = {
            k: {"allowed": v.allowed, "source": v.source, "constraints": v.constraints}
            for k, v in eff.items()
        }
    return data


def read_users(
    db: Session,
    user_context: CurrentUserContext,
    params: UsersReadParams,
) -> Dict[str, Any]:
    decision = PermissionEngine(db).authorize(user_context, "users.read")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = UserRepository(db, user_context.hospital_id, user_context.user_id)
    users = repo.list_hospital_users(search=params.search, role_name=params.role)
    perm_engine = PermissionEngine(db)
    serialized = [
        _serialize_user_summary(u, perm_engine, include_permissions=params.include_permissions)
        for u in users
    ]
    return {
        "operation": "users.read",
        "total_count": len(serialized),
        "users": serialized,
    }


def _resolve_and_authorize_access_change(
    db: Session,
    user_context: CurrentUserContext,
    params: UsersManageAccessParams,
) -> tuple[User, PermissionEngine]:
    perm_engine = PermissionEngine(db)
    # 1. Pre-query permission check
    pre_decision = perm_engine.authorize(user_context, "users.manage_access")
    if not pre_decision.allowed:
        raise OperationDeniedError(pre_decision.reason, pre_decision.source)

    # 2. Resolve target user strictly within same hospital
    repo = UserRepository(db, user_context.hospital_id, user_context.user_id)
    try:
        target_user = repo.resolve_target_user(
            target_user_id=params.target_user_id,
            target_user_email=params.target_user_email,
            target_user_name=params.target_user_name,
        )
    except AmbiguousUserError as exc:
        options = [f"{m.full_name} ({m.email})" for m in exc.matches]
        raise OperationClarificationError(
            f"Multiple users in {user_context.hospital_name} matched '{params.target_user_name}'. "
            f"Please specify which user: {', '.join(options)}",
            options=options,
        ) from exc

    if target_user is None:
        raise OperationNotFoundError("No matching user was found in your hospital.")

    # 3. Enforce access-management safeguards (self-demotion, subset grant)
    full_decision = perm_engine.authorize(
        user_context,
        "users.manage_access",
        target_user_id=target_user.id,
        access_action=params.action,
        target_role_name=params.role_name,
        target_permission_key=params.permission_key,
    )
    if not full_decision.allowed:
        raise OperationDeniedError(full_decision.reason, full_decision.source)

    return target_user, perm_engine


def _user_access_snapshot(target_user: User, perm_engine: PermissionEngine) -> Dict[str, Any]:
    eff = perm_engine.resolve_effective_permissions(target_user.id)
    return {
        "user_id": str(target_user.id),
        "full_name": target_user.full_name,
        "email": target_user.email,
        "roles": sorted({ur.role.name for ur in target_user.user_roles if ur.role is not None}),
        "overrides": sorted(
            [
                f"{ov.permission.permission_key}:{ov.effect}"
                for ov in target_user.permission_overrides
                if ov.permission is not None
            ]
        ),
        "allowed_permissions": sorted([k for k, v in eff.items() if v.allowed]),
    }


def _describe_proposed_access(before: Dict[str, Any], params: UsersManageAccessParams) -> Dict[str, Any]:
    proposed = {
        "roles": list(before["roles"]),
        "overrides": list(before["overrides"]),
        "action": params.action,
    }
    if params.action == "deny_permission" and params.permission_key:
        proposed["overrides"] = [
            o for o in proposed["overrides"] if not o.startswith(f"{params.permission_key}:")
        ] + [f"{params.permission_key}:DENY"]
        proposed["allowed_permissions"] = [
            p for p in before["allowed_permissions"] if p != params.permission_key
        ]
    elif params.action == "allow_permission" and params.permission_key:
        proposed["overrides"] = [
            o for o in proposed["overrides"] if not o.startswith(f"{params.permission_key}:")
        ] + [f"{params.permission_key}:ALLOW"]
        proposed["allowed_permissions"] = sorted(
            set(before["allowed_permissions"]) | {params.permission_key}
        )
    elif params.action == "remove_override" and params.permission_key:
        proposed["overrides"] = [
            o for o in proposed["overrides"] if not o.startswith(f"{params.permission_key}:")
        ]
    elif params.action == "grant_role" and params.role_name:
        proposed["roles"] = sorted(set(proposed["roles"]) | {params.role_name})
    elif params.action == "revoke_role" and params.role_name:
        proposed["roles"] = [r for r in proposed["roles"] if r != params.role_name]
    return proposed


def preview_manage_user_access(
    db: Session,
    user_context: CurrentUserContext,
    params: UsersManageAccessParams,
) -> OperationPreviewData:
    target_user, perm_engine = _resolve_and_authorize_access_change(db, user_context, params)
    before = _user_access_snapshot(target_user, perm_engine)
    after = _describe_proposed_access(before, params)

    target_label = params.permission_key or params.role_name
    summary = (
        f"Apply access change ({params.action}: {target_label}) to "
        f"{target_user.full_name} ({target_user.email}) in {user_context.hospital_name}. "
        "Shared role permissions for other users will NOT be modified. No changes have been applied yet."
    )

    return OperationPreviewData(
        operation="users.manage_access",
        summary=summary,
        affected_rows=1,
        requires_exact_row_count=False,
        samples=[
            {
                "id": str(target_user.id),
                "full_name": target_user.full_name,
                "email": target_user.email,
                "before": before,
                "after": after,
            }
        ],
        business_rules_note=(
            "Individual permission changes use user_permission_overrides so shared role_permissions "
            "remain unchanged for all other staff sharing the same role."
        ),
        snapshot_hash=compute_snapshot_hash([before]),
        target_ids=[str(target_user.id)],
    )


def execute_manage_user_access(
    db: Session,
    user_context: CurrentUserContext,
    params: UsersManageAccessParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    target_user, perm_engine = _resolve_and_authorize_access_change(db, user_context, params)
    before = _user_access_snapshot(target_user, perm_engine)
    current_hash = compute_snapshot_hash([before])
    if expected_row_count != 1 or current_hash != expected_snapshot_hash:
        raise StalePreviewError(
            "User access state changed after the preview was generated. Please generate a fresh preview."
        )

    repo = UserRepository(db, user_context.hospital_id, user_context.user_id)

    if params.action in ("deny_permission", "allow_permission", "remove_override"):
        perm = repo.get_permission_by_key(params.permission_key)
        if perm is None:
            raise OperationNotFoundError(f"Unknown permission '{params.permission_key}'.")

        existing_ov = db.scalar(
            select(UserPermissionOverride).where(
                UserPermissionOverride.user_id == target_user.id,
                UserPermissionOverride.permission_id == perm.id,
            )
        )
        if params.action == "remove_override":
            if existing_ov is not None:
                db.delete(existing_ov)
        else:
            effect = "DENY" if params.action == "deny_permission" else "ALLOW"
            if existing_ov is not None:
                existing_ov.effect = effect
            else:
                db.add(
                    UserPermissionOverride(
                        id=uuid.uuid4(),
                        user_id=target_user.id,
                        permission_id=perm.id,
                        effect=effect,
                        created_at=datetime.now(timezone.utc),
                    )
                )

    elif params.action in ("grant_role", "revoke_role"):
        role = repo.get_role_by_name(params.role_name)
        if role is None:
            raise OperationNotFoundError(f"Unknown role '{params.role_name}'.")
        existing_ur = db.scalar(
            select(UserRole).where(
                UserRole.user_id == target_user.id,
                UserRole.role_id == role.id,
            )
        )
        if params.action == "grant_role" and existing_ur is None:
            db.add(UserRole(id=uuid.uuid4(), user_id=target_user.id, role_id=role.id))
        elif params.action == "revoke_role" and existing_ur is not None:
            db.delete(existing_ur)

    db.flush()
    db.expire(target_user)
    # Re-read fresh user snapshot after flush
    refreshed_user = repo.resolve_target_user(target_user_id=target_user.id)
    after = _user_access_snapshot(refreshed_user, perm_engine)

    return OperationExecutionResult(
        operation="users.manage_access",
        message=f"Updated access for {target_user.full_name} ({params.action}).",
        affected_rows=1,
        before_data=before,
        after_data=after,
    )

