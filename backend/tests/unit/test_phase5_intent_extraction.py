import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import resolve_user_context_by_auth_id
from app.models import User
from app.schemas.intent import IntentExtractionResult
from app.services.intent.validator import IntentValidator
from app.services.llm.intent_extractor import IntentExtractorService


def _ctx(db: Session, email: str):
    u = db.scalar(select(User).where(User.email == email))
    assert u is not None
    return resolve_user_context_by_auth_id(db, u.auth_user_id, "demo")


def test_paraphrases_map_to_common_operation(db_session: Session):
    extractor = IntentExtractorService()
    admin = _ctx(db_session, "admin.a@metrogeneral.org")

    for phrase in [
        "Show medicines with low stock.",
        "Which medicines are running out?",
        "Find items below minimum quantity.",
    ]:
        ext = extractor.extract(phrase)
        outcome = IntentValidator.validate(ext, admin, phrase)
        assert outcome.status == "valid"
        assert outcome.spec is not None
        assert outcome.validated_params is not None
        assert outcome.spec.operation_key == "inventory.read"
        assert outcome.validated_params.filter == "low_stock"  # type: ignore[attr-defined]

    for phrase in [
        "Apply a 10% discount to last month's bills.",
        "Give last month's bills a 10 percent discount.",
    ]:
        ext = extractor.extract(phrase)
        outcome = IntentValidator.validate(ext, admin, phrase)
        assert outcome.status == "valid"
        assert outcome.spec is not None
        assert outcome.validated_params is not None
        assert outcome.spec.operation_key == "bills.discount"
        assert str(outcome.validated_params.discount_percentage) in ("10", "10.0")  # type: ignore[attr-defined]
        assert outcome.validated_params.period == "last_month"  # type: ignore[attr-defined]


def test_ambiguous_request_triggers_clarification(db_session: Session):
    extractor = IntentExtractorService()
    admin = _ctx(db_session, "admin.a@metrogeneral.org")

    ext = extractor.extract("Give Ravi access.")
    outcome = IntentValidator.validate(ext, admin, "Give Ravi access.")
    assert outcome.status == "clarification_required"
    assert outcome.message is not None


def test_sql_injection_and_unsupported_rejected(db_session: Session):
    extractor = IntentExtractorService()
    admin = _ctx(db_session, "admin.a@metrogeneral.org")

    for query in [
        "SELECT * FROM users;",
        "DROP TABLE inventory_items;--",
        "Book a cardiology appointment for tomorrow",
    ]:
        ext = extractor.extract(query)
        outcome = IntentValidator.validate(ext, admin, query)
        assert outcome.status == "unsupported"


def test_gemini_structured_output_integration_and_malformed_rejection(db_session: Session):
    admin = _ctx(db_session, "admin.a@metrogeneral.org")

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(
            {
                "intent": "inventory.read",
                "parameters": {"filter": "expiring_soon", "expiring_days": 30},
                "requires_clarification": False,
                "clarification_question": None,
            }
        )
    )
    extractor = IntentExtractorService(gemini_client=mock_client)
    ext = extractor.extract("Show medicines expiring in 30 days")
    assert ext.extractor_source == "gemini"
    outcome = IntentValidator.validate(ext, admin, "Show medicines expiring in 30 days")
    assert outcome.status == "valid"
    assert outcome.validated_params is not None
    assert outcome.validated_params.expiring_days == 30  # type: ignore[attr-defined]

    # Reject unknown operation or unexpected fields even if returned by model
    with pytest.raises(ValidationError):
        IntentExtractionResult.model_validate(
            {
                "intent": "execute_raw_sql",
                "parameters": {"sql": "DELETE FROM bills"},
                "requires_clarification": False,
            }
        )

    # Reject SQL hidden inside valid intent parameter
    sneaky = IntentExtractionResult(
        intent="inventory.read",
        parameters={"filter": "search", "search": "paracetamol; DROP TABLE bills;--"},
        requires_clarification=False,
    )
    sneaky_outcome = IntentValidator.validate(sneaky, admin, "find paracetamol")
    assert sneaky_outcome.status == "unsupported"

