from decimal import Decimal
import uuid

from sqlalchemy import select

from app.models import ApprovalRequest, AuditLog, Bill, InventoryItem
from tests.conftest import login_as


def test_undo_happy_path_and_conflict_when_row_touched_since(client, db_session):
    pharmacist = login_as(client, "pharmacist.a@metrogeneral.org")
    admin = login_as(client, "admin.a@metrogeneral.org")
    doctor = login_as(client, "doctor.a@metrogeneral.org")

    before_qty = {
        str(row.id): (row.quantity, row.version)
        for row in db_session.scalars(
            select(InventoryItem).where(InventoryItem.category == "Antibiotics")
        ).all()
        if str(row.hospital_id) == pharmacist["user"]["hospital_id"]
    }
    assert len(before_qty) > 0

    # 1. Pharmacist updates Antibiotics quantity +10
    p1 = client.post(
        "/api/agent/chat",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"message": "Increase quantity by 10 for all Antibiotics."},
    )
    assert p1.status_code == 200
    b1 = p1.json()
    assert b1["status"] == "preview_required"

    c1 = client.post(
        "/api/operations/confirm",
        headers={"Authorization": pharmacist["Authorization"]},
        json={
            "confirmation_token": b1["preview"]["confirmation_token"],
            "exact_row_count": b1["preview"]["affected_rows"],
        },
    )
    assert c1.status_code == 200

    db_session.expire_all()
    for item_id_str, (orig_qty, orig_ver) in before_qty.items():
        row = db_session.scalar(
            select(InventoryItem).where(InventoryItem.id == uuid.UUID(item_id_str))
        )
        assert row.quantity == orig_qty + 10
        assert row.version == orig_ver + 1

    # 2. Doctor (no write perms) cannot undo
    doc_undo = client.post(
        "/api/agent/chat",
        headers={"Authorization": doctor["Authorization"]},
        json={"message": "Undo my last change."},
    )
    assert doc_undo.status_code == 200
    assert doc_undo.json()["status"] == "denied"

    # 3. Pharmacist runs Undo -> preview -> confirm -> restores exact before-snapshot
    u1 = client.post(
        "/api/agent/chat",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"message": "Undo my last change."},
    )
    assert u1.status_code == 200
    ub1 = u1.json()
    assert ub1["status"] == "preview_required"
    assert ub1["operation"] == "operations.undo"
    assert ub1["preview"]["affected_rows"] == len(before_qty)

    uc1 = client.post(
        "/api/operations/confirm",
        headers={"Authorization": pharmacist["Authorization"]},
        json={
            "confirmation_token": ub1["preview"]["confirmation_token"],
            "exact_row_count": ub1["preview"]["affected_rows"],
        },
    )
    assert uc1.status_code == 200
    assert uc1.json()["operation"] == "operations.undo"

    db_session.expire_all()
    for item_id_str, (orig_qty, orig_ver) in before_qty.items():
        row = db_session.scalar(
            select(InventoryItem).where(InventoryItem.id == uuid.UUID(item_id_str))
        )
        assert row.quantity == orig_qty
        assert row.version == orig_ver + 2

    # 4. Second immediate Undo refuses/reports already undone
    u_again = client.post(
        "/api/agent/chat",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"message": "Undo my last change."},
    )
    assert u_again.status_code == 200
    assert u_again.json()["status"] == "not_found"
    assert "already been undone" in u_again.json()["message"].lower()

    # 5. Conflict detection: Pharmacist updates Antibiotics again, then Admin modifies one batch since
    p2 = client.post(
        "/api/agent/chat",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"message": "Increase quantity by 5 for all Antibiotics."},
    ).json()
    client.post(
        "/api/operations/confirm",
        headers={"Authorization": pharmacist["Authorization"]},
        json={
            "confirmation_token": p2["preview"]["confirmation_token"],
            "exact_row_count": p2["preview"]["affected_rows"],
        },
    ).raise_for_status()

    sample_item = db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.category == "Antibiotics",
            InventoryItem.hospital_id == uuid.UUID(pharmacist["user"]["hospital_id"]),
        )
    )
    admin_prev = client.post(
        "/api/operations/preview",
        headers={"Authorization": admin["Authorization"]},
        json={
            "operation": "inventory.update",
            "parameters": {"item_id": str(sample_item.id), "adjust_quantity": 1},
            "raw_user_query": "Admin touches one item",
        },
    ).json()
    client.post(
        "/api/operations/confirm",
        headers={"Authorization": admin["Authorization"]},
        json={"confirmation_token": admin_prev["confirmation_token"]},
    ).raise_for_status()

    # Pharmacist tries to undo now -> MUST be denied because Admin touched that row since!
    u_conflict = client.post(
        "/api/agent/chat",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"message": "Undo my last change."},
    )
    assert u_conflict.status_code == 200
    assert u_conflict.json()["status"] == "denied"
    assert "modified" in u_conflict.json()["message"].lower()


