"""store invalid imported rows as transaction data

Revision ID: 6a2d9f1c8b47
Revises: 1f8c4e7b2a63
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6a2d9f1c8b47"
down_revision: Union[str, None] = "1f8c4e7b2a63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invalid_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "import_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_files.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "transaction_type IN ('bank', 'ledger')",
            name="ck_invalid_transactions_transaction_type",
        ),
        sa.CheckConstraint("row_number > 0", name="ck_invalid_transactions_row_number"),
        sa.UniqueConstraint(
            "run_id",
            "transaction_type",
            "row_number",
            name="uq_invalid_transactions_run_type_row",
        ),
    )
    op.create_index(
        "idx_invalid_transactions_run", "invalid_transactions", ["run_id"]
    )

    op.execute(
        """
        INSERT INTO invalid_transactions (
            run_id,
            import_file_id,
            transaction_type,
            row_number,
            source_file,
            error,
            raw_data,
            created_at
        )
        SELECT
            audit.run_id,
            imported.id,
            parsed.payload->>'transaction_type',
            (parsed.payload->>'row')::integer,
            COALESCE(parsed.payload->>'source_file', imported.file_name, 'unknown'),
            COALESCE(parsed.payload->>'error', 'Row failed validation'),
            COALESCE(parsed.payload->'raw_data', '{}'::jsonb),
            audit.created_at
        FROM audit_history AS audit
        CROSS JOIN LATERAL (
            SELECT audit.description::jsonb AS payload
        ) AS parsed
        LEFT JOIN import_files AS imported
            ON imported.run_id = audit.run_id
            AND imported.file_type = parsed.payload->>'transaction_type'
        WHERE audit.action = 'transaction_invalid'
        """
    )
    op.execute("DELETE FROM audit_history WHERE action = 'transaction_invalid'")


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO audit_history (run_id, action, description, created_at)
        SELECT
            run_id,
            'transaction_invalid',
            jsonb_build_object(
                'transaction_type', transaction_type,
                'row', row_number,
                'source_file', source_file,
                'error', error,
                'raw_data', raw_data
            )::text,
            created_at
        FROM invalid_transactions
        """
    )
    op.drop_index("idx_invalid_transactions_run", table_name="invalid_transactions")
    op.drop_table("invalid_transactions")
