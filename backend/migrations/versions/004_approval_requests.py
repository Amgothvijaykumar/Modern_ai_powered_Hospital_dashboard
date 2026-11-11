"""Add approval_requests table for privileged escalation routing

Revision ID: 004_approval_requests
Revises: 003_operation_confirmations
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_approval_requests"
down_revision: Union[str, None] = "003_operation_confirmations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

jsonb_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "hospital_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("parameters", jsonb_type, nullable=False),
        sa.Column("raw_user_query", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "reviewed_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "confirmation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("operation_confirmations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'CANCELLED')",
            name="ck_approval_req_status_valid",
        ),
    )
    op.create_index(
        "ix_approval_req_hospital_status",
        "approval_requests",
        ["hospital_id", "status", "created_at"],
    )
    op.create_index("ix_approval_req_requester", "approval_requests", ["requester_user_id"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY approval_requests_tenant_isolation ON approval_requests
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
        op.execute("DROP POLICY IF EXISTS approval_requests_tenant_isolation ON approval_requests;")
    op.drop_index("ix_approval_req_requester", table_name="approval_requests")
    op.drop_index("ix_approval_req_hospital_status", table_name="approval_requests")
    op.drop_table("approval_requests")

