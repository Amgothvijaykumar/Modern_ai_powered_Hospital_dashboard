from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel

from app.schemas.operations import (
    ApprovalsReadParams,
    ApprovalsResolveParams,
    BillsDiscountParams,
    BillsReadParams,
    BillsUpdateStatusParams,
    InventoryDeleteParams,
    InventoryReadParams,
    InventoryUpdateParams,
    UndoOperationParams,
    UsersManageAccessParams,
    UsersReadParams,
)
from app.services.operations.approval_ops import (
    execute_resolve_approval,
    preview_resolve_approval,
    read_approvals,
)
from app.services.operations.billing_ops import (
    execute_apply_discount,
    execute_update_bill_status,
    preview_apply_discount,
    preview_update_bill_status,
    read_bills,
)
from app.services.operations.inventory_ops import (
    execute_delete_inventory,
    execute_update_inventory,
    preview_delete_inventory,
    preview_update_inventory,
    read_inventory,
)
from app.services.operations.undo_ops import (
    execute_undo_operation,
    preview_undo_operation,
)
from app.services.operations.user_ops import (
    execute_manage_user_access,
    preview_manage_user_access,
    read_users,
)


@dataclass(frozen=True)
class OperationSpec:
    operation_key: str
    category: str
    description: str
    required_permission: str
    is_write: bool
    schema_cls: Type[BaseModel]
    read_handler: Optional[Callable[..., Dict[str, Any]]] = None
    preview_handler: Optional[Callable[..., Any]] = None
    execute_handler: Optional[Callable[..., Any]] = None


OPERATION_REGISTRY: Dict[str, OperationSpec] = {
    "inventory.read": OperationSpec(
        operation_key="inventory.read",
        category="inventory",
        description="Read inventory items, low stock, expiring medicines, or summary metrics",
        required_permission="inventory.read",
        is_write=False,
        schema_cls=InventoryReadParams,
        read_handler=read_inventory,
    ),
    "inventory.update": OperationSpec(
        operation_key="inventory.update",
        category="inventory",
        description="Update inventory quantities, minimum thresholds, or unit prices (max 500 rows)",
        required_permission="inventory.update",
        is_write=True,
        schema_cls=InventoryUpdateParams,
        preview_handler=preview_update_inventory,
        execute_handler=execute_update_inventory,
    ),
    "inventory.delete": OperationSpec(
        operation_key="inventory.delete",
        category="inventory",
        description="Delete expired, out-of-stock, or specific inventory items (Admin only)",
        required_permission="inventory.delete",
        is_write=True,
        schema_cls=InventoryDeleteParams,
        preview_handler=preview_delete_inventory,
        execute_handler=execute_delete_inventory,
    ),
    "bills.read": OperationSpec(
        operation_key="bills.read",
        category="billing",
        description="Read hospital bills, pending bills, date-range bills, or billing summaries",
        required_permission="bills.read",
        is_write=False,
        schema_cls=BillsReadParams,
        read_handler=read_bills,
    ),
    "bills.discount": OperationSpec(
        operation_key="bills.discount",
        category="billing",
        description="Apply percentage discounts to eligible hospital bills",
        required_permission="bills.discount",
        is_write=True,
        schema_cls=BillsDiscountParams,
        preview_handler=preview_apply_discount,
        execute_handler=execute_apply_discount,
    ),
    "bills.update_status": OperationSpec(
        operation_key="bills.update_status",
        category="billing",
        description="Update bill payment or lifecycle status",
        required_permission="bills.update_status",
        is_write=True,
        schema_cls=BillsUpdateStatusParams,
        preview_handler=preview_update_bill_status,
        execute_handler=execute_update_bill_status,
    ),
    "users.read": OperationSpec(
        operation_key="users.read",
        category="user_management",
        description="List hospital employees, roles, and effective permissions",
        required_permission="users.read",
        is_write=False,
        schema_cls=UsersReadParams,
        read_handler=read_users,
    ),
    "users.manage_access": OperationSpec(
        operation_key="users.manage_access",
        category="user_management",
        description="Grant or revoke user permissions or roles within the hospital",
        required_permission="users.manage_access",
        is_write=True,
        schema_cls=UsersManageAccessParams,
        preview_handler=preview_manage_user_access,
        execute_handler=execute_manage_user_access,
    ),
    "operations.undo": OperationSpec(
        operation_key="operations.undo",
        category="operations",
        description="Undo the caller's last completed write change if no rows were modified since",
        required_permission="operations.undo",
        is_write=True,
        schema_cls=UndoOperationParams,
        preview_handler=preview_undo_operation,
        execute_handler=execute_undo_operation,
    ),
    "approvals.read": OperationSpec(
        operation_key="approvals.read",
        category="approvals",
        description="List pending or resolved escalated approval requests in the hospital",
        required_permission="approvals.read",
        is_write=False,
        schema_cls=ApprovalsReadParams,
        read_handler=read_approvals,
    ),
    "approvals.resolve": OperationSpec(
        operation_key="approvals.resolve",
        category="approvals",
        description="Approve or reject an escalated pending approval request (Admin only)",
        required_permission="approvals.resolve",
        is_write=True,
        schema_cls=ApprovalsResolveParams,
        preview_handler=preview_resolve_approval,
        execute_handler=execute_resolve_approval,
    ),
}


def get_operation_spec(operation_key: str) -> Optional[OperationSpec]:
    return OPERATION_REGISTRY.get(operation_key)

