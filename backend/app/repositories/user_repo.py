from typing import List, Optional, Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Permission, Role, User, UserPermissionOverride, UserRole
from app.repositories.base import TenantScopedRepository


class AmbiguousUserError(Exception):
    def __init__(self, matches: List[User]):
        self.matches = matches
        super().__init__("Multiple users matched the provided name within this hospital")


class UserRepository(TenantScopedRepository[User]):
    def __init__(self, db: Session, hospital_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        super().__init__(db, hospital_id, user_id)

    def list_hospital_users(
        self, search: Optional[str] = None, role_name: Optional[str] = None
    ) -> Sequence[User]:
        stmt = (
            self._base_select(User)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role),
                selectinload(User.permission_overrides).selectinload(
                    UserPermissionOverride.permission
                ),
            )
            .order_by(User.full_name.asc())
        )
        if search:
            pat = f"%{search.strip()}%"
            stmt = stmt.where((User.full_name.ilike(pat)) | (User.email.ilike(pat)))
        users = list(self.db.scalars(stmt).all())
        if role_name:
            users = [
                u
                for u in users
                if any(ur.role and ur.role.name == role_name for ur in u.user_roles)
            ]
        return users

    def resolve_target_user(
        self,
        *,
        target_user_id: Optional[uuid.UUID] = None,
        target_user_email: Optional[str] = None,
        target_user_name: Optional[str] = None,
    ) -> Optional[User]:
        """Resolve target user strictly within self.hospital_id. Never leaks other hospitals."""
        base = self._base_select(User).options(
            selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(User.permission_overrides).selectinload(
                UserPermissionOverride.permission
            ),
        )
        if target_user_id is not None:
            return self.db.scalar(base.where(User.id == target_user_id))
        if target_user_email:
            return self.db.scalar(base.where(User.email == target_user_email.strip().lower()))
        if target_user_name:
            name_clean = target_user_name.strip()
            exact_matches = list(
                self.db.scalars(base.where(User.full_name.ilike(name_clean))).all()
            )
            if len(exact_matches) == 1:
                return exact_matches[0]
            if len(exact_matches) > 1:
                raise AmbiguousUserError(exact_matches)

            partial_matches = list(
                self.db.scalars(base.where(User.full_name.ilike(f"%{name_clean}%"))).all()
            )
            if len(partial_matches) == 1:
                return partial_matches[0]
            if len(partial_matches) > 1:
                raise AmbiguousUserError(partial_matches)
        return None

    def get_role_by_name(self, role_name: str) -> Optional[Role]:
        return self.db.scalar(select(Role).where(Role.name == role_name))

    def get_permission_by_key(self, permission_key: str) -> Optional[Permission]:
        return self.db.scalar(select(Permission).where(Permission.permission_key == permission_key))

