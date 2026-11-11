import os
import tempfile
from typing import Generator

# Keep automated tests offline and deterministic even when root .env holds live keys.
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")
os.environ.setdefault("TEST_DATABASE_URL", "")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_ANON_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from seed.seed_data import seed_database


@pytest.fixture(scope="session")
def test_engine():
    settings = get_settings()
    if settings.TEST_DATABASE_URL:
        engine = create_engine(settings.TEST_DATABASE_URL, pool_pre_ping=True)
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        engine.dispose()
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_suite.db")
            engine = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=engine)
            yield engine
            engine.dispose()


@pytest.fixture(scope="session")
def seeded_engine(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    with TestingSession() as db:
        seed_database(db, inventory_per_hospital=620, bills_per_hospital=520)
    return test_engine


@pytest.fixture()
def db_session(seeded_engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(bind=seeded_engine, autocommit=False, autoflush=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(seeded_engine) -> Generator[TestClient, None, None]:
    TestingSession = sessionmaker(bind=seeded_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login_as(client: TestClient, email: str) -> dict:
    settings = get_settings()
    resp = client.post(
        "/api/auth/session",
        json={"email": email, "password": settings.DEMO_USER_PASSWORD},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    data = resp.json()
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "user": data["user"],
        "token": data["access_token"],
    }

