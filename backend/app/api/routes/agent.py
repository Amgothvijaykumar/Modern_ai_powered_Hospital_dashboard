import re
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.agent import AgentChatRequest, AgentChatResponse, PreviewPayload
from app.schemas.auth import CurrentUserContext
from app.services.audit.audit_service import AuditService
from app.services.intent.validator import IntentValidator
from app.services.llm.intent_extractor import IntentExtractorService
from app.services.operations.approval_ops import (
    create_pending_approval_request,
    serialize_approval_request,
)
from app.services.operations.common import (
    OperationClarificationError,
    OperationDeniedError,
    OperationNotFoundError,
)
from app.services.preview.confirmation_service import ConfirmationService

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


def _detect_cross_tenant_hospital_mention(
    current_user: CurrentUserContext, raw_query: str
) -> Optional[str]:
    """Detect explicit cross-tenant hospital targets without querying another tenant's data."""
    ql = raw_query.lower()
    own_name = (current_user.hospital_name or "").lower()
    if "metro general" in own_name:
        if re.search(r"\b(?:hospital\s*b|city\s*care(?:\s+medical\s+center)?)\b", ql):
            return "Cross-tenant access denied: you may only access records in your assigned hospital."
    elif "city care" in own_name:
        if re.search(r"\b(?:hospital\s*a|metro\s*general(?:\s+hospital)?)\b", ql):
            return "Cross-tenant access denied: you may only access records in your assigned hospital."
    return None


