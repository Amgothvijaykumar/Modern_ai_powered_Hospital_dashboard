from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Bill,
    InventoryItem,
    User,
    UserPermissionOverride,
    UserRole,
)
from app.repositories.user_repo import UserRepository
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import UndoOperationParams
from app.services.operations.common import (
    OperationDeniedError,
    OperationExecutionResult,
    OperationNotFoundError,
    OperationPreviewData,
    StalePreviewError,
    compute_snapshot_hash,
)
from app.services.permissions.engine import PermissionEngine
from app.utils.money import quantize_money

UNDOABLE_OPERATIONS = (
    "inventory.update",
    "inventory.delete",
    "bills.discount",
    "bills.update_status",
    "users.manage_access",
    "approvals.resolve",
)


def _is_undoable_audit(entry: AuditLog) -> bool:
    if entry.operation == "approvals.resolve":
        return bool(
            entry.before_data
            and entry.before_data.get("resolved_operation")
            and entry.before_data.get("records")
        )
    return entry.operation in UNDOABLE_OPERATIONS


def _effective_original_operation(entry: AuditLog) -> str:
    if entry.operation == "approvals.resolve" and entry.before_data:
        return str(entry.before_data.get("resolved_operation") or entry.operation)
    return str(entry.operation or "")


def _is_already_undone(db: Session, target: AuditLog) -> bool:
    undo_logs = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.hospital_id == target.hospital_id,
            AuditLog.operation == "operations.undo",
            AuditLog.execution_status == "SUCCESS",
            AuditLog.created_at >= target.created_at,
        )
        .order_by(desc(AuditLog.created_at))
    ).all()
    target_id_str = str(target.id)
    return any(
        (log.after_data or {}).get("undone_audit_id") == target_id_str
        for log in undo_logs
    )


def _find_target_audit(
    db: Session,
    user_context: CurrentUserContext,
    audit_log_id: Optional[uuid.UUID],
) -> AuditLog:
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.hospital_id == user_context.hospital_id,
            AuditLog.user_id == user_context.user_id,
            AuditLog.execution_status == "SUCCESS",
            AuditLog.operation.in_(UNDOABLE_OPERATIONS),
        )
        .order_by(desc(AuditLog.created_at))
    )
    if audit_log_id is not None:
        stmt = stmt.where(AuditLog.id == audit_log_id)

    candidates = db.scalars(stmt.limit(20)).all()
    target = next((c for c in candidates if _is_undoable_audit(c)), None)
    if target is None:
        raise OperationNotFoundError(
            "No recent completed write operation by your account was found to undo."
        )
    if _is_already_undone(db, target):
        raise OperationNotFoundError(
            f"Your most recent change ({_effective_original_operation(target)}) has already been undone."
        )
    return target


