from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.auth import CurrentUserContext, PermissionsMeResponse
from app.services.permissions.engine import PermissionEngine

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


@router.get("/me", response_model=PermissionsMeResponse)
def get_my_permissions(
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> PermissionsMeResponse:
    engine = PermissionEngine(db)
    effective = engine.resolve_effective_permissions(current_user.user_id)
    return PermissionsMeResponse(
        user_id=current_user.user_id,
        hospital_id=current_user.hospital_id,
        hospital_name=current_user.hospital_name,
        roles=current_user.roles,
        permissions=effective,
    )

