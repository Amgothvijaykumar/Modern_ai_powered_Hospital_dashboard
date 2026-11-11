import uuid
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    """Ensure PostgreSQL URLs explicitly use the psycopg v3 driver."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def create_db_engine(database_url: Optional[str] = None):
    settings = get_settings()
    url = normalize_database_url(database_url or settings.DATABASE_URL)
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def apply_rls_context(db: Session, hospital_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> None:
    """Set PostgreSQL session-local variables used by RLS policies.

    No-op on SQLite test engines; enforced on PostgreSQL/Supabase.
    """
    dialect_name = db.bind.dialect.name if db.bind is not None else ""
    if dialect_name == "postgresql":
        db.execute(
            text("SELECT set_config('app.current_hospital_id', :hid, true)"),
            {"hid": str(hospital_id)},
        )
        if user_id is not None:
            db.execute(
                text("SELECT set_config('app.current_user_id', :uid, true)"),
                {"uid": str(user_id)},
            )


@contextmanager
def transaction_scope(db: Session) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise

