import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import JSONBType, utcnow


class OperationConfirmation(Base):
    __tablename__ = "operation_confirmations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'INVALIDATED', 'FAILED')",
            name="ck_op_confirm_status_valid",
        ),
        CheckConstraint("expected_row_count >= 0", name="ck_op_confirm_rows_nonneg"),
        Index("ix_op_confirm_hospital_user", "hospital_id", "user_id"),
        Index("ix_op_confirm_token_hash", "token_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    raw_user_query: Mapped[str] = mapped_column(Text, nullable=False)
    expected_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_exact_row_count: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_summary: Mapped[Dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

