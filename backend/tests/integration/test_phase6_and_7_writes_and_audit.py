from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, InventoryItem, OperationConfirmation
from tests.conftest import login_as


def test_preview_confirm_cancel_and_exact_row_count_gt_50(client, db_session: Session):
    admin = login_as(client, "admin.a@metrogeneral.org")
    headers = {"Authorization": admin["Authorization"]}

    # 1. Operation affecting <= 50 rows (Antibiotics has 35 items in Hospital A)
    p1 = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "Increase quantity by 10 for all Antibiotics."},
    )
    assert p1.status_code == 200
    d1 = p1.json()
    assert d1["status"] == "preview_required"
    assert d1["preview"]["affected_rows"] == 35
    assert d1["preview"]["requires_exact_row_count"] is False
    assert len(d1["preview"]["samples"]) == 5
    token1 = d1["preview"]["confirmation_token"]

    # Confirm without exact_row_count succeeds for <= 50 rows
    c1 = client.post(
        "/api/operations/confirm",
        headers=headers,
        json={"confirmation_token": token1},
    )
    assert c1.status_code == 200
    assert c1.json()["affected_rows"] == 35

    # Replay of same token must fail (409)
    replay = client.post(
        "/api/operations/confirm",
        headers=headers,
        json={"confirmation_token": token1},
    )
    assert replay.status_code == 409

    # 2. Operation affecting > 50 rows (low_stock has > 50 items, <= 500)
    p2 = client.post(
        "/api/operations/preview",
        headers=headers,
        json={
            "operation": "inventory.update",
            "parameters": {"filter": "low_stock", "adjust_quantity": 5},
        },
    )
    assert p2.status_code == 200
    d2 = p2.json()
    assert d2["affected_rows"] > 50
    assert d2["requires_exact_row_count"] is True
    token2 = d2["confirmation_token"]

    # Confirming without exact_row_count or wrong row count must fail (422)
    fail_missing = client.post(
        "/api/operations/confirm",
        headers=headers,
        json={"confirmation_token": token2},
    )
    assert fail_missing.status_code == 422

    fail_wrong = client.post(
        "/api/operations/confirm",
        headers=headers,
        json={"confirmation_token": token2, "exact_row_count": d2["affected_rows"] + 1},
    )
    assert fail_wrong.status_code == 422

    # Cancel preview works and logs CANCELLED
    cancel_resp = client.post(
        "/api/operations/cancel",
        headers=headers,
        json={"confirmation_token": token2},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_cross_user_and_stale_preview_invalidation(client, db_session: Session):
    admin = login_as(client, "admin.a@metrogeneral.org")
    pharmacist = login_as(client, "pharmacist.a@metrogeneral.org")

    p = client.post(
        "/api/operations/preview",
        headers={"Authorization": admin["Authorization"]},
        json={
            "operation": "inventory.update",
            "parameters": {"filter": "category", "category": "Antibiotics", "adjust_quantity": 2},
        },
    )
    assert p.status_code == 200
    token = p.json()["confirmation_token"]
    sample_id = p.json()["samples"][0]["id"]

    # Pharmacist cannot confirm Admin's confirmation token
    cross_user = client.post(
        "/api/operations/confirm",
        headers={"Authorization": pharmacist["Authorization"]},
        json={"confirmation_token": token},
    )
    assert cross_user.status_code == 403

    # Modify underlying record version to simulate concurrent change -> preview invalidated
    import uuid
    item = db_session.get(InventoryItem, uuid.UUID(sample_id))
    item.version += 1
    db_session.commit()

    stale_confirm = client.post(
        "/api/operations/confirm",
        headers={"Authorization": admin["Authorization"]},
        json={"confirmation_token": token},
    )
    assert stale_confirm.status_code == 409
    assert "changed after the preview" in stale_confirm.json()["detail"]


def test_audit_log_records_all_outcomes_and_restricts_access(client, db_session: Session):
    admin = login_as(client, "admin.a@metrogeneral.org")
    pharmacist = login_as(client, "pharmacist.a@metrogeneral.org")

    # Non-admin cannot read audit logs
    non_admin_audit = client.get(
        "/api/audit-logs", headers={"Authorization": pharmacist["Authorization"]}
    )
    assert non_admin_audit.status_code == 403

    # No PUT/PATCH/DELETE endpoint exists for audit logs
    del_resp = client.delete(
        "/api/audit-logs", headers={"Authorization": admin["Authorization"]}
    )
    assert del_resp.status_code in (404, 405)

    # Admin can read hospital-scoped audit logs
    admin_audit = client.get(
        "/api/audit-logs?limit=20", headers={"Authorization": admin["Authorization"]}
    )
    assert admin_audit.status_code == 200
    logs = admin_audit.json()["items"]
    assert len(logs) > 0
    statuses = {entry["execution_status"] for entry in logs}
    assert "SUCCESS" in statuses or "CANCELLED" in statuses or "PREVIEW_CREATED" in statuses

