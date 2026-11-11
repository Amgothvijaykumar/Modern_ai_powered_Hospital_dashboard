import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserSummary(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    hospital_name: str
    full_name: str
    email: EmailStr
    roles: List[str]
    is_active: bool


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class CurrentUserContext(BaseModel):
    """Trusted server-side identity context resolved exclusively from DB + verified JWT."""

    user_id: uuid.UUID
    auth_user_id: uuid.UUID
    hospital_id: uuid.UUID
    hospital_name: str
    full_name: str
    email: str
    roles: List[str]
    is_active: bool
    auth_provider: str = "demo"


class EffectivePermissionDetail(BaseModel):
    permission_key: str
    allowed: bool
    source: str
    constraints: Dict[str, object] = Field(default_factory=dict)


class PermissionsMeResponse(BaseModel):
    user_id: uuid.UUID
    hospital_id: uuid.UUID
    hospital_name: str
    roles: List[str]
    permissions: Dict[str, EffectivePermissionDetail]

