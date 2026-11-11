from datetime import date
from decimal import Decimal
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventoryReadParams(StrictSchema):
    filter: Literal[
        "all",
        "low_stock",
        "expiring_soon",
        "out_of_stock",
        "category",
        "search",
        "summary",
    ] = "all"
    category: Optional[str] = Field(default=None, max_length=100)
    search: Optional[str] = Field(default=None, max_length=200)
    expiring_days: int = Field(default=30, ge=1, le=365)
    item_id: Optional[uuid.UUID] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class InventoryUpdateParams(StrictSchema):
    filter: Optional[Literal["all", "low_stock", "expiring_soon", "category", "search"]] = None
    item_id: Optional[uuid.UUID] = None
    batch_number: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    search: Optional[str] = Field(default=None, max_length=200)
    expiring_days: int = Field(default=30, ge=1, le=365)

    set_quantity: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    adjust_quantity: Optional[int] = Field(default=None, ge=-100_000, le=100_000)
    set_minimum_quantity: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    set_unit_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("1000000"))

    @model_validator(mode="after")
    def validate_update_shape(self) -> "InventoryUpdateParams":
        has_target = any(
            v is not None
            for v in (self.filter, self.item_id, self.batch_number, self.category, self.search)
        )
        if not has_target:
            raise ValueError("Inventory update requires a target filter, item_id, batch_number, category, or search")

        has_change = any(
            v is not None
            for v in (
                self.set_quantity,
                self.adjust_quantity,
                self.set_minimum_quantity,
                self.set_unit_price,
            )
        )
        if not has_change:
            raise ValueError("Inventory update requires at least one field to modify")

        if self.set_quantity is not None and self.adjust_quantity is not None:
            raise ValueError("Specify either set_quantity or adjust_quantity, not both")
        return self


class InventoryDeleteParams(StrictSchema):
    item_id: Optional[uuid.UUID] = None
    batch_number: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    filter: Optional[Literal["expired", "out_of_stock"]] = None

    @model_validator(mode="after")
    def validate_delete_target(self) -> "InventoryDeleteParams":
        if not any(v is not None for v in (self.item_id, self.batch_number, self.category, self.filter)):
            raise ValueError("Inventory deletion requires an explicit target selector")
        return self


PeriodLiteral = Literal[
    "last_month",
    "this_month",
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "today",
    "yesterday",
    "custom",
]

BillStatusLiteral = Literal["PENDING", "PAID", "PARTIALLY_PAID", "CANCELLED", "REFUNDED"]


class BillsReadParams(StrictSchema):
    filter: Literal[
        "all",
        "pending",
        "paid",
        "partially_paid",
        "cancelled",
        "refunded",
        "date_range",
        "summary",
    ] = "all"
    period: Optional[PeriodLiteral] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[BillStatusLiteral] = None
    patient_search: Optional[str] = Field(default=None, max_length=200)
    bill_id: Optional[uuid.UUID] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class BillsDiscountParams(StrictSchema):
    discount_percentage: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    period: Optional[PeriodLiteral] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status_filter: Literal["ALL_ELIGIBLE", "PENDING", "PARTIALLY_PAID"] = "ALL_ELIGIBLE"
    bill_id: Optional[uuid.UUID] = None
    patient_search: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_scope(self) -> "BillsDiscountParams":
        if not any(v is not None for v in (self.period, self.start_date, self.bill_id, self.patient_search)):
            raise ValueError("Discount operation requires a period, date range, bill_id, or patient_search")
        return self


class BillsUpdateStatusParams(StrictSchema):
    new_status: BillStatusLiteral
    bill_id: Optional[uuid.UUID] = None
    patient_search: Optional[str] = Field(default=None, max_length=200)
    current_status: Optional[BillStatusLiteral] = None
    period: Optional[PeriodLiteral] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_target(self) -> "BillsUpdateStatusParams":
        if not any(
            v is not None
            for v in (self.bill_id, self.patient_search, self.current_status, self.period, self.start_date)
        ):
            raise ValueError("Bill status update requires a target bill_id, patient_search, status, or period")
        return self


RoleNameLiteral = Literal["Admin", "Billing Manager", "Pharmacist", "Front Desk", "Doctor"]
PermissionKeyLiteral = Literal[
    "inventory.read",
    "inventory.update",
    "inventory.delete",
    "bills.read",
    "bills.discount",
    "bills.update_status",
    "users.read",
    "users.manage_access",
]


class UsersReadParams(StrictSchema):
    search: Optional[str] = Field(default=None, max_length=200)
    role: Optional[RoleNameLiteral] = None
    include_permissions: bool = True


class UsersManageAccessParams(StrictSchema):
    action: Literal[
        "deny_permission",
        "allow_permission",
        "remove_override",
        "grant_role",
        "revoke_role",
    ]
    target_user_id: Optional[uuid.UUID] = None
    target_user_name: Optional[str] = Field(default=None, max_length=200)
    target_user_email: Optional[str] = Field(default=None, max_length=255)
    permission_key: Optional[PermissionKeyLiteral] = None
    role_name: Optional[RoleNameLiteral] = None

    @model_validator(mode="after")
    def validate_access_request(self) -> "UsersManageAccessParams":
        if not any(v is not None for v in (self.target_user_id, self.target_user_name, self.target_user_email)):
            raise ValueError("Target user identifier (id, name, or email) is required")
        if self.action in ("deny_permission", "allow_permission", "remove_override") and not self.permission_key:
            raise ValueError("permission_key is required for permission override actions")
        if self.action in ("grant_role", "revoke_role") and not self.role_name:
            raise ValueError("role_name is required for role assignment actions")
        return self


class UndoOperationParams(StrictSchema):
    audit_log_id: Optional[uuid.UUID] = None


class ApprovalsReadParams(StrictSchema):
    status: Literal["PENDING", "ALL", "EXECUTED", "REJECTED"] = "PENDING"
    limit: int = Field(default=20, ge=1, le=100)


class ApprovalsResolveParams(StrictSchema):
    action: Literal["approve", "reject"]
    request_id: Optional[str] = Field(default=None, max_length=64)
    requester_name: Optional[str] = Field(default=None, max_length=200)
    review_note: Optional[str] = Field(default=None, max_length=500)

