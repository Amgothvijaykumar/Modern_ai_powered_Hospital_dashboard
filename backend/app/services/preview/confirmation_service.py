from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import apply_rls_context
from app.models import OperationConfirmation
from app.registry.operation_registry import OPERATION_REGISTRY
from app.schemas.auth import CurrentUserContext
from app.services.audit.audit_service import AuditService
from app.services.operations.common import (
    OperationClarificationError,
    OperationDeniedError,
    OperationExecutionResult,
    OperationNotFoundError,
    OperationPreviewData,
    StalePreviewError,
)


class ConfirmationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _sign_confirmation_token(
    confirmation_id: uuid.UUID,
    user_id: uuid.UUID,
    hospital_id: uuid.UUID,
    operation: str,
    nonce: str,
) -> str:
    settings = get_settings()
    msg = f"{confirmation_id}:{user_id}:{hospital_id}:{operation}:{nonce}".encode("utf-8")
    sig = hmac.new(
        settings.CONFIRMATION_TOKEN_SECRET.encode("utf-8"),
        msg,
        hashlib.sha256,
    ).hexdigest()
    return f"{confirmation_id}.{nonce}.{sig}"


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class ConfirmationService:
    """Manages dry-run previews, server-side confirmation tokens, and atomic write execution."""

    @staticmethod
    def create_preview(
        db: Session,
        user_context: CurrentUserContext,
        operation_key: str,
        raw_parameters: Dict[str, Any],
        raw_user_query: str,
    ) -> tuple[OperationPreviewData, OperationConfirmation, str]:
        settings = get_settings()
        apply_rls_context(db, user_context.hospital_id, user_context.user_id)

        spec = OPERATION_REGISTRY.get(operation_key)
        if spec is None or not spec.is_write or spec.preview_handler is None:
            raise ConfirmationError(
                f"Operation '{operation_key}' is not a previewable write operation.", 400
            )

        validated_params = spec.schema_cls.model_validate(raw_parameters)

        try:
            preview_data: OperationPreviewData = spec.preview_handler(
                db, user_context, validated_params
            )
        except OperationDeniedError as exc:
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=raw_user_query,
                parsed_intent={"intent": operation_key, "parameters": raw_parameters},
                operation=operation_key,
                authorization_result="DENIED",
                decision_reason=exc.reason,
                affected_rows=0,
                execution_status="DENIED",
            )
            raise
        except OperationClarificationError as exc:
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=raw_user_query,
                parsed_intent={"intent": operation_key, "parameters": raw_parameters},
                operation=operation_key,
                authorization_result="CLARIFICATION_REQUIRED",
                decision_reason=exc.question,
                affected_rows=0,
                execution_status="CLARIFICATION_REQUIRED",
            )
            raise
        except OperationNotFoundError as exc:
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=raw_user_query,
                parsed_intent={"intent": operation_key, "parameters": raw_parameters},
                operation=operation_key,
                authorization_result="ALLOWED",
                decision_reason=exc.message,
                affected_rows=0,
                execution_status="NOT_EXECUTED",
            )
            raise

        confirmation_id = uuid.uuid4()
        nonce = secrets.token_hex(16)
        raw_token = _sign_confirmation_token(
            confirmation_id,
            user_context.user_id,
            user_context.hospital_id,
            operation_key,
            nonce,
        )
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(seconds=settings.CONFIRMATION_TTL_SECONDS)

        serialized_params = json.loads(validated_params.model_dump_json())
        preview_summary_payload = {
            "summary": preview_data.summary,
            "affected_rows": preview_data.affected_rows,
            "requires_exact_row_count": preview_data.requires_exact_row_count,
            "samples": preview_data.samples,
            "financial_impact": preview_data.financial_impact,
            "resolved_date_range": preview_data.resolved_date_range,
            "business_rules_note": preview_data.business_rules_note,
        }

        record = OperationConfirmation(
            id=confirmation_id,
            token_hash=_hash_token(raw_token),
            hospital_id=user_context.hospital_id,
            user_id=user_context.user_id,
            operation=operation_key,
            parameters=serialized_params,
            raw_user_query=raw_user_query,
            expected_row_count=preview_data.affected_rows,
            requires_exact_row_count=preview_data.requires_exact_row_count,
            snapshot_hash=preview_data.snapshot_hash,
            preview_summary=preview_summary_payload,
            status="PENDING",
            expires_at=expires_at,
            created_at=now_utc,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        AuditService.record(
            db,
            hospital_id=user_context.hospital_id,
            user_id=user_context.user_id,
            raw_user_query=raw_user_query,
            parsed_intent={"intent": operation_key, "parameters": serialized_params},
            operation=operation_key,
            authorization_result="ALLOWED",
            decision_reason="Authorized; dry-run preview generated awaiting confirmation",
            affected_rows=preview_data.affected_rows,
            execution_status="PREVIEW_CREATED",
        )
        return preview_data, record, raw_token

    @staticmethod
    def confirm_and_execute(
        db: Session,
        user_context: CurrentUserContext,
        confirmation_token: str,
        exact_row_count: Optional[int] = None,
    ) -> OperationExecutionResult:
        apply_rls_context(db, user_context.hospital_id, user_context.user_id)
        token_hash = _hash_token(confirmation_token)

        # Strictly bind lookup to authenticated user and hospital
        record = db.scalar(
            select(OperationConfirmation).where(
                OperationConfirmation.token_hash == token_hash,
                OperationConfirmation.hospital_id == user_context.hospital_id,
                OperationConfirmation.user_id == user_context.user_id,
            )
        )
        if record is None:
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query="[confirm_operation]",
                parsed_intent=None,
                operation=None,
                authorization_result="DENIED",
                decision_reason="Invalid confirmation token or token belongs to another user/hospital",
                affected_rows=0,
                execution_status="DENIED",
            )
            raise OperationDeniedError(
                "Confirmation token is invalid, expired, or does not belong to you."
            )

        now_utc = datetime.now(timezone.utc)
        if record.status != "PENDING":
            raise ConfirmationError(
                f"This confirmation has already been {record.status.lower()} and cannot be reused.",
                409,
            )

        if _to_utc(record.expires_at) <= now_utc:
            record.status = "EXPIRED"
            record.resolved_at = now_utc
            db.commit()
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=record.raw_user_query,
                parsed_intent={"intent": record.operation, "parameters": record.parameters},
                operation=record.operation,
                authorization_result="DENIED",
                decision_reason="Confirmation token expired before execution",
                affected_rows=0,
                execution_status="FAILED",
            )
            raise ConfirmationError("Confirmation token has expired. Please request a fresh preview.", 410)

        # Enforce exact row-count entry for operations affecting > 50 rows
        if record.requires_exact_row_count:
            if exact_row_count is None:
                raise ConfirmationError(
                    f"This operation affects {record.expected_row_count} rows (> 50). "
                    f"You must enter the exact number of affected rows ({record.expected_row_count}) to confirm.",
                    422,
                )
            if exact_row_count != record.expected_row_count:
                raise ConfirmationError(
                    f"Row count confirmation mismatch: you entered {exact_row_count}, "
                    f"which does not match the previewed affected row count.",
                    422,
                )

        spec = OPERATION_REGISTRY.get(record.operation)
        if spec is None or spec.execute_handler is None:
            raise ConfirmationError(f"Unsupported operation '{record.operation}'.", 400)

        validated_params = spec.schema_cls.model_validate(record.parameters)

        try:
            result: OperationExecutionResult = spec.execute_handler(
                db,
                user_context,
                validated_params,
                record.snapshot_hash,
                record.expected_row_count,
            )
            record.status = "CONFIRMED"
            record.resolved_at = datetime.now(timezone.utc)
            db.commit()
        except StalePreviewError as exc:
            db.rollback()
            record_ref = db.get(OperationConfirmation, record.id)
            if record_ref is not None:
                record_ref.status = "INVALIDATED"
                record_ref.resolved_at = datetime.now(timezone.utc)
                db.commit()
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=record.raw_user_query,
                parsed_intent={"intent": record.operation, "parameters": record.parameters},
                operation=record.operation,
                authorization_result="ALLOWED",
                decision_reason=exc.message,
                affected_rows=0,
                execution_status="FAILED",
            )
            raise ConfirmationError(exc.message, 409) from exc
        except OperationDeniedError as exc:
            db.rollback()
            record_ref = db.get(OperationConfirmation, record.id)
            if record_ref is not None:
                record_ref.status = "FAILED"
                record_ref.resolved_at = datetime.now(timezone.utc)
                db.commit()
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=record.raw_user_query,
                parsed_intent={"intent": record.operation, "parameters": record.parameters},
                operation=record.operation,
                authorization_result="DENIED",
                decision_reason=exc.reason,
                affected_rows=0,
                execution_status="DENIED",
            )
            raise
        except Exception as exc:
            db.rollback()
            record_ref = db.get(OperationConfirmation, record.id)
            if record_ref is not None:
                record_ref.status = "FAILED"
                record_ref.resolved_at = datetime.now(timezone.utc)
                db.commit()
            AuditService.record(
                db,
                hospital_id=user_context.hospital_id,
                user_id=user_context.user_id,
                raw_user_query=record.raw_user_query,
                parsed_intent={"intent": record.operation, "parameters": record.parameters},
                operation=record.operation,
                authorization_result="ALLOWED",
                decision_reason=f"Execution failed safely and rolled back: {exc}",
                affected_rows=0,
                execution_status="FAILED",
            )
            raise ConfirmationError(f"Operation failed safely and was rolled back: {exc}", 400) from exc

        AuditService.record(
            db,
            hospital_id=user_context.hospital_id,
            user_id=user_context.user_id,
            raw_user_query=record.raw_user_query,
            parsed_intent={"intent": record.operation, "parameters": record.parameters},
            operation=record.operation,
            authorization_result="ALLOWED",
            decision_reason="Confirmed and executed atomically",
            affected_rows=result.affected_rows,
            execution_status="SUCCESS",
            before_data=result.before_data,
            after_data=result.after_data,
        )
        return result

    @staticmethod
    def cancel_preview(
        db: Session,
        user_context: CurrentUserContext,
        confirmation_token: str,
    ) -> OperationConfirmation:
        apply_rls_context(db, user_context.hospital_id, user_context.user_id)
        token_hash = _hash_token(confirmation_token)
        record = db.scalar(
            select(OperationConfirmation).where(
                OperationConfirmation.token_hash == token_hash,
                OperationConfirmation.hospital_id == user_context.hospital_id,
                OperationConfirmation.user_id == user_context.user_id,
            )
        )
        if record is None:
            raise OperationDeniedError(
                "Confirmation token is invalid or does not belong to you."
            )
        if record.status != "PENDING":
            raise ConfirmationError(
                f"Cannot cancel confirmation because its status is already {record.status}.",
                409,
            )

        record.status = "CANCELLED"
        record.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)

        AuditService.record(
            db,
            hospital_id=user_context.hospital_id,
            user_id=user_context.user_id,
            raw_user_query=record.raw_user_query,
            parsed_intent={"intent": record.operation, "parameters": record.parameters},
            operation=record.operation,
            authorization_result="ALLOWED",
            decision_reason="User cancelled the pending operation preview",
            affected_rows=0,
            execution_status="CANCELLED",
        )
        return record

