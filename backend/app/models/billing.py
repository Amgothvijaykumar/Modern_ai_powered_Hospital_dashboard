import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import utcnow


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("gross_amount >= 0", name="ck_bills_gross_nonneg"),
        CheckConstraint("discount_amount >= 0", name="ck_bills_discount_nonneg"),
        CheckConstraint("net_amount >= 0", name="ck_bills_net_nonneg"),
        CheckConstraint("discount_amount <= gross_amount", name="ck_bills_discount_le_gross"),
        CheckConstraint(
            "status IN ('PENDING', 'PAID', 'PARTIALLY_PAID', 'CANCELLED', 'REFUNDED')",
            name="ck_bills_status_valid",
        ),
        CheckConstraint("version >= 1", name="ck_bills_version_pos"),
        Index("ix_bills_hospital_id", "hospital_id"),
        Index("ix_bills_hospital_created_at", "hospital_id", "created_at"),
        Index("ix_bills_hospital_status", "hospital_id", "status"),
        Index("ix_bills_hospital_creator", "hospital_id", "created_by_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

