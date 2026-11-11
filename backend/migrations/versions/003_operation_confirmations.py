"""Add operation_confirmations table for safe write confirmation tokens

Revision ID: 003_operation_confirmations
Revises: 002_rls_policies
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_operation_confirmations"
down_revision: Union[str, None] = "002_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

jsonb_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "operation_confirmations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "hospital_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("parameters", jsonb_type, nullable=False),
        sa.Column("raw_user_query", sa.Text(), nullable=False),
        sa.Column("expected_row_count", sa.Integer(), nullable=False),
        sa.Column("requires_exact_row_count", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("preview_summary", jsonb_type, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'INVALIDATED', 'FAILED')",
            name="ck_op_confirm_status_valid",
        ),
        sa.CheckConstraint("expected_row_count >= 0", name="ck_op_confirm_rows_nonneg"),
    )
    op.create_index(
        "ix_op_confirm_hospital_user", "operation_confirmations", ["hospital_id", "user_id"]
    )
    op.create_index("ix_op_confirm_token_hash", "operation_confirmations", ["token_hash"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE operation_confirmations ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY operation_confirmations_tenant_isolation ON operation_confirmations
            USING (
                app_rls_bypass_enabled()
                OR hospital_id = app_current_hospital_id()
            )
            WITH CHECK (
                app_rls_bypass_enabled()
                OR hospital_id = app_current_hospital_id()
            );
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS operation_confirmations_tenant_isolation ON operation_confirmations;"
        )
        op.execute("ALTER TABLE operation_confirmations DISABLE ROW LEVEL SECURITY;")

    op.drop_table("operation_confirmations")