def _load_and_verify_undo_state(
    db: Session,
    user_context: CurrentUserContext,
    target: AuditLog,
    *,
    is_execute: bool = False,
) -> Tuple[str, List[Any], List[Dict[str, Any]], List[Any]]:
    """
    Validate current database rows against target.after_data to ensure no one has touched
    any affected row since the target operation ran.
    Returns: (effective_op, current_orm_objects, samples, snapshot_state)
    """
    effective_op = _effective_original_operation(target)
    before_data = target.before_data or {}
    after_data = target.after_data or {}

    def _conflict(msg: str) -> None:
        if is_execute:
            raise StalePreviewError(msg)
        raise OperationDeniedError(msg, source="undo_conflict")

    if effective_op == "inventory.update":
        before_records = before_data.get("records") or []
        after_records = after_data.get("records") or []
        if not before_records or len(before_records) != len(after_records):
            _conflict("Cannot undo: complete row snapshot is unavailable for this operation.")

        id_list = [uuid.UUID(r["id"]) for r in before_records]
        items = db.scalars(
            select(InventoryItem).where(
                InventoryItem.hospital_id == user_context.hospital_id,
                InventoryItem.id.in_(id_list),
            )
        ).all()
        by_id = {str(i.id): i for i in items}
        if len(by_id) != len(before_records):
            _conflict(
                "Cannot undo: one or more affected inventory items were deleted after your change."
            )

        modified_names: List[str] = []
        ordered_items: List[InventoryItem] = []
        snapshot_state: List[Any] = [str(target.id)]
        for after_rec in after_records:
            item = by_id[after_rec["id"]]
            ordered_items.append(item)
            snapshot_state.append([str(item.id), item.version])
            price_now = str(quantize_money(Decimal(item.unit_price)))
            if (
                item.version != after_rec["version"]
                or item.quantity != after_rec["quantity"]
                or item.minimum_quantity != after_rec["minimum_quantity"]
                or price_now != after_rec["unit_price"]
            ):
                modified_names.append(item.item_name)

        if modified_names:
            sample_str = ", ".join(modified_names[:3])
            _conflict(
                f"Cannot undo: {len(modified_names)} inventory item(s) ({sample_str}) "
                "have been modified by another operation since your change."
            )

        before_map = {r["id"]: r for r in before_records}
        samples = [
            {
                "id": str(item.id),
                "item_name": item.item_name,
                "batch_number": item.batch_number,
                "before": {
                    "quantity": item.quantity,
                    "minimum_quantity": item.minimum_quantity,
                    "unit_price": str(quantize_money(Decimal(item.unit_price))),
                },
                "after": {
                    "quantity": before_map[str(item.id)]["quantity"],
                    "minimum_quantity": before_map[str(item.id)]["minimum_quantity"],
                    "unit_price": before_map[str(item.id)]["unit_price"],
                },
            }
            for item in ordered_items[:5]
        ]
        return effective_op, ordered_items, samples, snapshot_state

    if effective_op == "inventory.delete":
        before_records = before_data.get("records") or []
        if not before_records:
            _conflict("Cannot undo deletion: full row snapshot is unavailable.")
        id_list = [uuid.UUID(r["id"]) for r in before_records]
        batch_list = [r["batch_number"] for r in before_records]
        existing = db.scalars(
            select(InventoryItem).where(
                InventoryItem.hospital_id == user_context.hospital_id,
                (InventoryItem.id.in_(id_list)) | (InventoryItem.batch_number.in_(batch_list)),
            )
        ).all()
        if existing:
            _conflict(
                "Cannot undo deletion: one or more deleted batch numbers already exist again in inventory."
            )
        samples = [
            {
                "id": r["id"],
                "item_name": r["item_name"],
                "batch_number": r["batch_number"],
                "before": {"deleted": True},
                "after": {"quantity": r["quantity"], "unit_price": r["unit_price"]},
            }
            for r in before_records[:5]
        ]
        snapshot_state = [str(target.id), len(before_records), "deleted_absent"]
        return effective_op, [], samples, snapshot_state

    if effective_op == "bills.discount":
        before_records = before_data.get("records") or []
        after_records = after_data.get("records") or []
        if not before_records or len(before_records) != len(after_records):
            _conflict("Cannot undo: complete billing snapshot is unavailable for this operation.")

        id_list = [uuid.UUID(r["id"]) for r in before_records]
        bills = db.scalars(
            select(Bill).where(
                Bill.hospital_id == user_context.hospital_id,
                Bill.id.in_(id_list),
            )
        ).all()
        by_id = {str(b.id): b for b in bills}
        if len(by_id) != len(before_records):
            _conflict("Cannot undo: one or more affected bills are no longer present.")

        modified_patients: List[str] = []
        ordered_bills: List[Bill] = []
        snapshot_state = [str(target.id)]
        for after_rec in after_records:
            bill = by_id[after_rec["id"]]
            ordered_bills.append(bill)
            snapshot_state.append([str(bill.id), bill.version])
            disc_now = str(quantize_money(Decimal(bill.discount_amount)))
            net_now = str(quantize_money(Decimal(bill.net_amount)))
            if (
                bill.version != after_rec["version"]
                or disc_now != after_rec["discount_amount"]
                or net_now != after_rec["net_amount"]
                or bill.status != after_rec["status"]
            ):
                modified_patients.append(bill.patient_name)

        if modified_patients:
            sample_str = ", ".join(modified_patients[:3])
            _conflict(
                f"Cannot undo: {len(modified_patients)} bill(s) ({sample_str}) "
                "have been modified since your discount was applied."
            )

        before_map = {r["id"]: r for r in before_records}
        samples = [
            {
                "id": str(b.id),
                "patient_name": b.patient_name,
                "before": {
                    "discount_amount": str(quantize_money(Decimal(b.discount_amount))),
                    "net_amount": str(quantize_money(Decimal(b.net_amount))),
                },
                "after": {
                    "discount_amount": before_map[str(b.id)]["discount_amount"],
                    "net_amount": before_map[str(b.id)]["net_amount"],
                },
            }
            for b in ordered_bills[:5]
        ]
        return effective_op, ordered_bills, samples, snapshot_state

    if effective_op == "bills.update_status":
        before_records = before_data.get("records") or []
        after_records = after_data.get("records") or []
        if not before_records or len(before_records) != len(after_records):
            _conflict("Cannot undo: complete bill status snapshot is unavailable.")

        id_list = [uuid.UUID(r["id"]) for r in before_records]
        bills = db.scalars(
            select(Bill).where(
                Bill.hospital_id == user_context.hospital_id,
                Bill.id.in_(id_list),
            )
        ).all()
        by_id = {str(b.id): b for b in bills}
        if len(by_id) != len(before_records):
            _conflict("Cannot undo: one or more affected bills are no longer present.")

        modified_count = 0
        ordered_bills = []
        snapshot_state = [str(target.id)]
        for after_rec in after_records:
            bill = by_id[after_rec["id"]]
            ordered_bills.append(bill)
            snapshot_state.append([str(bill.id), bill.version])
            if bill.version != after_rec["version"] or bill.status != after_rec["status"]:
                modified_count += 1

        if modified_count:
            _conflict(
                f"Cannot undo: {modified_count} bill(s) were modified after your status update."
            )

        before_map = {r["id"]: r for r in before_records}
        samples = [
            {
                "id": str(b.id),
                "patient_name": b.patient_name,
                "before": {"status": b.status},
                "after": {"status": before_map[str(b.id)]["status"]},
            }
            for b in ordered_bills[:5]
        ]
        return effective_op, ordered_bills, samples, snapshot_state

    if effective_op == "users.manage_access":
        target_uid_str = before_data.get("id")
        if not target_uid_str:
            _conflict("Cannot undo user access change: user snapshot missing.")
        repo = UserRepository(db, user_context.hospital_id, user_context.user_id)
        target_user = repo.resolve_target_user(target_user_id=uuid.UUID(target_uid_str))
        current_roles = sorted({ur.role.name for ur in target_user.user_roles if ur.role is not None})
        current_overrides = sorted(
            [
                {"permission_key": ov.permission.permission_key, "effect": ov.effect}
                for ov in target_user.permission_overrides
                if ov.permission is not None
            ],
            key=lambda o: (o["permission_key"], o["effect"]),
        )
        expected_after_roles = sorted(after_data.get("roles") or [])
        expected_after_overrides = sorted(
            after_data.get("overrides") or [],
            key=lambda o: (o["permission_key"], o["effect"]),
        )
        if current_roles != expected_after_roles or current_overrides != expected_after_overrides:
            _conflict(
                f"Cannot undo: access permissions for {target_user.full_name} "
                "were modified again after your change."
            )
        samples = [
            {
                "id": str(target_user.id),
                "full_name": target_user.full_name,
                "email": target_user.email,
                "before": {"roles": current_roles, "overrides": current_overrides},
                "after": {
                    "roles": before_data.get("roles", []),
                    "overrides": before_data.get("overrides", []),
                },
            }
        ]
        snapshot_state = [str(target.id), current_roles, current_overrides]
        return effective_op, [target_user], samples, snapshot_state

    _conflict(f"Operation '{effective_op}' is not supported for undo.")
    raise AssertionError("unreachable")