def test_approval_routing_workflow_and_isolation(client, db_session):
    billing_a = login_as(client, "billing.a@metrogeneral.org")
    admin_a = login_as(client, "admin.a@metrogeneral.org")
    admin_b = login_as(client, "admin.b@citycare.org")

    # 1. Billing Manager requests 20% discount -> denied with 10% ceiling + creates pending ApprovalRequest
    bm_resp = client.post(
        "/api/agent/chat",
        headers={"Authorization": billing_a["Authorization"]},
        json={"message": "Apply a 20% discount to last month's bills."},
    )
    assert bm_resp.status_code == 200
    bm_body = bm_resp.json()
    assert bm_body["status"] == "denied"
    assert "10" in bm_body["message"]
    approval_req = bm_body["data"]["approval_request"]
    short_id = approval_req["short_id"]
    assert approval_req["status"] == "PENDING"

    # 2. Billing Manager cannot approve their own escalated request
    bm_approve = client.post(
        "/api/agent/chat",
        headers={"Authorization": billing_a["Authorization"]},
        json={"message": f"Approve request #{short_id}"},
    )
    assert bm_approve.status_code == 200
    assert bm_approve.json()["status"] == "denied"

    # 3. Hospital B Admin cannot list or approve Hospital A's pending request
    b_list = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin_b["Authorization"]},
        json={"message": "Show pending approval requests."},
    )
    assert b_list.status_code == 200
    assert b_list.json()["data"]["total_count"] == 0

    b_approve = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin_b["Authorization"]},
        json={"message": f"Approve request #{short_id}"},
    )
    assert b_approve.status_code == 200
    assert b_approve.json()["status"] == "not_found"

    # 4. Hospital A Admin sees the pending request and approves it in chat -> dry-run preview -> execute
    a_list = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin_a["Authorization"]},
        json={"message": "Show pending approval requests."},
    )
    assert a_list.status_code == 200
    assert any(r["short_id"] == short_id for r in a_list.json()["data"]["approvals"])

    a_approve = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin_a["Authorization"]},
        json={"message": f"Approve request #{short_id}"},
    )
    assert a_approve.status_code == 200
    app_body = a_approve.json()
    assert app_body["status"] == "preview_required"
    assert app_body["operation"] == "approvals.resolve"
    assert app_body["preview"]["requires_exact_row_count"] is True
    affected_bills = app_body["preview"]["affected_rows"]
    assert affected_bills > 50
    assert Decimal(app_body["preview"]["financial_impact"]["total_discount_amount"]) > Decimal("0")

    confirm_app = client.post(
        "/api/operations/confirm",
        headers={"Authorization": admin_a["Authorization"]},
        json={
            "confirmation_token": app_body["preview"]["confirmation_token"],
            "exact_row_count": affected_bills,
        },
    )
    assert confirm_app.status_code == 200
    assert confirm_app.json()["affected_rows"] == affected_bills

    db_session.expire_all()
    db_req = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(approval_req["id"]))
    )
    assert db_req.status == "EXECUTED"
    assert str(db_req.reviewed_by_user_id) == admin_a["user"]["id"]

    # 5. Admin can undo the approved discount if nobody touched bills since!
    undo_prev = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin_a["Authorization"]},
        json={"message": "Undo my last change."},
    ).json()
    assert undo_prev["status"] == "preview_required"
    assert undo_prev["preview"]["affected_rows"] == affected_bills
    undo_conf = client.post(
        "/api/operations/confirm",
        headers={"Authorization": admin_a["Authorization"]},
        json={
            "confirmation_token": undo_prev["preview"]["confirmation_token"],
            "exact_row_count": affected_bills,
        },
    )
    assert undo_conf.status_code == 200


