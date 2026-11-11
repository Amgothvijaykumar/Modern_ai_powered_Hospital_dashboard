from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import InventoryItem
from app.repositories.inventory_repo import InventoryRepository
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import (
    InventoryDeleteParams,
    InventoryReadParams,
    InventoryUpdateParams,
)
from app.services.operations.common import (
    OperationDeniedError,
    OperationExecutionResult,
    OperationNotFoundError,
    OperationPreviewData,
    StalePreviewError,
    compute_snapshot_hash,
)
from app.services.permissions.engine import PermissionEngine
from app.utils.dates import resolve_expiry_window
from app.utils.money import quantize_money


def _serialize_inventory(item: InventoryItem) -> Dict[str, Any]:
    return {
        "id": str(item.id),
        "item_name": item.item_name,
        "category": item.category,
        "quantity": item.quantity,
        "minimum_quantity": item.minimum_quantity,
        "unit_price": str(quantize_money(Decimal(item.unit_price))),
        "expiry_date": item.expiry_date.isoformat(),
        "batch_number": item.batch_number,
        "is_low_stock": item.quantity < item.minimum_quantity,
        "version": item.version,
    }


def read_inventory(
    db: Session,
    user_context: CurrentUserContext,
    params: InventoryReadParams,
) -> Dict[str, Any]:
    decision = PermissionEngine(db).authorize(user_context, "inventory.read")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = InventoryRepository(db, user_context.hospital_id, user_context.user_id)
    summary = repo.get_summary_metrics(expiring_days=params.expiring_days)

    if params.filter == "summary":
        return {
            "operation": "inventory.read",
            "filter": params.filter,
            "summary": summary,
            "total_count": summary["total_items"],
            "items": [],
        }

    items, total_count = repo.query_items(params)
    window_start, window_end = resolve_expiry_window(params.expiring_days)
    return {
        "operation": "inventory.read",
        "filter": params.filter,
        "summary": summary,
        "expiry_window": (
            {"start_date": window_start.isoformat(), "end_date": window_end.isoformat(), "timezone": "Asia/Kolkata"}
            if params.filter == "expiring_soon"
            else None
        ),
        "total_count": total_count,
        "returned_count": len(items),
        "items": [_serialize_inventory(i) for i in items],
    }


def _compute_updated_values(item: InventoryItem, params: InventoryUpdateParams) -> Dict[str, Any]:
    new_qty = item.quantity
    if params.set_quantity is not None:
        new_qty = params.set_quantity
    elif params.adjust_quantity is not None:
        new_qty = item.quantity + params.adjust_quantity
        if new_qty < 0:
            raise ValueError(
                f"Cannot reduce quantity of '{item.item_name}' below 0 (current {item.quantity}, adjustment {params.adjust_quantity})"
            )

    new_min_qty = (
        params.set_minimum_quantity
        if params.set_minimum_quantity is not None
        else item.minimum_quantity
    )
    new_price = (
        quantize_money(params.set_unit_price)
        if params.set_unit_price is not None
        else quantize_money(Decimal(item.unit_price))
    )
    return {
        "quantity": new_qty,
        "minimum_quantity": new_min_qty,
        "unit_price": new_price,
    }


def preview_update_inventory(
    db: Session,
    user_context: CurrentUserContext,
    params: InventoryUpdateParams,
) -> OperationPreviewData:
    # 1. Pre-query authorization check (prevents unauthorized roles from touching inventory table)
    pre_decision = PermissionEngine(db).authorize(user_context, "inventory.update")
    if not pre_decision.allowed:
        raise OperationDeniedError(pre_decision.reason, pre_decision.source)

    # 2. Query hospital-scoped targets
    repo = InventoryRepository(db, user_context.hospital_id, user_context.user_id)
    targets = repo.find_targets_for_update(params)
    if not targets:
        raise OperationNotFoundError("No matching inventory items found in your hospital.")

    # 3. Enforce max_rows constraint (500 rows for all roles including Admin)
    row_decision = PermissionEngine(db).authorize(
        user_context, "inventory.update", requested_rows=len(targets)
    )
    if not row_decision.allowed:
        raise OperationDeniedError(row_decision.reason, row_decision.source)

    samples: List[Dict[str, Any]] = []
    snapshot_state: List[Any] = []
    for idx, item in enumerate(targets):
        updated = _compute_updated_values(item, params)
        snapshot_state.append([str(item.id), item.version])
        if idx < 5:
            samples.append(
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
                        "quantity": updated["quantity"],
                        "minimum_quantity": updated["minimum_quantity"],
                        "unit_price": str(updated["unit_price"]),
                    },
                }
            )

    return OperationPreviewData(
        operation="inventory.update",
        summary=f"Update {len(targets)} inventory item(s) in {user_context.hospital_name}. No changes have been applied yet.",
        affected_rows=len(targets),
        requires_exact_row_count=len(targets) > 50,
        samples=samples,
        business_rules_note="Maximum 500 rows per operation. Updates execute atomically inside a transaction.",
        snapshot_hash=compute_snapshot_hash(snapshot_state),
        target_ids=[str(t.id) for t in targets],
    )