def preview_undo_operation(
    db: Session,
    user_context: CurrentUserContext,
    params: UndoOperationParams,
) -> OperationPreviewData:
    perm_engine = PermissionEngine(db)
    undo_dec = perm_engine.authorize(user_context, "operations.undo")
    if not undo_dec.allowed:
        raise OperationDeniedError(undo_dec.reason, undo_dec.source)

    target = _find_target_audit(db, user_context, params.audit_log_id)
    effective_op = _effective_original_operation(target)

    # Re-check user still holds permission on the underlying resource
    orig_dec = perm_engine.authorize(user_context, effective_op)
    if not orig_dec.allowed:
        raise OperationDeniedError(orig_dec.reason, orig_dec.source)

    _, orm_objs, samples, snapshot_state = _load_and_verify_undo_state(
        db, user_context, target, is_execute=False
    )
    records = (target.before_data or {}).get("records")
    affected_rows = len(records) if isinstance(records, list) else max(target.affected_rows or 1, 1)

    if effective_op == "inventory.update":
        row_dec = perm_engine.authorize(user_context, "inventory.update", requested_rows=affected_rows)
        if not row_dec.allowed:
            raise OperationDeniedError(row_dec.reason, row_dec.source)

    return OperationPreviewData(
        operation="operations.undo",
        summary=(
            f"Undo your last '{effective_op}' change ({affected_rows} row(s)) in "
            f"{user_context.hospital_name} and restore the before-snapshot. "
            "No changes have been applied yet."
        ),
        affected_rows=affected_rows,
        requires_exact_row_count=affected_rows > 50,
        samples=samples,
        business_rules_note=(
            "Undo verifies that no rows were modified by anyone else since the original change "
            "before restoring exact snapshot values."
        ),
        snapshot_hash=compute_snapshot_hash(snapshot_state),
        target_ids=[str(target.id)],
    )


