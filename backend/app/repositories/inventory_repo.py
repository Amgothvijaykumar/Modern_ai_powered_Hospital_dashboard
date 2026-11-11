from datetime import date
from typing import List, Optional, Sequence
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import InventoryItem
from app.repositories.base import TenantScopedRepository
from app.schemas.operations import InventoryDeleteParams, InventoryReadParams, InventoryUpdateParams
from app.utils.dates import resolve_expiry_window


class InventoryRepository(TenantScopedRepository[InventoryItem]):
    def __init__(self, db: Session, hospital_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        super().__init__(db, hospital_id, user_id)

    def query_items(self, params: InventoryReadParams) -> tuple[Sequence[InventoryItem], int]:
        stmt = self._base_select(InventoryItem)

        if params.item_id is not None:
            stmt = stmt.where(InventoryItem.id == params.item_id)
        if params.category:
            stmt = stmt.where(func.lower(InventoryItem.category) == params.category.strip().lower())
        if params.search:
            pattern = f"%{params.search.strip()}%"
            stmt = stmt.where(InventoryItem.item_name.ilike(pattern))

        if params.filter == "low_stock":
            stmt = stmt.where(InventoryItem.quantity < InventoryItem.minimum_quantity)
        elif params.filter == "out_of_stock":
            stmt = stmt.where(InventoryItem.quantity == 0)
        elif params.filter == "expiring_soon":
            start_d, end_d = resolve_expiry_window(params.expiring_days)
            stmt = stmt.where(
                InventoryItem.expiry_date >= start_d,
                InventoryItem.expiry_date <= end_d,
            )

        total_count = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.order_by(InventoryItem.item_name.asc(), InventoryItem.id.asc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
        return items, int(total_count)

    def get_summary_metrics(self, expiring_days: int = 30) -> dict:
        base = self._base_select(InventoryItem)
        total_items = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        low_stock_count = (
            self.db.scalar(
                select(func.count()).select_from(
                    base.where(InventoryItem.quantity < InventoryItem.minimum_quantity).subquery()
                )
            )
            or 0
        )
        out_of_stock_count = (
            self.db.scalar(
                select(func.count()).select_from(
                    base.where(InventoryItem.quantity == 0).subquery()
                )
            )
            or 0
        )
        start_d, end_d = resolve_expiry_window(expiring_days)
        expiring_count = (
            self.db.scalar(
                select(func.count()).select_from(
                    base.where(
                        InventoryItem.expiry_date >= start_d,
                        InventoryItem.expiry_date <= end_d,
                    ).subquery()
                )
            )
            or 0
        )
        return {
            "total_items": int(total_items),
            "low_stock_count": int(low_stock_count),
            "out_of_stock_count": int(out_of_stock_count),
            "expiring_count": int(expiring_count),
            "expiry_window_start": start_d.isoformat(),
            "expiry_window_end": end_d.isoformat(),
        }

    def find_targets_for_update(self, params: InventoryUpdateParams) -> List[InventoryItem]:
        stmt = self._base_select(InventoryItem)
        if params.item_id is not None:
            stmt = stmt.where(InventoryItem.id == params.item_id)
        if params.batch_number:
            stmt = stmt.where(InventoryItem.batch_number == params.batch_number.strip())
        if params.category:
            stmt = stmt.where(func.lower(InventoryItem.category) == params.category.strip().lower())
        if params.search:
            stmt = stmt.where(InventoryItem.item_name.ilike(f"%{params.search.strip()}%"))
        if params.filter == "low_stock":
            stmt = stmt.where(InventoryItem.quantity < InventoryItem.minimum_quantity)
        elif params.filter == "expiring_soon":
            start_d, end_d = resolve_expiry_window(params.expiring_days)
            stmt = stmt.where(
                InventoryItem.expiry_date >= start_d,
                InventoryItem.expiry_date <= end_d,
            )
        return list(self.db.scalars(stmt.order_by(InventoryItem.id.asc())).all())

    def find_targets_for_delete(self, params: InventoryDeleteParams) -> List[InventoryItem]:
        stmt = self._base_select(InventoryItem)
        if params.item_id is not None:
            stmt = stmt.where(InventoryItem.id == params.item_id)
        if params.batch_number:
            stmt = stmt.where(InventoryItem.batch_number == params.batch_number.strip())
        if params.category:
            stmt = stmt.where(func.lower(InventoryItem.category) == params.category.strip().lower())
        if params.filter == "expired":
            start_d, _ = resolve_expiry_window(0)
            stmt = stmt.where(InventoryItem.expiry_date < start_d)
        elif params.filter == "out_of_stock":
            stmt = stmt.where(InventoryItem.quantity == 0)
        return list(self.db.scalars(stmt.order_by(InventoryItem.id.asc())).all())

