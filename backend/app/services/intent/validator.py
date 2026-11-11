import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel, ValidationError

from app.registry.operation_registry import OPERATION_REGISTRY, OperationSpec
from app.schemas.auth import CurrentUserContext
from app.schemas.intent import IntentExtractionResult

SQL_INJECTION_RE = re.compile(
    r"\b(select\s+.*\s+from|drop\s+table|delete\s+from|insert\s+into|union\s+select|alter\s+table|;\s*--)\b",
    re.IGNORECASE,
)


@dataclass
class ValidatedIntentOutcome:
    status: str  # "valid" | "clarification_required" | "unsupported" | "invalid"
    raw_intent: IntentExtractionResult
    spec: Optional[OperationSpec] = None
    validated_params: Optional[BaseModel] = None
    message: Optional[str] = None


def _contains_sql_like_payload(value: Any) -> bool:
    if isinstance(value, str):
        return bool(SQL_INJECTION_RE.search(value))
    if isinstance(value, dict):
        return any(_contains_sql_like_payload(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_sql_like_payload(v) for v in value)
    return False


class IntentValidator:
    """Validates LLM-extracted intent against the fixed OPERATION_REGISTRY and strict Pydantic schemas."""

    @staticmethod
    def validate(
        extraction: IntentExtractionResult,
        current_user: CurrentUserContext,
        raw_user_query: str,
    ) -> ValidatedIntentOutcome:
        # Reject raw SQL attempts if passed in parameters or raw query when intent is unsupported
        if _contains_sql_like_payload(extraction.parameters) or (
            extraction.intent == "unsupported" and SQL_INJECTION_RE.search(raw_user_query)
        ):
            return ValidatedIntentOutcome(
                status="unsupported",
                raw_intent=extraction,
                message="Unsupported request: arbitrary SQL or direct database queries are not permitted.",
            )

        if extraction.intent == "unsupported":
            return ValidatedIntentOutcome(
                status="unsupported",
                raw_intent=extraction,
                message=(
                    extraction.clarification_question
                    or "This request is outside the supported hospital operations catalog."
                ),
            )

        if extraction.requires_clarification:
            return ValidatedIntentOutcome(
                status="clarification_required",
                raw_intent=extraction,
                message=extraction.clarification_question
                or "Could you please clarify the details of your request?",
            )

        spec = OPERATION_REGISTRY.get(extraction.intent)
        if spec is None:
            return ValidatedIntentOutcome(
                status="unsupported",
                raw_intent=extraction,
                message=f"Operation '{extraction.intent}' is not in the approved registry.",
            )

        params_dict: Dict[str, Any] = dict(extraction.parameters or {})

        # Resolve explicit self-reference in users.manage_access using trusted server-side user_id
        if extraction.intent == "users.manage_access":
            target_name = str(params_dict.get("target_user_name") or "").strip().lower()
            if target_name in ("self", "me", "myself", "my", "my own"):
                params_dict["target_user_id"] = str(current_user.user_id)
                params_dict["target_user_name"] = None

        try:
            validated_params = spec.schema_cls.model_validate(params_dict)
        except ValidationError as exc:
            # If parameters are missing for a known operation, safely ask for clarification
            missing_fields = [
                ".".join(str(loc) for loc in err.get("loc", []))
                for err in exc.errors()
                if err.get("type") == "missing"
            ]
            if missing_fields or extraction.intent in ("users.manage_access", "bills.discount", "inventory.update"):
                return ValidatedIntentOutcome(
                    status="clarification_required",
                    raw_intent=extraction,
                    spec=spec,
                    message=IntentValidator._friendly_clarification(extraction.intent, exc),
                )
            return ValidatedIntentOutcome(
                status="invalid",
                raw_intent=extraction,
                spec=spec,
                message=f"Invalid parameters for {extraction.intent}: {exc.errors()[0].get('msg')}",
            )

        return ValidatedIntentOutcome(
            status="valid",
            raw_intent=extraction,
            spec=spec,
            validated_params=validated_params,
        )

    @staticmethod
    def _friendly_clarification(intent: str, exc: ValidationError) -> str:
        if intent == "users.manage_access":
            return (
                "Please specify which user, what action (grant or remove), and which exact "
                "permission or role you want to change."
            )
        if intent == "bills.discount":
            return "Please specify the discount percentage (0–100%) and which bills (e.g., last month's bills or a specific patient/bill)."
        if intent == "inventory.update":
            return "Please specify which inventory items to update (e.g., category, batch, or item name) and the new quantity or price."
        return f"Please clarify your request: {exc.errors()[0].get('msg', 'missing required details')}."

