from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.auth import CurrentUserContext
from app.schemas.operations import UsersReadParams
from app.services.operations.common import OperationDeniedError
from app.services.operations.user_ops import read_users

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("")
def list_users(
    search: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    include_permissions: bool = Query(default=True),
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    try:
        params = UsersReadParams(
            search=search,
            role=role,
            include_permissions=include_permissions,
        )
        return read_users(db, current_user, params)
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

