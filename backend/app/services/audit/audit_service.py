from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import apply_rls_context
from app.models import AuditLog
from app.schemas.auth import CurrentUserContext
from app.services.operations.common import OperationDeniedError
from app.services.permissions.engine import PermissionEngine

SENSITIVE_KEYS = {"password", "token", "access_token", "api_key", "secret", "confirmation_token"}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sanitize_payload(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, (Decimal, uuid.UUID, date, datetime)):
        return str(value)
    return value


def _sanitize_payload(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if data is None:
        return None
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        if str(k).lower() in SENSITIVE_KEYS:
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = _sanitize_value(v)
    return sanitized


class AuditService:
    """Append-only audit logging service for all operation attempts and outcomes."""

    @staticmethod
    def record(
        db: Session,
        *,
        hospital_id: Optional[uuid.UUID],
        user_id: Optional[uuid.UUID],
        raw_user_query: str,
        parsed_intent: Optional[Dict[str, Any]],
        operation: Optional[str],
        authorization_result: str,
        decision_reason: str,
        affected_rows: Optional[int],
        execution_status: str,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        if hospital_id is not None:
            apply_rls_context(db, hospital_id, user_id)

        entry = AuditLog(
            id=uuid.uuid4(),
            hospital_id=hospital_id,
            user_id=user_id,
            raw_user_query=raw_user_query,
            parsed_intent=_sanitize_payload(parsed_intent),
            operation=operation,
            authorization_result=authorization_result,
            decision_reason=decision_reason,
            affected_rows=affected_rows,
            execution_status=execution_status,
            before_data=_sanitize_payload(before_data),
            after_data=_sanitize_payload(after_data),
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def list_audit_logs(
        db: Session,
        user_context: CurrentUserContext,
        *,
        limit: int = 50,
        offset: int = 0,
        operation: Optional[str] = None,
        execution_status: Optional[str] = None,
    ) -> tuple[List[AuditLog], int]:
        # Strictly Admin-only (users.read + Admin role check)
        perm_decision = PermissionEngine(db).authorize(user_context, "users.read")
        if not perm_decision.allowed or "Admin" not in user_context.roles:
            raise OperationDeniedError(
                "Permission denied: only hospital Admins may view audit logs."
            )

        apply_rls_context(db, user_context.hospital_id, user_context.user_id)
        stmt = select(AuditLog).where(AuditLog.hospital_id == user_context.hospital_id)
        if operation:
            stmt = stmt.where(AuditLog.operation == operation)
        if execution_status:
            stmt = stmt.where(AuditLog.execution_status == execution_status)

        total_count = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            db.scalars(
                stmt.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
            ).all()
        )
        return rows, int(total_count)
