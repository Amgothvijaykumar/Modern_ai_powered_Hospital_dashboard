"""Initial multi-tenant hospital operations schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

jsonb_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "hospitals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("permission_key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "hospital_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("auth_user_id", sa.Uuid(as_uuid=True), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_hospital_id", "users", ["hospital_id"])
    op.create_index("ix_users_auth_user_id", "users", ["auth_user_id"])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "role_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("constraints", jsonb_type, nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_perm"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])

    op.create_table(
        "user_permission_overrides",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effect", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "permission_id", name="uq_user_perm_override_user_perm"),
        sa.CheckConstraint("effect IN ('ALLOW', 'DENY')", name="ck_user_perm_override_effect"),
    )
    op.create_index(
        "ix_user_permission_overrides_user_id", "user_permission_overrides", ["user_id"]
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "hospital_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("minimum_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("batch_number", sa.String(length=100), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("hospital_id", "batch_number", name="uq_inventory_hospital_batch"),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonneg"),
        sa.CheckConstraint("minimum_quantity >= 0", name="ck_inventory_min_qty_nonneg"),
        sa.CheckConstraint("unit_price >= 0", name="ck_inventory_unit_price_nonneg"),
        sa.CheckConstraint("version >= 1", name="ck_inventory_version_pos"),
    )
    op.create_index("ix_inventory_hospital_id", "inventory_items", ["hospital_id"])
    op.create_index("ix_inventory_hospital_expiry", "inventory_items", ["hospital_id", "expiry_date"])
    op.create_index("ix_inventory_hospital_category", "inventory_items", ["hospital_id", "category"])

    op.create_table(
        "bills",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "hospital_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("patient_name", sa.String(length=200), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("gross_amount >= 0", name="ck_bills_gross_nonneg"),
        sa.CheckConstraint("discount_amount >= 0", name="ck_bills_discount_nonneg"),
        sa.CheckConstraint("net_amount >= 0", name="ck_bills_net_nonneg"),
        sa.CheckConstraint("discount_amount <= gross_amount", name="ck_bills_discount_le_gross"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'PARTIALLY_PAID', 'CANCELLED', 'REFUNDED')",
            name="ck_bills_status_valid",
        ),
        sa.CheckConstraint("version >= 1", name="ck_bills_version_pos"),
    )
    op.create_index("ix_bills_hospital_id", "bills", ["hospital_id"])
    op.create_index("ix_bills_hospital_created_at", "bills", ["hospital_id", "created_at"])
    op.create_index("ix_bills_hospital_status", "bills", ["hospital_id", "status"])
    op.create_index("ix_bills_hospital_creator", "bills", ["hospital_id", "created_by_user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "hospital_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("raw_user_query", sa.Text(), nullable=False),
        sa.Column("parsed_intent", jsonb_type, nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("authorization_result", sa.String(length=50), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False),
        sa.Column("affected_rows", sa.Integer(), nullable=True),
        sa.Column("execution_status", sa.String(length=50), nullable=False),
        sa.Column("before_data", jsonb_type, nullable=True),
        sa.Column("after_data", jsonb_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_hospital_created_at", "audit_log", ["hospital_id", "created_at"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_operation", "audit_log", ["operation"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("bills")
    op.drop_table("inventory_items")
    op.drop_table("user_permission_overrides")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("users")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("hospitals")

