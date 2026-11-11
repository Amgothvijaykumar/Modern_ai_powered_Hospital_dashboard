import uuid

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Hospital, InventoryItem, User
from app.repositories.base import TenantScopedRepository
from seed.seed_data import det_uuid
from tests.conftest import login_as


def test_login_and_trusted_identity_resolution(client):
    auth = login_as(client, "pharmacist.a@metrogeneral.org")
    headers = {"Authorization": auth["Authorization"]}

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me = me_resp.json()
    assert me["email"] == "pharmacist.a@metrogeneral.org"
    assert me["hospital_name"] == "Metro General Hospital"
    assert me["roles"] == ["Pharmacist"]
    assert me["hospital_id"] == str(det_uuid("hospital_a"))


def test_spoofed_jwt_claims_cannot_override_hospital_or_role(client, db_session: Session):
    """Even if a JWT embeds hospital_id or role claims, the server ignores them and uses DB."""
    settings = get_settings()
    pharmacist_a = db_session.scalar(
        select(User).where(User.email == "pharmacist.a@metrogeneral.org")
    )
    hospital_b_id = det_uuid("hospital_b")

    tampered_payload = {
        "sub": str(pharmacist_a.auth_user_id),
        "email": pharmacist_a.email,
        "iss": "hospital-ai-demo",
        "hospital_id": str(hospital_b_id),
        "role": "Admin",
    }
    token = jwt.encode(tampered_payload, settings.DEMO_JWT_SECRET, algorithm="HS256")

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me = me_resp.json()
    assert me["hospital_id"] == str(det_uuid("hospital_a"))
    assert me["roles"] == ["Pharmacist"]


def test_inactive_user_and_missing_token_rejected(client, db_session: Session):
    # Unauthenticated request rejected
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401

    # Deactivate a user temporarily and confirm rejection
    user = db_session.scalar(select(User).where(User.email == "doctor.a@metrogeneral.org"))
    user.is_active = False
    db_session.commit()

    try:
        settings = get_settings()
        login_resp = client.post(
            "/api/auth/session",
            json={"email": "doctor.a@metrogeneral.org", "password": settings.DEMO_USER_PASSWORD},
        )
        assert login_resp.status_code == 403
    finally:
        user.is_active = True
        db_session.commit()


def test_tenant_scoped_repository_isolates_hospitals(db_session: Session):
    hosp_a = db_session.scalar(select(Hospital).where(Hospital.name == "Metro General Hospital"))
    hosp_b = db_session.scalar(select(Hospital).where(Hospital.name == "City Care Medical Center"))

    item_b = db_session.scalar(
        select(InventoryItem).where(InventoryItem.hospital_id == hosp_b.id).limit(1)
    )
    assert item_b is not None

    repo_a = TenantScopedRepository(db_session, hosp_a.id)
    # Hospital A repository must NEVER return Hospital B's record
    assert repo_a.get_by_id(InventoryItem, item_b.id) is None

    repo_b = TenantScopedRepository(db_session, hosp_b.id)
    assert repo_b.get_by_id(InventoryItem, item_b.id) is not None


def test_supabase_configured_falls_back_to_demo_when_allowed(client, monkeypatch):
    """When Supabase Auth is configured and ALLOW_DEMO_AUTH=true, seeded demo users still log in."""
    from types import SimpleNamespace
    import httpx
    from app.api.routes import auth as auth_routes

    class _MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return SimpleNamespace(status_code=400, json=lambda: {"error": "invalid_grant"})

    monkeypatch.setenv("SUPABASE_URL", "https://example-project.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-placeholder")
    monkeypatch.setenv("ALLOW_DEMO_AUTH", "true")
    monkeypatch.setattr(httpx, "AsyncClient", _MockAsyncClient)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        ok_resp = client.post(
            "/api/auth/session",
            json={"email": "admin.a@metrogeneral.org", "password": settings.DEMO_USER_PASSWORD},
        )
        assert ok_resp.status_code == 200
        assert ok_resp.json()["user"]["email"] == "admin.a@metrogeneral.org"

        bad_resp = client.post(
            "/api/auth/session",
            json={"email": "admin.a@metrogeneral.org", "password": "wrong-password"},
        )
        assert bad_resp.status_code == 401

        # When ALLOW_DEMO_AUTH=false, demo fallback must stay strictly disabled
        monkeypatch.setenv("ALLOW_DEMO_AUTH", "false")
        get_settings.cache_clear()
        disabled_resp = client.post(
            "/api/auth/session",
            json={"email": "admin.a@metrogeneral.org", "password": settings.DEMO_USER_PASSWORD},
        )
        assert disabled_resp.status_code == 401
        assert auth_routes is not None
    finally:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "")
        monkeypatch.setenv("ALLOW_DEMO_AUTH", "true")
        get_settings.cache_clear()

