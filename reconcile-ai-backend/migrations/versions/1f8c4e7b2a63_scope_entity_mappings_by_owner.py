"""scope entity mappings by owner

Revision ID: 1f8c4e7b2a63
Revises: 4d71a9c2f860
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1f8c4e7b2a63"
down_revision: Union[str, None] = "4d71a9c2f860"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_entity_mappings_source_name",
        "entity_mappings",
        type_="unique",
    )
    op.add_column(
        "entity_mappings",
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_entity_mappings_owner_user_id_users",
        "entity_mappings",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        INSERT INTO users (full_name, email, is_active)
        VALUES ('Default User', 'demo@reconcileai.test', TRUE)
        ON CONFLICT (email) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE entity_mappings
        SET owner_user_id = (
            SELECT id FROM users WHERE email = 'demo@reconcileai.test'
        )
        WHERE owner_user_id IS NULL
        """
    )
    op.alter_column("entity_mappings", "owner_user_id", nullable=False)
    op.create_unique_constraint(
        "uq_entity_mappings_owner_source",
        "entity_mappings",
        ["owner_user_id", "source_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_entity_mappings_owner_source",
        "entity_mappings",
        type_="unique",
    )
    op.drop_constraint(
        "fk_entity_mappings_owner_user_id_users",
        "entity_mappings",
        type_="foreignkey",
    )
    op.drop_column("entity_mappings", "owner_user_id")
    op.create_unique_constraint(
        "uq_entity_mappings_source_name",
        "entity_mappings",
        ["source_name"],
    )
