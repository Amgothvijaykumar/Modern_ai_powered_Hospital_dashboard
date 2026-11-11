import hmac

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user_context
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_demo_access_token, verify_jwt_token
from app.models import User, UserRole
from app.schemas.auth import CurrentUserContext, LoginRequest, SessionResponse, UserSummary

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _authenticate_demo_user(db: Session, email: str, password: str) -> tuple[User, str]:
    """Validate seeded demo credentials against the local database and issue a demo JWT."""
    settings = get_settings()
    stmt = (
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.email == email.lower())
    )
    user = db.scalar(stmt)
    password_ok = hmac.compare_digest(password, settings.DEMO_USER_PASSWORD)
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user, create_demo_access_token(user.auth_user_id, user.email)


@router.post("/session", response_model=SessionResponse)
async def create_session(payload: LoginRequest, db: Session = Depends(get_db)) -> SessionResponse:
    """Authenticate via Supabase Auth (when configured) or local demo credentials."""
    settings = get_settings()
    supabase_configured = (
        bool(settings.SUPABASE_URL)
        and bool(settings.SUPABASE_ANON_KEY)
        and "your-project-ref" not in settings.SUPABASE_URL
    )

    user: User | None = None
    access_token: str | None = None

    if supabase_configured:
        token_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
        resp = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    token_url,
                    headers={
                        "apikey": settings.SUPABASE_ANON_KEY,
                        "Content-Type": "application/json",
                    },
                    json={"email": payload.email, "password": payload.password},
                )
        except httpx.HTTPError as exc:
            if not settings.ALLOW_DEMO_AUTH:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Supabase authentication service is unavailable",
                ) from exc

        if resp is not None and resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Supabase authentication did not return a session token",
                )
            identity = verify_jwt_token(access_token)
            stmt = (
                select(User)
                .options(selectinload(User.user_roles).selectinload(UserRole.role))
                .where(User.auth_user_id == identity.auth_user_id)
            )
            user = db.scalar(stmt)
        elif settings.ALLOW_DEMO_AUTH:
            user, access_token = _authenticate_demo_user(db, payload.email, payload.password)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
    elif settings.ALLOW_DEMO_AUTH:
        user, access_token = _authenticate_demo_user(db, payload.email, payload.password)
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not configured",
        )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile is missing or inactive",
        )

    roles = sorted({ur.role.name for ur in user.user_roles if ur.role is not None})
    return SessionResponse(
        access_token=access_token,
        user=UserSummary(
            id=user.id,
            hospital_id=user.hospital_id,
            hospital_name=user.hospital.name if user.hospital else "",
            full_name=user.full_name,
            email=user.email,
            roles=roles,
            is_active=user.is_active,
        ),
    )


@router.get("/me", response_model=CurrentUserContext)
def get_me(current_user: CurrentUserContext = Depends(get_current_user_context)) -> CurrentUserContext:
    return current_user

