from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import Bill
from app.repositories.billing_repo import BillingRepository
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import (
    BillsDiscountParams,
    BillsReadParams,
    BillsUpdateStatusParams,
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
from app.utils.dates import IST
from app.utils.money import calculate_bill_discount, quantize_money


def _serialize_bill(bill: Bill) -> Dict[str, Any]:
    created_ist = (
        bill.created_at.replace(tzinfo=timezone.utc).astimezone(IST)
        if bill.created_at.tzinfo is None
        else bill.created_at.astimezone(IST)
    )
    return {
        "id": str(bill.id),
        "patient_name": bill.patient_name,
        "gross_amount": str(quantize_money(Decimal(bill.gross_amount))),
        "discount_amount": str(quantize_money(Decimal(bill.discount_amount))),
        "net_amount": str(quantize_money(Decimal(bill.net_amount))),
        "status": bill.status,
        "created_by_user_id": str(bill.created_by_user_id),
        "created_at_ist": created_ist.isoformat(),
        "version": bill.version,
    }


def read_bills(
    db: Session,
    user_context: CurrentUserContext,
    params: BillsReadParams,
) -> Dict[str, Any]:
    decision = PermissionEngine(db).authorize(user_context, "bills.read")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    own_only = decision.constraints.get("scope") == "own_only"
    repo = BillingRepository(db, user_context.hospital_id, user_context.user_id)
    summary = repo.get_summary_metrics(own_only=own_only, owner_user_id=user_context.user_id)

    if params.filter == "summary":
        return {
            "operation": "bills.read",
            "filter": params.filter,
            "scope": "own_only" if own_only else "hospital",
            "summary": summary,
            "total_count": summary["total_bills"],
            "bills": [],
        }

    bills, total_count, date_range = repo.query_bills(
        params, own_only=own_only, owner_user_id=user_context.user_id
    )
    return {
        "operation": "bills.read",
        "filter": params.filter,
        "scope": "own_only" if own_only else "hospital",
        "summary": summary,
        "resolved_date_range": (
            {
                "period": date_range.period,
                "start_date": date_range.start_date_ist.isoformat(),
                "end_date": date_range.end_date_ist.isoformat(),
                "timezone": date_range.timezone,
            }
            if date_range
            else None
        ),
        "total_count": total_count,
        "returned_count": len(bills),
        "bills": [_serialize_bill(b) for b in bills],
    }


def preview_apply_discount(
    db: Session,
    user_context: CurrentUserContext,
    params: BillsDiscountParams,
) -> OperationPreviewData:
    # 1. Pre-query permission + discount-cap check
    decision = PermissionEngine(db).authorize(
        user_context, "bills.discount", discount_pct=params.discount_percentage
    )
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    # 2. Resolve hospital-scoped target bills + Asia/Kolkata date range
    repo = BillingRepository(db, user_context.hospital_id, user_context.user_id)
    targets, date_range = repo.find_targets_for_discount(params)
    if not targets:
        raise OperationNotFoundError("No matching eligible bills found in your hospital.")

    total_gross = Decimal("0.00")
    total_before_net = Decimal("0.00")
    total_after_net = Decimal("0.00")
    total_new_discount = Decimal("0.00")

    samples: List[Dict[str, Any]] = []
    snapshot_state: List[Any] = []

    for idx, bill in enumerate(targets):
        gross = quantize_money(Decimal(bill.gross_amount))
        old_discount = quantize_money(Decimal(bill.discount_amount))
        old_net = quantize_money(Decimal(bill.net_amount))
        new_discount, new_net = calculate_bill_discount(gross, params.discount_percentage)

        total_gross += gross
        total_before_net += old_net
        total_after_net += new_net
        total_new_discount += new_discount
        snapshot_state.append([str(bill.id), bill.version])

        if idx < 5:
            samples.append(
                {
                    "id": str(bill.id),
                    "patient_name": bill.patient_name,
                    "status": bill.status,
                    "before": {
                        "gross_amount": str(gross),
                        "discount_amount": str(old_discount),
                        "net_amount": str(old_net),
                    },
                    "after": {
                        "gross_amount": str(gross),
                        "discount_amount": str(new_discount),
                        "net_amount": str(new_net),
                    },
                }
            )

    net_reduction = quantize_money(total_before_net - total_after_net)
    resolved_range_dict = (
        {
            "period": date_range.period,
            "start_date": date_range.start_date_ist.isoformat(),
            "end_date": date_range.end_date_ist.isoformat(),
            "timezone": date_range.timezone,
        }
        if date_range
        else None
    )

    return OperationPreviewData(
        operation="bills.discount",
        summary=(
            f"Apply {params.discount_percentage}% discount to {len(targets)} eligible bill(s) "
            f"in {user_context.hospital_name}. No changes have been applied yet."
        ),
        affected_rows=len(targets),
        requires_exact_row_count=len(targets) > 50,
        samples=samples,
        financial_impact={
            "discount_percentage": str(params.discount_percentage),
            "total_gross_amount": str(quantize_money(total_gross)),
            "total_net_before": str(quantize_money(total_before_net)),
            "total_net_after": str(quantize_money(total_after_net)),
            "total_discount_amount": str(quantize_money(total_new_discount)),
            "net_revenue_change": str(-net_reduction),
            "currency": "INR",
        },
        resolved_date_range=resolved_range_dict,
        business_rules_note=(
            "Policy: New percentage discount replaces any previous discount on gross_amount, "
            "computed using Decimal arithmetic rounded HALF_UP to 2 decimal places."
        ),
        snapshot_hash=compute_snapshot_hash(snapshot_state),
        target_ids=[str(t.id) for t in targets],
    )


def execute_apply_discount(
    db: Session,
    user_context: CurrentUserContext,
    params: BillsDiscountParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    decision = PermissionEngine(db).authorize(
        user_context, "bills.discount", discount_pct=params.discount_percentage
    )
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = BillingRepository(db, user_context.hospital_id, user_context.user_id)
    targets, _ = repo.find_targets_for_discount(params)
    current_hash = compute_snapshot_hash([[str(t.id), t.version] for t in targets])
    if len(targets) != expected_row_count or current_hash != expected_snapshot_hash:
        raise StalePreviewError(
            "Billing records changed after the preview was generated. Please generate a fresh preview."
        )

    before_samples: List[Dict[str, Any]] = []
    after_samples: List[Dict[str, Any]] = []
    before_records: List[Dict[str, Any]] = []
    after_records: List[Dict[str, Any]] = []
    total_before_net = Decimal("0.00")
    total_after_net = Decimal("0.00")
    total_discount = Decimal("0.00")
    now_utc = datetime.now(timezone.utc)

    for idx, bill in enumerate(targets):
        before_records.append(
            {
                "id": str(bill.id),
                "gross_amount": str(quantize_money(Decimal(bill.gross_amount))),
                "discount_amount": str(quantize_money(Decimal(bill.discount_amount))),
                "net_amount": str(quantize_money(Decimal(bill.net_amount))),
                "status": bill.status,
                "version": bill.version,
            }
        )
        if idx < 5:
            before_samples.append(_serialize_bill(bill))
        gross = quantize_money(Decimal(bill.gross_amount))
        total_before_net += quantize_money(Decimal(bill.net_amount))
        new_discount, new_net = calculate_bill_discount(gross, params.discount_percentage)
        bill.discount_amount = new_discount
        bill.net_amount = new_net
        bill.updated_at = now_utc
        bill.version += 1
        total_after_net += new_net
        total_discount += new_discount
        after_records.append(
            {
                "id": str(bill.id),
                "gross_amount": str(quantize_money(Decimal(bill.gross_amount))),
                "discount_amount": str(quantize_money(Decimal(bill.discount_amount))),
                "net_amount": str(quantize_money(Decimal(bill.net_amount))),
                "status": bill.status,
                "version": bill.version,
            }
        )
        if idx < 5:
            after_samples.append(_serialize_bill(bill))

    db.flush()
    return OperationExecutionResult(
        operation="bills.discount",
        message=f"Applied {params.discount_percentage}% discount to {len(targets)} bill(s).",
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
        financial_impact={
            "total_net_before": str(quantize_money(total_before_net)),
            "total_net_after": str(quantize_money(total_after_net)),
            "total_discount_amount": str(quantize_money(total_discount)),
            "currency": "INR",
        },
    )


def preview_update_bill_status(
    db: Session,
    user_context: CurrentUserContext,
    params: BillsUpdateStatusParams,
) -> OperationPreviewData:
    decision = PermissionEngine(db).authorize(user_context, "bills.update_status")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = BillingRepository(db, user_context.hospital_id, user_context.user_id)
    targets, date_range = repo.find_targets_for_status_update(params)
    if not targets:
        raise OperationNotFoundError("No matching bills found in your hospital.")

    samples = [
        {
            "id": str(b.id),
            "patient_name": b.patient_name,
            "before": {"status": b.status, "net_amount": str(quantize_money(Decimal(b.net_amount)))},
            "after": {"status": params.new_status, "net_amount": str(quantize_money(Decimal(b.net_amount)))},
        }
        for b in targets[:5]
    ]
    snapshot_hash = compute_snapshot_hash([[str(t.id), t.version] for t in targets])
    return OperationPreviewData(
        operation="bills.update_status",
        summary=(
            f"Update status to {params.new_status} for {len(targets)} bill(s) "
            f"in {user_context.hospital_name}. No changes have been applied yet."
        ),
        affected_rows=len(targets),
        requires_exact_row_count=len(targets) > 50,
        samples=samples,
        resolved_date_range=(
            {
                "period": date_range.period,
                "start_date": date_range.start_date_ist.isoformat(),
                "end_date": date_range.end_date_ist.isoformat(),
                "timezone": date_range.timezone,
            }
            if date_range
            else None
        ),
        snapshot_hash=snapshot_hash,
        target_ids=[str(t.id) for t in targets],
    )


def execute_update_bill_status(
    db: Session,
    user_context: CurrentUserContext,
    params: BillsUpdateStatusParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    decision = PermissionEngine(db).authorize(user_context, "bills.update_status")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    repo = BillingRepository(db, user_context.hospital_id, user_context.user_id)
    targets, _ = repo.find_targets_for_status_update(params)
    current_hash = compute_snapshot_hash([[str(t.id), t.version] for t in targets])
    if len(targets) != expected_row_count or current_hash != expected_snapshot_hash:
        raise StalePreviewError(
            "Billing records changed after the preview was generated. Please generate a fresh preview."
        )

    before_samples: List[Dict[str, Any]] = []
    after_samples: List[Dict[str, Any]] = []
    before_records: List[Dict[str, Any]] = []
    after_records: List[Dict[str, Any]] = []
    now_utc = datetime.now(timezone.utc)
    for idx, bill in enumerate(targets):
        before_records.append(
            {"id": str(bill.id), "status": bill.status, "version": bill.version}
        )
        if idx < 5:
            before_samples.append(_serialize_bill(bill))
        bill.status = params.new_status
        bill.updated_at = now_utc
        bill.version += 1
        after_records.append(
            {"id": str(bill.id), "status": bill.status, "version": bill.version}
        )
        if idx < 5:
            after_samples.append(_serialize_bill(bill))

    db.flush()
    return OperationExecutionResult(
        operation="bills.update_status",
        message=f"Updated status to {params.new_status} for {len(targets)} bill(s).",
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

