from datetime import datetime, timezone

from sqlalchemy import JSON
from sqlalchemy.dialects import postgresql

JSONBType = JSON().with_variant(postgresql.JSONB(astext_type=None), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

