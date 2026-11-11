from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Permission,
    Role,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from app.schemas.auth import CurrentUserContext, EffectivePermissionDetail

HARD_MAX_INVENTORY_UPDATE_ROWS = 500


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    permission_key: str
    source: str
    reason: str
    constraints: Dict[str, Any] = field(default_factory=dict)


class PermissionEngine:
    """Authoritative backend RBAC + user-override + constraint + safeguard engine."""

    def __init__(self, db: Session):
        self.db = db

    def resolve_effective_permissions(
        self, user_id: uuid.UUID
    ) -> Dict[str, EffectivePermissionDetail]:
        all_permissions = self.db.scalars(select(Permission)).all()

        # 1. Gather role-based grants
        user_roles = self.db.scalars(
            select(UserRole)
            .options(
                selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(UserRole.user_id == user_id)
        ).all()

        role_grants: Dict[str, Dict[str, Any]] = {}
        for ur in user_roles:
            if ur.role is None:
                continue
            for rp in ur.role.role_permissions:
                if rp.permission is None:
                    continue
                pkey = rp.permission.permission_key
                c = dict(rp.constraints or {})
                if pkey not in role_grants:
                    role_grants[pkey] = c
                else:
                    role_grants[pkey] = self._merge_constraints(pkey, role_grants[pkey], c)

        # 2. Gather user-specific overrides (DENY always wins over ALLOW and role grants)
        overrides = self.db.scalars(
            select(UserPermissionOverride)
            .options(selectinload(UserPermissionOverride.permission))
            .where(UserPermissionOverride.user_id == user_id)
        ).all()
        override_map: Dict[str, UserPermissionOverride] = {
            ov.permission.permission_key: ov
            for ov in overrides
            if ov.permission is not None
        }

        effective: Dict[str, EffectivePermissionDetail] = {}
        for perm in all_permissions:
            pkey = perm.permission_key
            ov = override_map.get(pkey)
            if ov is not None and ov.effect == "DENY":
                effective[pkey] = EffectivePermissionDetail(
                    permission_key=pkey,
                    allowed=False,
                    source="user_override_deny",
                    constraints={},
                )
            elif ov is not None and ov.effect == "ALLOW":
                base_constraints = role_grants.get(pkey, self._default_constraints(pkey))
                effective[pkey] = EffectivePermissionDetail(
                    permission_key=pkey,
                    allowed=True,
                    source="user_override_allow",
                    constraints=base_constraints,
                )
            elif pkey in role_grants:
                effective[pkey] = EffectivePermissionDetail(
                    permission_key=pkey,
                    allowed=True,
                    source="role_grant",
                    constraints=role_grants[pkey],
                )
            else:
                effective[pkey] = EffectivePermissionDetail(
                    permission_key=pkey,
                    allowed=False,
                    source="not_granted",
                    constraints={},
                )
        return effective

    def authorize(
        self,
        user_context: CurrentUserContext,
        permission_key: str,
        *,
        requested_rows: Optional[int] = None,
        discount_pct: Optional[Decimal] = None,
        target_user_id: Optional[uuid.UUID] = None,
        access_action: Optional[str] = None,
        target_role_name: Optional[str] = None,
        target_permission_key: Optional[str] = None,
    ) -> PermissionDecision:
        if not user_context.is_active:
            return PermissionDecision(
                allowed=False,
                permission_key=permission_key,
                source="inactive_user",
                reason="Your user account is inactive and cannot perform operations.",
            )

        effective = self.resolve_effective_permissions(user_context.user_id)

        # Stretch meta-operations derived strictly from existing RBAC matrix
        if permission_key == "operations.undo":
            write_keys = (
                "inventory.update",
                "inventory.delete",
                "bills.discount",
                "bills.update_status",
                "users.manage_access",
            )
            if any(effective.get(k) and effective[k].allowed for k in write_keys):
                return PermissionDecision(
                    allowed=True,
                    permission_key=permission_key,
                    source="role_grant",
                    reason="Authorized to undo caller's own write operation.",
                    constraints={},
                )
            return PermissionDecision(
                allowed=False,
                permission_key=permission_key,
                source="not_granted",
                reason=(
                    f"Permission denied: your role ({', '.join(user_context.roles) or 'None'}) "
                    "has no write permissions to undo changes."
                ),
            )

        if permission_key == "approvals.read":
            can_read_approvals = (
                "Admin" in user_context.roles
                or (effective.get("users.manage_access") and effective["users.manage_access"].allowed)
                or (effective.get("bills.discount") and effective["bills.discount"].allowed)
            )
            if can_read_approvals:
                return PermissionDecision(
                    allowed=True,
                    permission_key=permission_key,
                    source="role_grant",
                    reason="Authorized to view approval requests.",
                    constraints={"scope": "hospital" if "Admin" in user_context.roles else "own_only"},
                )
            return PermissionDecision(
                allowed=False,
                permission_key=permission_key,
                source="not_granted",
                reason=(
                    f"Permission denied: your role ({', '.join(user_context.roles) or 'None'}) "
                    "does not have access to approval requests."
                ),
            )

        if permission_key == "approvals.resolve":
            if "Admin" in user_context.roles:
                return PermissionDecision(
                    allowed=True,
                    permission_key=permission_key,
                    source="role_grant",
                    reason="Authorized as Hospital Admin to resolve escalated approval requests.",
                    constraints={},
                )
            return PermissionDecision(
                allowed=False,
                permission_key=permission_key,
                source="not_granted",
                reason=(
                    f"Permission denied: only a Hospital Admin can approve or reject escalated requests "
                    f"(your role: {', '.join(user_context.roles) or 'None'})."
                ),
            )

        detail = effective.get(permission_key)
        if detail is None or not detail.allowed:
            return PermissionDecision(
                allowed=False,
                permission_key=permission_key,
                source=detail.source if detail else "unknown_permission",
                reason=f"Permission denied: your role ({', '.join(user_context.roles) or 'None'}) "
                f"does not have '{permission_key}' access.",
            )

        constraints = dict(detail.constraints or {})

        # Inventory update row cap (hard limit 500 across all roles including Admin)
        if permission_key == "inventory.update" and requested_rows is not None:
            max_rows = min(
                int(constraints.get("max_rows", HARD_MAX_INVENTORY_UPDATE_ROWS)),
                HARD_MAX_INVENTORY_UPDATE_ROWS,
            )
            if requested_rows > max_rows:
                return PermissionDecision(
                    allowed=False,
                    permission_key=permission_key,
                    source="constraint_violation",
                    reason=(
                        f"Operation denied: this update affects {requested_rows} inventory rows, "
                        f"which exceeds the maximum limit of {max_rows} rows per operation. "
                        "Please narrow your filter (for example, by category or batch) and try again."
                    ),
                    constraints=constraints,
                )

        # Billing discount maximum percentage constraint
        if permission_key == "bills.discount" and discount_pct is not None:
            max_pct = Decimal(str(constraints.get("max_discount_pct", 0)))
            if discount_pct > max_pct:
                return PermissionDecision(
                    allowed=False,
                    permission_key=permission_key,
                    source="constraint_violation",
                    reason=(
                        f"Permission denied: requested {discount_pct}% discount exceeds your maximum "
                        f"permitted discount of {max_pct}%. You may submit a revised request up to {max_pct}%."
                    ),
                    constraints=constraints,
                )

        # Access management safeguards
        if permission_key == "users.manage_access":
            # Safeguard 1: Admin cannot remove their own Admin role or manage_access permission
            if target_user_id == user_context.user_id:
                if access_action == "revoke_role" and target_role_name == "Admin":
                    return PermissionDecision(
                        allowed=False,
                        permission_key=permission_key,
                        source="safeguard_violation",
                        reason="Safeguard violation: Administrators cannot remove their own Admin role.",
                        constraints=constraints,
                    )
                if access_action == "deny_permission" and target_permission_key == "users.manage_access":
                    return PermissionDecision(
                        allowed=False,
                        permission_key=permission_key,
                        source="safeguard_violation",
                        reason="Safeguard violation: Administrators cannot revoke their own access-management permission.",
                        constraints=constraints,
                    )

            # Safeguard 2: Actor cannot grant a permission they do not personally hold
            if access_action == "allow_permission" and target_permission_key:
                actor_perm = effective.get(target_permission_key)
                if actor_perm is None or not actor_perm.allowed:
                    return PermissionDecision(
                        allowed=False,
                        permission_key=permission_key,
                        source="safeguard_violation",
                        reason=(
                            f"Safeguard violation: you cannot grant '{target_permission_key}' "
                            "because you do not possess that permission yourself."
                        ),
                        constraints=constraints,
                    )

            # Safeguard 3: Actor cannot grant a role containing permissions they do not possess
            if access_action == "grant_role" and target_role_name:
                target_role = self.db.scalar(
                    select(Role)
                    .options(
                        selectinload(Role.role_permissions).selectinload(RolePermission.permission)
                    )
                    .where(Role.name == target_role_name)
                )
                if target_role is None:
                    return PermissionDecision(
                        allowed=False,
                        permission_key=permission_key,
                        source="invalid_role",
                        reason=f"Role '{target_role_name}' does not exist.",
                        constraints=constraints,
                    )
                for rp in target_role.role_permissions:
                    if rp.permission is None:
                        continue
                    actor_perm = effective.get(rp.permission.permission_key)
                    if actor_perm is None or not actor_perm.allowed:
                        return PermissionDecision(
                            allowed=False,
                            permission_key=permission_key,
                            source="safeguard_violation",
                            reason=(
                                f"Safeguard violation: you cannot grant role '{target_role_name}' "
                                f"because it includes '{rp.permission.permission_key}', which you do not possess."
                            ),
                            constraints=constraints,
                        )

        return PermissionDecision(
            allowed=True,
            permission_key=permission_key,
            source=detail.source,
            reason="Authorized",
            constraints=constraints,
        )

    @staticmethod
    def _default_constraints(permission_key: str) -> Dict[str, Any]:
        if permission_key == "inventory.update":
            return {"max_rows": HARD_MAX_INVENTORY_UPDATE_ROWS}
        if permission_key == "bills.discount":
            return {"max_discount_pct": 10}
        if permission_key == "bills.read":
            return {"scope": "own_only"}
        return {}

    @staticmethod
    def _merge_constraints(
        permission_key: str, first: Dict[str, Any], second: Dict[str, Any]
    ) -> Dict[str, Any]:
        merged = dict(first)
        if permission_key == "inventory.update":
            merged["max_rows"] = min(
                max(int(first.get("max_rows", 500)), int(second.get("max_rows", 500))),
                HARD_MAX_INVENTORY_UPDATE_ROWS,
            )
        elif permission_key == "bills.discount":
            merged["max_discount_pct"] = max(
                int(first.get("max_discount_pct", 0)),
                int(second.get("max_discount_pct", 0)),
            )
        elif permission_key == "bills.read":
            scopes = {first.get("scope"), second.get("scope")}
            merged["scope"] = "hospital" if "hospital" in scopes else "own_only"
        else:
            merged.update(second)
        return merged