def test_telugu_and_hinglish_queries_match_english_behavior(client):
    admin = login_as(client, "admin.a@metrogeneral.org")
    billing = login_as(client, "billing.a@metrogeneral.org")
    pharmacist = login_as(client, "pharmacist.a@metrogeneral.org")

    # 1. Telugu/Hinglish 20% discount as Admin -> identical preview to English
    en_resp = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin["Authorization"]},
        json={"message": "Give 20% discount on all bills from last month"},
    ).json()
    te_resp = client.post(
        "/api/agent/chat",
        headers={"Authorization": admin["Authorization"]},
        json={"message": "Last month bills ki 20% discount ivvu"},
    ).json()
    assert te_resp["status"] == "preview_required"
    assert te_resp["operation"] == "bills.discount"
    assert te_resp["preview"]["affected_rows"] == en_resp["preview"]["affected_rows"]
    assert te_resp["preview"]["resolved_date_range"] == en_resp["preview"]["resolved_date_range"]
    assert te_resp["preview"]["financial_impact"] == en_resp["preview"]["financial_impact"]

    # 2. Telugu/Hinglish 20% discount as Billing Manager -> denied + pending approval created
    te_bm = client.post(
        "/api/agent/chat",
        headers={"Authorization": billing["Authorization"]},
        json={"message": "Last month bills ki 20% discount ivvu"},
    ).json()
    assert te_bm["status"] == "denied"
    assert "10" in te_bm["message"]
    assert te_bm["data"]["approval_request"]["status"] == "PENDING"

    # 3. Telugu low stock query as Pharmacist
    te_inv = client.post(
        "/api/agent/chat",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"message": "Takkuva stock medicines chupinchu"},
    ).json()
    assert te_inv["status"] == "completed"
    assert te_inv["operation"] == "inventory.read"
    assert te_inv["data"]["total_count"] > 0


def test_demo_role_switcher_all_7_accounts(client):
    expected_profiles = [
        ("admin.a@metrogeneral.org", "Metro General Hospital", "Admin", 8, True, True),
        ("billing.a@metrogeneral.org", "Metro General Hospital", "Billing Manager", 3, False, True),
        ("pharmacist.a@metrogeneral.org", "Metro General Hospital", "Pharmacist", 2, True, False),
        ("ravi.a@metrogeneral.org", "Metro General Hospital", "Pharmacist", 2, True, False),
        ("frontdesk.a@metrogeneral.org", "Metro General Hospital", "Front Desk", 1, False, True),
        ("doctor.a@metrogeneral.org", "Metro General Hospital", "Doctor", 1, True, False),
        ("admin.b@citycare.org", "City Care Medical Center", "Admin", 8, True, True),
    ]

    for email, hosp_name, role_name, expected_allowed, can_inv, can_bills in expected_profiles:
        session = login_as(client, email)
        headers = {"Authorization": session["Authorization"]}
        assert session["user"]["hospital_name"] == hosp_name
        assert role_name in session["user"]["roles"]

        perms = client.get("/api/permissions/me", headers=headers).json()["permissions"]
        allowed_count = sum(1 for p in perms.values() if p["allowed"])
        assert allowed_count == expected_allowed

        inv_resp = client.get("/api/inventory", headers=headers, params={"filter": "summary"})
        assert inv_resp.status_code == (200 if can_inv else 403)

        bills_resp = client.get("/api/bills", headers=headers, params={"filter": "summary"})
        assert bills_resp.status_code == (200 if can_bills else 403)
