"""add ledger transaction direction

Revision ID: c48d31a26020
Revises: 3b97ff423519
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c48d31a26020"
down_revision: Union[str, None] = "3b97ff423519"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ledger_entries",
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="unknown"),
    )
    op.execute(
        """
        UPDATE ledger_entries
        SET direction = CASE
            WHEN COALESCE(credit_amount, 0) > 0 THEN 'credit'
            WHEN COALESCE(debit_amount, 0) > 0 THEN 'debit'
            ELSE 'unknown'
        END
        """
    )
    op.create_check_constraint(
        "ck_ledger_entries_direction",
        "ledger_entries",
        "direction IN ('credit', 'debit', 'unknown')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ledger_entries_direction", "ledger_entries", type_="check")
    op.drop_column("ledger_entries", "direction")
