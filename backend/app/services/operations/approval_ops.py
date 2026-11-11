from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ApprovalRequest, User
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import (
    ApprovalsReadParams,
    ApprovalsResolveParams,
    BillsDiscountParams,
)
from app.services.operations.billing_ops import (
    execute_apply_discount,
    preview_apply_discount,
)
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
from app.utils.dates import IST


def serialize_approval_request(
    req: ApprovalRequest,
    requester_name: Optional[str] = None,
    requester_email: Optional[str] = None,
) -> Dict[str, Any]:
    created_ist = (
        req.created_at.replace(tzinfo=timezone.utc).astimezone(IST)
        if req.created_at.tzinfo is None
        else req.created_at.astimezone(IST)
    )
    resolved_ist = None
    if req.resolved_at is not None:
        resolved_ist = (
            req.resolved_at.replace(tzinfo=timezone.utc).astimezone(IST)
            if req.resolved_at.tzinfo is None
            else req.resolved_at.astimezone(IST)
        ).isoformat()

    return {
        "id": str(req.id),
        "short_id": str(req.id)[:8].upper(),
        "hospital_id": str(req.hospital_id),
        "requester_user_id": str(req.requester_user_id),
        "requester_name": requester_name,
        "requester_email": requester_email,
        "operation": req.operation,
        "parameters": req.parameters,
        "raw_user_query": req.raw_user_query,
        "reason": req.reason,
        "status": req.status,
        "reviewed_by_user_id": str(req.reviewed_by_user_id) if req.reviewed_by_user_id else None,
        "review_note": req.review_note,
        "created_at_ist": created_ist.isoformat(),
        "resolved_at_ist": resolved_ist,
    }


