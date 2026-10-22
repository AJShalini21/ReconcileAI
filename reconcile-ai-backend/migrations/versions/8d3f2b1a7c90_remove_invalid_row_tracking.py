"""remove invalid row tracking

Revision ID: 8d3f2b1a7c90
Revises: 6a2d9f1c8b47
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8d3f2b1a7c90"
down_revision: Union[str, None] = "6a2d9f1c8b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invalid_transactions")


def downgrade() -> None:
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
