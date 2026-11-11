from decimal import Decimal
from typing import List, Optional, Sequence
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Bill
from app.repositories.base import TenantScopedRepository
from app.schemas.operations import BillsDiscountParams, BillsReadParams, BillsUpdateStatusParams
from app.utils.dates import DateRangeResult, resolve_date_range


class BillingRepository(TenantScopedRepository[Bill]):
    def __init__(self, db: Session, hospital_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        super().__init__(db, hospital_id, user_id)

    def query_bills(
        self,
        params: BillsReadParams,
        *,
        own_only: bool = False,
        owner_user_id: Optional[uuid.UUID] = None,
    ) -> tuple[Sequence[Bill], int, Optional[DateRangeResult]]:
        stmt = self._base_select(Bill)
        if own_only:
            if owner_user_id is None:
                raise ValueError("owner_user_id is required when own_only scope is active")
            stmt = stmt.where(Bill.created_by_user_id == owner_user_id)

        if params.bill_id is not None:
            stmt = stmt.where(Bill.id == params.bill_id)
        if params.patient_search:
            stmt = stmt.where(Bill.patient_name.ilike(f"%{params.patient_search.strip()}%"))

        status_from_filter = {
            "pending": "PENDING",
            "paid": "PAID",
            "partially_paid": "PARTIALLY_PAID",
            "cancelled": "CANCELLED",
            "refunded": "REFUNDED",
        }.get(params.filter)
        effective_status = params.status or status_from_filter
        if effective_status:
            stmt = stmt.where(Bill.status == effective_status)

        date_range: Optional[DateRangeResult] = None
        if params.period or (params.start_date and params.end_date):
            date_range = resolve_date_range(params.period, params.start_date, params.end_date)
            stmt = stmt.where(
                Bill.created_at >= date_range.start_utc,
                Bill.created_at < date_range.end_utc_exclusive,
            )

        total_count = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        bills = self.db.scalars(
            stmt.order_by(Bill.created_at.desc(), Bill.id.asc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
        return bills, int(total_count), date_range

    def get_summary_metrics(
        self,
        *,
        own_only: bool = False,
        owner_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        stmt = self._base_select(Bill)
        if own_only and owner_user_id is not None:
            stmt = stmt.where(Bill.created_by_user_id == owner_user_id)

        total_bills = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        pending_count = (
            self.db.scalar(
                select(func.count()).select_from(stmt.where(Bill.status == "PENDING").subquery())
            )
            or 0
        )
        paid_count = (
            self.db.scalar(
                select(func.count()).select_from(stmt.where(Bill.status == "PAID").subquery())
            )
            or 0
        )
        total_net = (
            self.db.scalar(
                select(func.coalesce(func.sum(Bill.net_amount), Decimal("0.00"))).where(
                    Bill.hospital_id == self.hospital_id,
                    *(
                        [Bill.created_by_user_id == owner_user_id]
                        if (own_only and owner_user_id is not None)
                        else []
                    ),
                )
            )
            or Decimal("0.00")
        )
        return {
            "total_bills": int(total_bills),
            "pending_count": int(pending_count),
            "paid_count": int(paid_count),
            "total_net_amount": str(Decimal(total_net).quantize(Decimal("0.01"))),
        }

    def find_targets_for_discount(
        self, params: BillsDiscountParams
    ) -> tuple[List[Bill], Optional[DateRangeResult]]:
        stmt = self._base_select(Bill)
        if params.bill_id is not None:
            stmt = stmt.where(Bill.id == params.bill_id)
        if params.patient_search:
            stmt = stmt.where(Bill.patient_name.ilike(f"%{params.patient_search.strip()}%"))

        if params.status_filter == "ALL_ELIGIBLE":
            stmt = stmt.where(Bill.status.notin_(["CANCELLED", "REFUNDED"]))
        else:
            stmt = stmt.where(Bill.status == params.status_filter)

        date_range: Optional[DateRangeResult] = None
        if params.period or (params.start_date and params.end_date):
            date_range = resolve_date_range(params.period, params.start_date, params.end_date)
            stmt = stmt.where(
                Bill.created_at >= date_range.start_utc,
                Bill.created_at < date_range.end_utc_exclusive,
            )

        bills = list(self.db.scalars(stmt.order_by(Bill.created_at.asc(), Bill.id.asc())).all())
        return bills, date_range

    def find_targets_for_status_update(
        self, params: BillsUpdateStatusParams
    ) -> tuple[List[Bill], Optional[DateRangeResult]]:
        stmt = self._base_select(Bill)
        if params.bill_id is not None:
            stmt = stmt.where(Bill.id == params.bill_id)
        if params.patient_search:
            stmt = stmt.where(Bill.patient_name.ilike(f"%{params.patient_search.strip()}%"))
        if params.current_status:
            stmt = stmt.where(Bill.status == params.current_status)

        date_range: Optional[DateRangeResult] = None
        if params.period or (params.start_date and params.end_date):
            date_range = resolve_date_range(params.period, params.start_date, params.end_date)
            stmt = stmt.where(
                Bill.created_at >= date_range.start_utc,
                Bill.created_at < date_range.end_utc_exclusive,
            )

        bills = list(self.db.scalars(stmt.order_by(Bill.created_at.asc(), Bill.id.asc())).all())
        return bills, date_range