def execute_update_inventory(
    db: Session,
    user_context: CurrentUserContext,
    params: InventoryUpdateParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    pre_decision = PermissionEngine(db).authorize(user_context, "inventory.update")
    if not pre_decision.allowed:
        raise OperationDeniedError(pre_decision.reason, pre_decision.source)

    repo = InventoryRepository(db, user_context.hospital_id, user_context.user_id)
    targets = repo.find_targets_for_update(params)

    row_decision = PermissionEngine(db).authorize(
        user_context, "inventory.update", requested_rows=len(targets)
    )
    if not row_decision.allowed:
        raise OperationDeniedError(row_decision.reason, row_decision.source)

    current_hash = compute_snapshot_hash([[str(t.id), t.version] for t in targets])
    if len(targets) != expected_row_count or current_hash != expected_snapshot_hash:
        raise StalePreviewError(
            "Inventory data changed after the preview was generated. Please generate a fresh preview."
        )

    before_samples: List[Dict[str, Any]] = []
    after_samples: List[Dict[str, Any]] = []
    before_records: List[Dict[str, Any]] = []
    after_records: List[Dict[str, Any]] = []
    now_utc = datetime.now(timezone.utc)

    for idx, item in enumerate(targets):
        updated = _compute_updated_values(item, params)
        before_records.append(
            {
                "id": str(item.id),
                "quantity": item.quantity,
                "minimum_quantity": item.minimum_quantity,
                "unit_price": str(quantize_money(Decimal(item.unit_price))),
                "version": item.version,
            }
        )
        if idx < 5:
            before_samples.append(_serialize_inventory(item))
        item.quantity = updated["quantity"]
        item.minimum_quantity = updated["minimum_quantity"]
        item.unit_price = updated["unit_price"]
        item.updated_at = now_utc
        item.version += 1
        after_records.append(
            {
                "id": str(item.id),
                "quantity": item.quantity,
                "minimum_quantity": item.minimum_quantity,
                "unit_price": str(quantize_money(Decimal(item.unit_price))),
                "version": item.version,
            }
        )
        if idx < 5:
            after_samples.append(_serialize_inventory(item))

    db.flush()
    return OperationExecutionResult(
        operation="inventory.update",
        message=f"Successfully updated {len(targets)} inventory item(s).",
        affected_rows=len(targets),
        before_data={
            "samples": before_samples,
            "total_affected": len(targets),
            "records": before_records,
        },
        after_data={
            "samples": after_samples,
            "total_affected": len(targets),
            "records": after_records,
        },
    )


def preview_delete_inventory(
    db: Session,
    user_context: CurrentUserContext,
    params: InventoryDeleteParams,
) -> OperationPreviewData:
    decision = PermissionEngine(db).authorize(user_context, "inventory.delete")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = InventoryRepository(db, user_context.hospital_id, user_context.user_id)
    targets = repo.find_targets_for_delete(params)
    if not targets:
        raise OperationNotFoundError("No matching inventory items found in your hospital.")

    samples = [
        {
            "id": str(item.id),
            "item_name": item.item_name,
            "batch_number": item.batch_number,
            "before": _serialize_inventory(item),
            "after": {"deleted": True},
        }
        for item in targets[:5]
    ]
    snapshot_hash = compute_snapshot_hash([[str(t.id), t.version] for t in targets])
    return OperationPreviewData(
        operation="inventory.delete",
        summary=f"Delete {len(targets)} inventory item(s) in {user_context.hospital_name}. No changes have been applied yet.",
        affected_rows=len(targets),
        requires_exact_row_count=len(targets) > 50,
        samples=samples,
        business_rules_note="Inventory deletion is permanent and restricted to Admins.",
        snapshot_hash=snapshot_hash,
        target_ids=[str(t.id) for t in targets],
    )


def execute_delete_inventory(
    db: Session,
    user_context: CurrentUserContext,
    params: InventoryDeleteParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    decision = PermissionEngine(db).authorize(user_context, "inventory.delete")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = InventoryRepository(db, user_context.hospital_id, user_context.user_id)
    targets = repo.find_targets_for_delete(params)
    current_hash = compute_snapshot_hash([[str(t.id), t.version] for t in targets])
    if len(targets) != expected_row_count or current_hash != expected_snapshot_hash:
        raise StalePreviewError(
            "Inventory data changed after the preview was generated. Please generate a fresh preview."
        )

    before_samples = [_serialize_inventory(t) for t in targets[:5]]
    before_records = [
        {
            **_serialize_inventory(t),
            "hospital_id": str(t.hospital_id),
        }
        for t in targets
    ]
    deleted_ids = [str(t.id) for t in targets]
    for item in targets:
        db.delete(item)
    db.flush()

    return OperationExecutionResult(
        operation="inventory.delete",
        message=f"Successfully deleted {len(targets)} inventory item(s).",
        affected_rows=len(targets),
        before_data={
            "samples": before_samples,
            "total_affected": len(targets),
            "records": before_records,
        },
        after_data={"deleted_count": len(targets), "deleted_ids": deleted_ids},
    )

