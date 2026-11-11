from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import InventoryReadParams
from app.services.operations.common import OperationDeniedError
from app.services.operations.inventory_ops import read_inventory

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get("")
def list_inventory(
    filter: str = Query(default="all"),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    expiring_days: int = Query(default=30, ge=1, le=365),
    item_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    try:
        params = InventoryReadParams(
            filter=filter,
            category=category,
            search=search,
            expiring_days=expiring_days,
            item_id=item_id,
            limit=limit,
            offset=offset,
        )
        return read_inventory(db, current_user, params)
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