def create_pending_approval_request(
    db: Session,
    *,
    user_context: CurrentUserContext,
    operation: str,
    parameters: Dict[str, Any],
    raw_user_query: str,
    reason: str,
) -> ApprovalRequest:
    req = ApprovalRequest(
        id=uuid.uuid4(),
        hospital_id=user_context.hospital_id,
        requester_user_id=user_context.user_id,
        operation=operation,
        parameters=parameters,
        raw_user_query=raw_user_query,
        reason=reason,
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def read_approvals(
    db: Session,
    user_context: CurrentUserContext,
    params: ApprovalsReadParams,
) -> Dict[str, Any]:
    decision = PermissionEngine(db).authorize(user_context, "approvals.read")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    stmt = (
        select(ApprovalRequest, User)
        .join(User, User.id == ApprovalRequest.requester_user_id)
        .where(ApprovalRequest.hospital_id == user_context.hospital_id)
    )
    if decision.constraints.get("scope") == "own_only":
        stmt = stmt.where(ApprovalRequest.requester_user_id == user_context.user_id)
    if params.status != "ALL":
        stmt = stmt.where(ApprovalRequest.status == params.status)

    rows = db.execute(
        stmt.order_by(desc(ApprovalRequest.created_at)).limit(params.limit)
    ).all()

    items = [
        serialize_approval_request(
            req,
            requester_name=requester.full_name,
            requester_email=requester.email,
        )
        for req, requester in rows
    ]
    return {
        "operation": "approvals.read",
        "scope": decision.constraints.get("scope", "hospital"),
        "status_filter": params.status,
        "total_count": len(items),
        "approvals": items,
    }


def _resolve_target_approval_request(
    db: Session,
    user_context: CurrentUserContext,
    params: ApprovalsResolveParams,
) -> Tuple[ApprovalRequest, User]:
    rows = db.execute(
        select(ApprovalRequest, User)
        .join(User, User.id == ApprovalRequest.requester_user_id)
        .where(
            ApprovalRequest.hospital_id == user_context.hospital_id,
            ApprovalRequest.status == "PENDING",
        )
        .order_by(desc(ApprovalRequest.created_at))
    ).all()

    if not rows:
        raise OperationNotFoundError(
            f"No pending approval requests were found in {user_context.hospital_name}."
        )

    if params.request_id:
        needle = params.request_id.strip().lstrip("#").lower()
        matches = [
            pair
            for pair in rows
            if str(pair[0].id).lower() == needle or str(pair[0].id).lower().startswith(needle)
        ]
        if not matches:
            raise OperationNotFoundError(
                f"No pending approval request matching '{params.request_id}' was found in {user_context.hospital_name}."
            )
        if len(matches) > 1:
            options = [f"#{str(r.id)[:8].upper()} ({u.full_name})" for r, u in matches[:5]]
            raise OperationClarificationError(
                f"Multiple pending requests matched '{params.request_id}'. Please specify one: {', '.join(options)}",
                options=options,
            )
        return matches[0]

    if params.requester_name:
        rname = params.requester_name.strip().lower()
        matches = [
            pair
            for pair in rows
            if rname in pair[1].full_name.lower() or rname in pair[1].email.lower()
        ]
        if not matches:
            raise OperationNotFoundError(
                f"No pending approval request from '{params.requester_name}' was found in {user_context.hospital_name}."
            )
        if len(matches) > 1:
            options = [
                f"#{str(r.id)[:8].upper()} ({r.operation}: {r.raw_user_query[:40]})"
                for r, _ in matches[:5]
            ]
            raise OperationClarificationError(
                f"Multiple pending requests from '{params.requester_name}'. Please specify request ID: {', '.join(options)}",
                options=options,
            )
        return matches[0]

    if len(rows) > 1:
        options = [
            f"#{str(r.id)[:8].upper()} by {u.full_name} ({r.operation}: {r.parameters.get('discount_percentage', '')}%)"
            for r, u in rows[:5]
        ]
        raise OperationClarificationError(
            f"There are {len(rows)} pending approval requests. Which request ID should I {params.action}? "
            f"Options: {', '.join(options)}",
            options=options,
        )

    return rows[0]


def preview_resolve_approval(
    db: Session,
    user_context: CurrentUserContext,
    params: ApprovalsResolveParams,
) -> OperationPreviewData:
    decision = PermissionEngine(db).authorize(user_context, "approvals.resolve")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    req, requester = _resolve_target_approval_request(db, user_context, params)
    short_id = str(req.id)[:8].upper()

    if params.action == "reject":
        return OperationPreviewData(
            operation="approvals.resolve",
            summary=(
                f"Reject pending approval request #{short_id} from {requester.full_name} "
                f"({req.operation}). No changes have been applied yet."
            ),
            affected_rows=1,
            requires_exact_row_count=False,
            samples=[
                {
                    "id": str(req.id),
                    "patient_name": requester.full_name,
                    "before": {"status": req.status, "operation": req.operation},
                    "after": {"status": "REJECTED", "review_note": params.review_note},
                }
            ],
            business_rules_note="Only Hospital Admins may approve or reject escalated requests.",
            snapshot_hash=compute_snapshot_hash([str(req.id), req.status, "reject"]),
            target_ids=[str(req.id)],
        )

    if req.operation != "bills.discount":
        raise OperationDeniedError(
            f"Approval execution for operation '{req.operation}' is not supported.",
            source="unsupported_approval_operation",
        )

    discount_params = BillsDiscountParams.model_validate(req.parameters)
    inner_preview = preview_apply_discount(db, user_context, discount_params)
    return OperationPreviewData(
        operation="approvals.resolve",
        summary=(
            f"Approve request #{short_id} from {requester.full_name}: "
            f"{inner_preview.summary}"
        ),
        affected_rows=inner_preview.affected_rows,
        requires_exact_row_count=inner_preview.requires_exact_row_count,
        samples=inner_preview.samples,
        financial_impact=inner_preview.financial_impact,
        resolved_date_range=inner_preview.resolved_date_range,
        business_rules_note=(
            f"Approved Admin execution for request #{short_id} ({requester.full_name}). "
            f"{inner_preview.business_rules_note or ''}".strip()
        ),
        snapshot_hash=compute_snapshot_hash([str(req.id), req.status, inner_preview.snapshot_hash]),
        target_ids=[str(req.id)] + inner_preview.target_ids,
    )


def execute_resolve_approval(
    db: Session,
    user_context: CurrentUserContext,
    params: ApprovalsResolveParams,
    expected_snapshot_hash: str,
    expected_row_count: int,
) -> OperationExecutionResult:
    decision = PermissionEngine(db).authorize(user_context, "approvals.resolve")
    if not decision.allowed:
        raise OperationDeniedError(decision.reason, decision.source)

    req, requester = _resolve_target_approval_request(db, user_context, params)
    short_id = str(req.id)[:8].upper()
    now_utc = datetime.now(timezone.utc)

    if params.action == "reject":
        curr_hash = compute_snapshot_hash([str(req.id), req.status, "reject"])
        if expected_row_count != 1 or curr_hash != expected_snapshot_hash:
            raise StalePreviewError(
                "Approval request state changed after preview. Please generate a fresh preview."
            )
        req.status = "REJECTED"
        req.reviewed_by_user_id = user_context.user_id
        req.review_note = params.review_note or f"Rejected by {user_context.full_name}"
        req.resolved_at = now_utc
        db.flush()
        return OperationExecutionResult(
            operation="approvals.resolve",
            message=f"Rejected pending request #{short_id} from {requester.full_name}.",
            affected_rows=1,
            before_data={"approval_request_id": str(req.id), "status": "PENDING"},
            after_data={"approval_request_id": str(req.id), "status": "REJECTED"},
        )

    if req.operation != "bills.discount":
        raise OperationDeniedError(
            f"Approval execution for operation '{req.operation}' is not supported.",
            source="unsupported_approval_operation",
        )

    discount_params = BillsDiscountParams.model_validate(req.parameters)
    inner_preview = preview_apply_discount(db, user_context, discount_params)
    combined_hash = compute_snapshot_hash([str(req.id), req.status, inner_preview.snapshot_hash])
    if (
        inner_preview.affected_rows != expected_row_count
        or combined_hash != expected_snapshot_hash
    ):
        raise StalePreviewError(
            "Billing records or approval request state changed after preview. Please generate a fresh preview."
        )

    exec_result = execute_apply_discount(
        db,
        user_context,
        discount_params,
        inner_preview.snapshot_hash,
        inner_preview.affected_rows,
    )
    req.status = "EXECUTED"
    req.reviewed_by_user_id = user_context.user_id
    req.review_note = params.review_note or f"Approved and executed by {user_context.full_name}"
    req.resolved_at = now_utc
    db.flush()

    before_data = dict(exec_result.before_data)
    before_data["approval_request_id"] = str(req.id)
    before_data["resolved_operation"] = "bills.discount"
    after_data = dict(exec_result.after_data)
    after_data["approval_request_id"] = str(req.id)
    after_data["approval_status"] = "EXECUTED"

    return OperationExecutionResult(
        operation="approvals.resolve",
        message=f"Approved request #{short_id} ({requester.full_name}): {exec_result.message}",
        affected_rows=exec_result.affected_rows,
        before_data=before_data,
        after_data=after_data,
        financial_impact=exec_result.financial_impact,
    )

