"""PostgreSQL Row Level Security (RLS) policies and audit immutability

Revision ID: 002_rls_policies
Revises: 001_initial_schema
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_rls_policies"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_hospital_id() RETURNS uuid AS $$
        DECLARE
            setting_val text;
        BEGIN
            setting_val := NULLIF(current_setting('app.current_hospital_id', true), '');
            IF setting_val IS NOT NULL THEN
                RETURN setting_val::uuid;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_rls_bypass_enabled() RETURNS boolean AS $$
        BEGIN
            RETURN COALESCE(current_setting('app.rls_bypass', true), 'false') = 'true';
        END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    # Fail-closed tenant isolation on business tables
    for table_name in ["inventory_items", "bills", "audit_log"]:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation ON {table_name}
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

    # Users table allows lookup during auth resolution when app_current_hospital_id is not yet set,
    # or strict tenant isolation once app.current_hospital_id is bound.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY users_tenant_isolation ON users
        USING (
            app_rls_bypass_enabled()
            OR app_current_hospital_id() IS NULL
            OR hospital_id = app_current_hospital_id()
        )
        WITH CHECK (
            app_rls_bypass_enabled()
            OR hospital_id = app_current_hospital_id()
        );
        """
    )

    op.execute("ALTER TABLE hospitals ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY hospitals_tenant_isolation ON hospitals
        USING (
            app_rls_bypass_enabled()
            OR app_current_hospital_id() IS NULL
            OR id = app_current_hospital_id()
        );
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log records are append-only and cannot be modified or deleted';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation();")

    op.execute("DROP POLICY IF EXISTS hospitals_tenant_isolation ON hospitals;")
    op.execute("ALTER TABLE hospitals DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS users_tenant_isolation ON users;")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")

    for table_name in ["inventory_items", "bills", "audit_log"]:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name};")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP FUNCTION IF EXISTS app_rls_bypass_enabled();")
    op.execute("DROP FUNCTION IF EXISTS app_current_hospital_id();")