def execute_undo_operation(
    db: Session,
    user_context: CurrentUserContext,
    params: UndoOperationParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    perm_engine = PermissionEngine(db)
    undo_dec = perm_engine.authorize(user_context, "operations.undo")
    if not undo_dec.allowed:
        raise OperationDeniedError(undo_dec.reason, undo_dec.source)

    target = _find_target_audit(db, user_context, params.audit_log_id)
    effective_op = _effective_original_operation(target)
    orig_dec = perm_engine.authorize(user_context, effective_op)
    if not orig_dec.allowed:
        raise OperationDeniedError(orig_dec.reason, orig_dec.source)

    effective_op, orm_objs, samples, snapshot_state = _load_and_verify_undo_state(
        db, user_context, target, is_execute=True
    )
    records = (target.before_data or {}).get("records")
    affected_rows = len(records) if isinstance(records, list) else max(target.affected_rows or 1, 1)

    if affected_rows != expected_row_count or compute_snapshot_hash(snapshot_state) != expected_snapshot_hash:
        raise StalePreviewError(
            "Target records changed after the undo preview was generated. Please try again."
        )

    now_utc = datetime.now(timezone.utc)
    before_data = target.before_data or {}

    if effective_op == "inventory.update":
        before_map = {r["id"]: r for r in before_data["records"]}
        for item in orm_objs:
            snap = before_map[str(item.id)]
            item.quantity = int(snap["quantity"])
            item.minimum_quantity = int(snap["minimum_quantity"])
            item.unit_price = Decimal(snap["unit_price"])
            item.updated_at = now_utc
            item.version += 1

    elif effective_op == "inventory.delete":
        for rec in before_data["records"]:
            db.add(
                InventoryItem(
                    id=uuid.UUID(rec["id"]),
                    hospital_id=user_context.hospital_id,
                    item_name=rec["item_name"],
                    category=rec["category"],
                    quantity=int(rec["quantity"]),
                    minimum_quantity=int(rec["minimum_quantity"]),
                    unit_price=Decimal(rec["unit_price"]),
                    expiry_date=date.fromisoformat(rec["expiry_date"]),
                    batch_number=rec["batch_number"],
                    created_at=now_utc,
                    updated_at=now_utc,
                    version=int(rec.get("version", 1)) + 1,
                )
            )

    elif effective_op == "bills.discount":
        before_map = {r["id"]: r for r in before_data["records"]}
        for bill in orm_objs:
            snap = before_map[str(bill.id)]
            bill.discount_amount = Decimal(snap["discount_amount"])
            bill.net_amount = Decimal(snap["net_amount"])
            bill.updated_at = now_utc
            bill.version += 1

    elif effective_op == "bills.update_status":
        before_map = {r["id"]: r for r in before_data["records"]}
        for bill in orm_objs:
            snap = before_map[str(bill.id)]
            bill.status = snap["status"]
            bill.updated_at = now_utc
            bill.version += 1

    elif effective_op == "users.manage_access":
        target_user: User = orm_objs[0]
        repo = UserRepository(db, user_context.hospital_id, user_context.user_id)
        desired_roles = set(before_data.get("roles") or [])
        desired_overrides = {
            ov["permission_key"]: ov["effect"]
            for ov in (before_data.get("overrides") or [])
        }
        # Reconcile overrides
        for existing_ov in list(target_user.permission_overrides):
            db.delete(existing_ov)
        db.flush()
        for pkey, effect in desired_overrides.items():
            perm = repo.get_permission_by_key(pkey)
            if perm is not None:
                db.add(
                    UserPermissionOverride(
                        id=uuid.uuid4(),
                        user_id=target_user.id,
                        permission_id=perm.id,
                        effect=effect,
                        created_at=now_utc,
                    )
                )
        # Reconcile roles
        for existing_ur in list(target_user.user_roles):
            db.delete(existing_ur)
        db.flush()
        for rname in sorted(desired_roles):
            role = repo.get_role_by_name(rname)
            if role is not None:
                db.add(UserRole(id=uuid.uuid4(), user_id=target_user.id, role_id=role.id))

    db.flush()
    return OperationExecutionResult(
        operation="operations.undo",
        message=(
            f"Successfully undone '{effective_op}' ({affected_rows} row(s) restored to "
            "before-snapshot state)."
        ),
        affected_rows=affected_rows,
        before_data={
            "target_audit_id": str(target.id),
            "undone_operation": effective_op,
            "samples": [s["before"] for s in samples],
        },
        after_data={
            "undone_audit_id": str(target.id),
            "undone_operation": effective_op,
            "restored_rows": affected_rows,
            "samples": [s["after"] for s in samples],
        },
    )

