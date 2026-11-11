import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import utcnow


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("hospital_id", "batch_number", name="uq_inventory_hospital_batch"),
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonneg"),
        CheckConstraint("minimum_quantity >= 0", name="ck_inventory_min_qty_nonneg"),
        CheckConstraint("unit_price >= 0", name="ck_inventory_unit_price_nonneg"),
        CheckConstraint("version >= 1", name="ck_inventory_version_pos"),
        Index("ix_inventory_hospital_id", "hospital_id"),
        Index("ix_inventory_hospital_expiry", "hospital_id", "expiry_date"),
        Index("ix_inventory_hospital_category", "hospital_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

