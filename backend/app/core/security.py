from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import get_settings


@dataclass(frozen=True)
class AuthenticatedIdentity:
    auth_user_id: uuid.UUID
    email: Optional[str]
    provider: str


_jwks_client_cache: dict[str, PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    if jwks_url not in _jwks_client_cache:
        _jwks_client_cache[jwks_url] = PyJWKClient(jwks_url)
    return _jwks_client_cache[jwks_url]


def create_demo_access_token(
    auth_user_id: uuid.UUID,
    email: str,
    expires_minutes: int = 480,
) -> str:
    """Issue a signed JWT for local development/testing when ALLOW_DEMO_AUTH=true.

    Note: Only `sub` (auth_user_id) and `email` are embedded; hospital_id and roles
    are ALWAYS resolved server-side from the database.
    """
    settings = get_settings()
    if not settings.ALLOW_DEMO_AUTH:
        raise RuntimeError("Demo authentication is disabled")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(auth_user_id),
        "email": email,
        "iss": "hospital-ai-demo",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.DEMO_JWT_SECRET, algorithm="HS256")


def verify_jwt_token(token: str) -> AuthenticatedIdentity:
    """Verify either a Supabase Auth JWT or (when enabled) a local demo JWT."""
    settings = get_settings()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token format",
        ) from exc

    issuer = unverified_claims.get("iss")
    alg = unverified_header.get("alg", "HS256")

    # 1. Local Demo JWT path (explicitly gated by ALLOW_DEMO_AUTH)
    if issuer == "hospital-ai-demo":
        if not settings.ALLOW_DEMO_AUTH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Demo tokens are disabled in this environment",
            )
        try:
            claims = jwt.decode(
                token,
                settings.DEMO_JWT_SECRET,
                algorithms=["HS256"],
                issuer="hospital-ai-demo",
            )
            return AuthenticatedIdentity(
                auth_user_id=uuid.UUID(claims["sub"]),
                email=claims.get("email"),
                provider="demo",
            )
        except (InvalidTokenError, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token",
            ) from exc

    # 2. Supabase Auth JWT path
    try:
        if alg in ("RS256", "ES256") and settings.SUPABASE_URL:
            jwks_client = _get_jwks_client(settings.SUPABASE_URL)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
        elif settings.SUPABASE_JWT_SECRET and "your-supabase" not in settings.SUPABASE_JWT_SECRET:
            claims = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication provider is not configured for this token",
            )

        return AuthenticatedIdentity(
            auth_user_id=uuid.UUID(claims["sub"]),
            email=claims.get("email"),
            provider="supabase",
        )
    except HTTPException:
        raise
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase session token",
        ) from exc

