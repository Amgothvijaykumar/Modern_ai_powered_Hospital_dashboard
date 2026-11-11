from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.registry.operation_registry import OPERATION_REGISTRY, get_operation_spec
from app.schemas.operations import BillsDiscountParams, InventoryReadParams
from app.utils.dates import IST, resolve_date_range
from app.utils.money import calculate_bill_discount
from tests.conftest import login_as


def test_decimal_discount_calculation_and_rounding():
    # 100.05 * 10% = 10.005 -> rounds HALF_UP to 10.01
    discount, net = calculate_bill_discount(Decimal("100.05"), Decimal("10"))
    assert discount == Decimal("10.01")
    assert net == Decimal("90.04")
    assert isinstance(discount, Decimal)
    assert isinstance(net, Decimal)

    # 20% discount on 1234.50
    discount2, net2 = calculate_bill_discount(Decimal("1234.50"), Decimal("20"))
    assert discount2 == Decimal("246.90")
    assert net2 == Decimal("987.60")

    with pytest.raises(ValueError):
        calculate_bill_discount(Decimal("100.00"), Decimal("101"))


def test_asia_kolkata_date_range_resolution():
    # 2026-11-11 16:00 IST -> last month is Oct 1..Oct 31 IST
    ref_utc = datetime(2026, 11, 11, 10, 30, tzinfo=timezone.utc)
    r = resolve_date_range("last_month", reference_now_utc=ref_utc)
    assert r.start_date_ist == date(2026, 10, 1)
    assert r.end_date_ist == date(2026, 10, 31)
    assert r.timezone == "Asia/Kolkata"
    assert r.start_utc == datetime(2026, 10, 1, 0, 0, tzinfo=IST).astimezone(timezone.utc)
    assert r.end_utc_exclusive == datetime(2026, 11, 1, 0, 0, tzinfo=IST).astimezone(timezone.utc)

    # January -> December of previous year
    jan_utc = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    r_jan = resolve_date_range("last_month", reference_now_utc=jan_utc)
    assert r_jan.start_date_ist == date(2025, 12, 1)
    assert r_jan.end_date_ist == date(2025, 12, 31)


def test_strict_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        InventoryReadParams(filter="low_stock", sql="DROP TABLE users;")

    with pytest.raises(ValidationError):
        BillsDiscountParams(discount_percentage=Decimal("150"), period="last_month")


def test_operation_registry_contains_all_core_operations():
    expected = {
        "inventory.read",
        "inventory.update",
        "inventory.delete",
        "bills.read",
        "bills.discount",
        "bills.update_status",
        "users.read",
        "users.manage_access",
    }
    assert expected.issubset(set(OPERATION_REGISTRY.keys()))
    assert get_operation_spec("unknown.op") is None


def test_read_endpoints_and_front_desk_own_only_scope(client):
    # Front Desk A can only see their own bills, not Front Desk 2's bills
    fd1 = login_as(client, "frontdesk.a@metrogeneral.org")
    fd2 = login_as(client, "frontdesk2.a@metrogeneral.org")
    billing = login_as(client, "billing.a@metrogeneral.org")

    r1 = client.get("/api/bills?limit=500", headers={"Authorization": fd1["Authorization"]})
    r2 = client.get("/api/bills?limit=500", headers={"Authorization": fd2["Authorization"]})
    rb = client.get("/api/bills?limit=500", headers={"Authorization": billing["Authorization"]})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert rb.status_code == 200

    d1, d2, db_data = r1.json(), r2.json(), rb.json()
    assert d1["scope"] == "own_only"
    assert d2["scope"] == "own_only"
    assert db_data["scope"] == "hospital"

    assert all(b["created_by_user_id"] == fd1["user"]["id"] for b in d1["bills"])
    assert all(b["created_by_user_id"] == fd2["user"]["id"] for b in d2["bills"])
    assert d1["total_count"] + d2["total_count"] < db_data["total_count"]

    # Front Desk denied inventory & users
    assert (
        client.get("/api/inventory", headers={"Authorization": fd1["Authorization"]}).status_code
        == 403
    )
    assert (
        client.get("/api/users", headers={"Authorization": fd1["Authorization"]}).status_code == 403
    )

