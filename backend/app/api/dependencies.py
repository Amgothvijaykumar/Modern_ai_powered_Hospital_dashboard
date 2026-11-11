from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import apply_rls_context, get_db
from app.core.security import verify_jwt_token
from app.models import User, UserRole
from app.schemas.auth import CurrentUserContext

bearer_scheme = HTTPBearer(auto_error=False)


def resolve_user_context_by_auth_id(db: Session, auth_user_id, auth_provider: str) -> CurrentUserContext:
    stmt = (
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.auth_user_id == auth_user_id)
    )
    user = db.scalar(stmt)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user profile was not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    apply_rls_context(db, user.hospital_id, user.id)
    role_names = sorted({ur.role.name for ur in user.user_roles if ur.role is not None})

    return CurrentUserContext(
        user_id=user.id,
        auth_user_id=user.auth_user_id,
        hospital_id=user.hospital_id,
        hospital_name=user.hospital.name if user.hospital else "",
        full_name=user.full_name,
        email=user.email,
        roles=role_names,
        is_active=user.is_active,
        auth_provider=auth_provider,
    )


def get_current_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUserContext:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )
    identity = verify_jwt_token(credentials.credentials)
    return resolve_user_context_by_auth_id(db, identity.auth_user_id, identity.provider)

