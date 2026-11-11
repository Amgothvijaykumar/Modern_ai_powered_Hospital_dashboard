from datetime import date
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import BillsReadParams
from app.services.operations.billing_ops import read_bills
from app.services.operations.common import OperationDeniedError

router = APIRouter(prefix="/api/bills", tags=["Bills"])


@router.get("")
def list_bills(
    filter: str = Query(default="all"),
    period: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    status_param: Optional[str] = Query(default=None, alias="status"),
    patient_search: Optional[str] = Query(default=None),
    bill_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    try:
        params = BillsReadParams(
            filter=filter,
            period=period,
            start_date=start_date,
            end_date=end_date,
            status=status_param,
            patient_search=patient_search,
            bill_id=bill_id,
            limit=limit,
            offset=offset,
        )
        return read_bills(db, current_user, params)
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

