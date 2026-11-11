import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import resolve_user_context_by_auth_id
from app.models import Permission, User, UserPermissionOverride
from app.services.permissions.engine import PermissionEngine
from tests.conftest import login_as


def _ctx(db: Session, email: str):
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return resolve_user_context_by_auth_id(db, user.auth_user_id, "demo")


def test_role_permission_matrix(db_session: Session):
    engine = PermissionEngine(db_session)

    admin = _ctx(db_session, "admin.a@metrogeneral.org")
    billing = _ctx(db_session, "billing.a@metrogeneral.org")
    pharmacist = _ctx(db_session, "pharmacist.a@metrogeneral.org")
    frontdesk = _ctx(db_session, "frontdesk.a@metrogeneral.org")
    doctor = _ctx(db_session, "doctor.a@metrogeneral.org")

    # inventory.read: Admin, Pharmacist, Doctor = Allow; Billing, Front Desk = Deny
    assert engine.authorize(admin, "inventory.read").allowed is True
    assert engine.authorize(pharmacist, "inventory.read").allowed is True
    assert engine.authorize(doctor, "inventory.read").allowed is True
    assert engine.authorize(billing, "inventory.read").allowed is False
    assert engine.authorize(frontdesk, "inventory.read").allowed is False

    # inventory.update: Admin, Pharmacist = Allow (max 500); others = Deny
    assert engine.authorize(admin, "inventory.update", requested_rows=500).allowed is True
    assert engine.authorize(admin, "inventory.update", requested_rows=501).allowed is False
    assert engine.authorize(pharmacist, "inventory.update", requested_rows=500).allowed is True
    assert engine.authorize(pharmacist, "inventory.update", requested_rows=501).allowed is False
    assert engine.authorize(doctor, "inventory.update", requested_rows=1).allowed is False
    assert engine.authorize(frontdesk, "inventory.update", requested_rows=1).allowed is False

    # inventory.delete: Admin only
    assert engine.authorize(admin, "inventory.delete").allowed is True
    assert engine.authorize(pharmacist, "inventory.delete").allowed is False

    # bills.read: Admin, Billing (hospital), Front Desk (own_only); Pharmacist, Doctor = Deny
    assert engine.authorize(admin, "bills.read").constraints.get("scope") == "hospital"
    assert engine.authorize(billing, "bills.read").constraints.get("scope") == "hospital"
    assert engine.authorize(frontdesk, "bills.read").constraints.get("scope") == "own_only"
    assert engine.authorize(pharmacist, "bills.read").allowed is False
    assert engine.authorize(doctor, "bills.read").allowed is False

    # bills.discount: Admin max 100%, Billing Manager max 10%
    assert engine.authorize(admin, "bills.discount", discount_pct=Decimal("20")).allowed is True
    assert engine.authorize(admin, "bills.discount", discount_pct=Decimal("100")).allowed is True
    assert engine.authorize(billing, "bills.discount", discount_pct=Decimal("10")).allowed is True
    assert engine.authorize(billing, "bills.discount", discount_pct=Decimal("20")).allowed is False
    assert engine.authorize(frontdesk, "bills.discount", discount_pct=Decimal("5")).allowed is False


def test_user_permission_override_does_not_affect_other_role_members(db_session: Session):
    engine = PermissionEngine(db_session)
    ravi = _ctx(db_session, "ravi.a@metrogeneral.org")
    priya = _ctx(db_session, "pharmacist.a@metrogeneral.org")
    inv_update_perm = db_session.scalar(
        select(Permission).where(Permission.permission_key == "inventory.update")
    )

    override = UserPermissionOverride(
        id=uuid.uuid4(),
        user_id=ravi.user_id,
        permission_id=inv_update_perm.id,
        effect="DENY",
    )
    db_session.add(override)
    db_session.flush()

    try:
        ravi_decision = engine.authorize(ravi, "inventory.update", requested_rows=1)
        priya_decision = engine.authorize(priya, "inventory.update", requested_rows=1)
        assert ravi_decision.allowed is False
        assert ravi_decision.source == "user_override_deny"
        assert priya_decision.allowed is True
    finally:
        db_session.rollback()


def test_access_management_safeguards(db_session: Session):
    engine = PermissionEngine(db_session)
    admin = _ctx(db_session, "admin.a@metrogeneral.org")
    billing = _ctx(db_session, "billing.a@metrogeneral.org")
    ravi = _ctx(db_session, "ravi.a@metrogeneral.org")

    # Admin cannot remove their own Admin role
    self_demote = engine.authorize(
        admin,
        "users.manage_access",
        target_user_id=admin.user_id,
        access_action="revoke_role",
        target_role_name="Admin",
    )
    assert self_demote.allowed is False
    assert self_demote.source == "safeguard_violation"

    # Billing Manager cannot promote themselves to Admin
    self_promote = engine.authorize(
        billing,
        "users.manage_access",
        target_user_id=billing.user_id,
        access_action="grant_role",
        target_role_name="Admin",
    )
    assert self_promote.allowed is False

    # Admin cannot grant a permission they do not possess (simulate Admin having DENY on inventory.delete)
    inv_del_perm = db_session.scalar(
        select(Permission).where(Permission.permission_key == "inventory.delete")
    )
    db_session.add(
        UserPermissionOverride(
            id=uuid.uuid4(),
            user_id=admin.user_id,
            permission_id=inv_del_perm.id,
            effect="DENY",
        )
    )
    db_session.flush()
    try:
        grant_missing = engine.authorize(
            admin,
            "users.manage_access",
            target_user_id=ravi.user_id,
            access_action="allow_permission",
            target_permission_key="inventory.delete",
        )
        assert grant_missing.allowed is False
        assert grant_missing.source == "safeguard_violation"
    finally:
        db_session.rollback()


def test_permissions_me_endpoint(client):
    auth = login_as(client, "billing.a@metrogeneral.org")
    resp = client.get(
        "/api/permissions/me", headers={"Authorization": auth["Authorization"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["roles"] == ["Billing Manager"]
    assert data["permissions"]["bills.discount"]["allowed"] is True
    assert data["permissions"]["bills.discount"]["constraints"]["max_discount_pct"] == 10
    assert data["permissions"]["inventory.read"]["allowed"] is False

