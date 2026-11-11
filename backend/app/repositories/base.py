import uuid
from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import apply_rls_context

ModelT = TypeVar("ModelT")


class TenantScopedRepository(Generic[ModelT]):
    """Base repository enforcing mandatory hospital_id scoping on every query.

    Even if a privileged connection bypasses PostgreSQL RLS (e.g. Supabase service_role),
    every query built through this base class binds `model.hospital_id == self.hospital_id`
    and sets PostgreSQL session context variables as defense-in-depth.
    """

    def __init__(self, db: Session, hospital_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        self.db = db
        self.hospital_id = hospital_id
        self.user_id = user_id
        apply_rls_context(db, hospital_id, user_id)

    def _base_select(self, model: Type[ModelT]):
        return select(model).where(model.hospital_id == self.hospital_id)

    def get_by_id(self, model: Type[ModelT], record_id: uuid.UUID) -> Optional[ModelT]:
        stmt = self._base_select(model).where(model.id == record_id)
        return self.db.scalar(stmt)

    def list_all(self, model: Type[ModelT], limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        stmt = self._base_select(model).offset(offset).limit(limit)
        return self.db.scalars(stmt).all()

