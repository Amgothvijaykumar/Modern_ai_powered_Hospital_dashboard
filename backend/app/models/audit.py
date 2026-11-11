import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import JSONBType, utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_hospital_created_at", "hospital_id", "created_at"),
        Index("ix_audit_log_user_id", "user_id"),
        Index("ix_audit_log_operation", "operation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    raw_user_query: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    operation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    authorization_result: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    affected_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(50), nullable=False)
    before_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    after_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