def _build_read_summary(operation_key: str, data: dict) -> str:
    if operation_key == "inventory.read":
        flt = data.get("filter", "all")
        total = data.get("total_count", 0)
        if flt == "expiring_soon" and data.get("expiry_window"):
            win = data["expiry_window"]
            return (
                f"Found {total} inventory item(s) expiring between {win['start_date']} "
                f"and {win['end_date']} ({win['timezone']})."
            )
        if flt == "low_stock":
            items = data.get("items") or []
            cat_counts = Counter(item.get("category", "Uncategorized") for item in items)
            if cat_counts:
                breakdown = ", ".join(f"{cat}: {cnt}" for cat, cnt in sorted(cat_counts.items()))
                return (
                    f"Found {total} low-stock inventory item(s) below minimum quantity "
                    f"(showing {len(items)} — {breakdown})."
                )
            return f"Found {total} low-stock inventory item(s) below minimum quantity."
        if flt == "summary":
            s = data.get("summary", {})
            return (
                f"Inventory overview: {s.get('total_items', 0)} total items, "
                f"{s.get('low_stock_count', 0)} low-stock, "
                f"{s.get('expiring_count', 0)} expiring in 30 days."
            )
        return f"Found {total} matching inventory item(s)."
    if operation_key == "bills.read":
        scope_note = " (scoped to your own bills)" if data.get("scope") == "own_only" else ""
        total = data.get("total_count", 0)
        return f"Found {total} matching bill(s){scope_note}."
    if operation_key == "users.read":
        return f"Found {data.get('total_count', 0)} user(s) in your hospital."
    if operation_key == "approvals.read":
        total = data.get("total_count", 0)
        scope_note = " (your requests)" if data.get("scope") == "own_only" else ""
        if total == 0:
            return f"No {data.get('status_filter', 'PENDING').lower()} approval requests found{scope_note}."
        items = data.get("approvals") or []
        previews = "; ".join(
            f"#{a['short_id']} ({a.get('requester_name') or 'Staff'}: {a['operation']})"
            for a in items[:5]
        )
        return f"Found {total} approval request(s){scope_note}: {previews}."
    return "Operation completed."


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(
    payload: AgentChatRequest,
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> AgentChatResponse:
    extractor = IntentExtractorService()
    extraction = extractor.extract(payload.message)
    outcome = IntentValidator.validate(extraction, current_user, payload.message)
    parsed_intent_dict = extraction.model_dump()

    cross_tenant_reason = _detect_cross_tenant_hospital_mention(current_user, payload.message)
    if cross_tenant_reason is not None and outcome.status not in ("unsupported",):
        audit = AuditService.record(
            db,
            hospital_id=current_user.hospital_id,
            user_id=current_user.user_id,
            raw_user_query=payload.message,
            parsed_intent=parsed_intent_dict,
            operation=extraction.intent,
            authorization_result="DENIED",
            decision_reason=cross_tenant_reason,
            affected_rows=0,
            execution_status="DENIED",
        )
        return AgentChatResponse(
            status="denied",
            message=cross_tenant_reason,
            intent=extraction.intent,
            operation=extraction.intent,
            extractor_source=extraction.extractor_source,
            audit_id=audit.id,
        )

    if outcome.status == "unsupported":
        audit = AuditService.record(
            db,
            hospital_id=current_user.hospital_id,
            user_id=current_user.user_id,
            raw_user_query=payload.message,
            parsed_intent=parsed_intent_dict,
            operation=extraction.intent,
            authorization_result="UNSUPPORTED",
            decision_reason=outcome.message or "Unsupported operation",
            affected_rows=0,
            execution_status="NOT_EXECUTED",
        )
        return AgentChatResponse(
            status="unsupported",
            message=outcome.message or "Unsupported operation.",
            intent=extraction.intent,
            extractor_source=extraction.extractor_source,
            audit_id=audit.id,
        )

    if outcome.status == "clarification_required":
        audit = AuditService.record(
            db,
            hospital_id=current_user.hospital_id,
            user_id=current_user.user_id,
            raw_user_query=payload.message,
            parsed_intent=parsed_intent_dict,
            operation=extraction.intent,
            authorization_result="CLARIFICATION_REQUIRED",
            decision_reason=outcome.message or "Clarification required",
            affected_rows=0,
            execution_status="CLARIFICATION_REQUIRED",
        )
        return AgentChatResponse(
            status="clarification_required",
            message=outcome.message or "Please clarify your request.",
            intent=extraction.intent,
            operation=extraction.intent,
            extractor_source=extraction.extractor_source,
            clarification_question=outcome.message,
            audit_id=audit.id,
        )

    if outcome.status == "invalid" or outcome.spec is None or outcome.validated_params is None:
        audit = AuditService.record(
            db,
            hospital_id=current_user.hospital_id,
            user_id=current_user.user_id,
            raw_user_query=payload.message,
            parsed_intent=parsed_intent_dict,
            operation=extraction.intent,
            authorization_result="INVALID",
            decision_reason=outcome.message or "Invalid parameters",
            affected_rows=0,
            execution_status="NOT_EXECUTED",
        )
        return AgentChatResponse(
            status="invalid",
            message=outcome.message or "Invalid parameters.",
            intent=extraction.intent,
            extractor_source=extraction.extractor_source,
            audit_id=audit.id,
        )

    spec = outcome.spec

    # Read operation path (no confirmation required)
    if not spec.is_write and spec.read_handler is not None:
        try:
            data = spec.read_handler(db, current_user, outcome.validated_params)
            returned_rows = data.get("total_count", 0)
            audit = AuditService.record(
                db,
                hospital_id=current_user.hospital_id,
                user_id=current_user.user_id,
                raw_user_query=payload.message,
                parsed_intent=parsed_intent_dict,
                operation=spec.operation_key,
                authorization_result="ALLOWED",
                decision_reason="Authorized read operation",
                affected_rows=returned_rows,
                execution_status="SUCCESS",
            )
            return AgentChatResponse(
                status="completed",
                message=_build_read_summary(spec.operation_key, data),
                intent=extraction.intent,
                operation=spec.operation_key,
                extractor_source=extraction.extractor_source,
                data=data,
                audit_id=audit.id,
            )
        except OperationDeniedError as exc:
            audit = AuditService.record(
                db,
                hospital_id=current_user.hospital_id,
                user_id=current_user.user_id,
                raw_user_query=payload.message,
                parsed_intent=parsed_intent_dict,
                operation=spec.operation_key,
                authorization_result="DENIED",
                decision_reason=exc.reason,
                affected_rows=0,
                execution_status="DENIED",
            )
            return AgentChatResponse(
                status="denied",
                message=exc.reason,
                intent=extraction.intent,
                operation=spec.operation_key,
                extractor_source=extraction.extractor_source,
                audit_id=audit.id,
            )

    # Write operation path -> always generates dry-run preview & confirmation token
    try:
        preview_data, record, raw_token = ConfirmationService.create_preview(
            db,
            current_user,
            spec.operation_key,
            outcome.validated_params.model_dump(mode="json"),
            payload.message,
        )
        return AgentChatResponse(
            status="preview_required",
            message=preview_data.summary,
            intent=extraction.intent,
            operation=spec.operation_key,
            extractor_source=extraction.extractor_source,
            preview=PreviewPayload(
                confirmation_token=raw_token,
                operation=preview_data.operation,
                summary=preview_data.summary,
                affected_rows=preview_data.affected_rows,
                requires_exact_row_count=preview_data.requires_exact_row_count,
                samples=preview_data.samples,
                financial_impact=preview_data.financial_impact,
                resolved_date_range=preview_data.resolved_date_range,
                business_rules_note=preview_data.business_rules_note,
                expires_at=record.expires_at,
            ),
        )
    except OperationDeniedError as exc:
        # Stretch Goal: route over-limit bills.discount requests to Admin approval queue
        # while keeping status="denied" and ceiling reason intact for immediate policy clarity.
        if (
            spec.operation_key == "bills.discount"
            and exc.source == "constraint_violation"
        ):
            approval_req = create_pending_approval_request(
                db,
                user_context=current_user,
                operation=spec.operation_key,
                parameters=outcome.validated_params.model_dump(mode="json"),
                raw_user_query=payload.message,
                reason=exc.reason,
            )
            serialized_req = serialize_approval_request(
                approval_req,
                requester_name=current_user.full_name,
                requester_email=current_user.email,
            )
            return AgentChatResponse(
                status="denied",
                message=(
                    f"{exc.reason} Pending Admin approval request "
                    f"#{serialized_req['short_id']} has been created so a Hospital Admin can review and approve it in chat."
                ),
                intent=extraction.intent,
                operation=spec.operation_key,
                extractor_source=extraction.extractor_source,
                data={"approval_request": serialized_req},
            )

        return AgentChatResponse(
            status="denied",
            message=exc.reason,
            intent=extraction.intent,
            operation=spec.operation_key,
            extractor_source=extraction.extractor_source,
        )
    except OperationClarificationError as exc:
        return AgentChatResponse(
            status="clarification_required",
            message=exc.question,
            intent=extraction.intent,
            operation=spec.operation_key,
            extractor_source=extraction.extractor_source,
            clarification_question=exc.question,
            clarification_options=exc.options,
        )
    except OperationNotFoundError as exc:
        return AgentChatResponse(
            status="not_found",
            message=exc.message,
            intent=extraction.intent,
            operation=spec.operation_key,
            extractor_source=extraction.extractor_source,
        )
