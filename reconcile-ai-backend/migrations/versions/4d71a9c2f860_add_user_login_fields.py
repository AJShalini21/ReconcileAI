"""add user login fields

Revision ID: 4d71a9c2f860
Revises: c48d31a26020
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d71a9c2f860"
down_revision: Union[str, None] = "c48d31a26020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"]: column for column in inspector.get_columns("users")}

    if "email" not in columns and "username" in columns:
        op.alter_column(
            "users",
            "username",
            new_column_name="email",
            existing_type=columns["username"]["type"],
            type_=sa.String(length=255),
            existing_nullable=False,
        )
    elif "email" not in columns:
        raise RuntimeError("The users table has neither an email nor a username column.")
    elif getattr(columns["email"]["type"], "length", None) != 255:
        op.alter_column(
            "users",
            "email",
            existing_type=columns["email"]["type"],
            type_=sa.String(length=255),
            existing_nullable=False,
        )

    if "full_name" not in columns and "display_name" in columns:
        op.alter_column(
            "users",
            "display_name",
            new_column_name="full_name",
            existing_type=columns["display_name"]["type"],
            type_=sa.String(length=255),
            existing_nullable=False,
        )
    elif "full_name" not in columns:
        raise RuntimeError("The users table has neither a full_name nor a display_name column.")
    elif getattr(columns["full_name"]["type"], "length", None) != 255:
        op.alter_column(
            "users",
            "full_name",
            existing_type=columns["full_name"]["type"],
            type_=sa.String(length=255),
            existing_nullable=False,
        )

    if "password_hash" not in columns:
        op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))

    for constraint in inspector.get_unique_constraints("users"):
        if constraint.get("column_names") in (["username"], ["email"]):
            op.drop_constraint(constraint["name"], "users", type_="unique")

    op.execute(
        """
        UPDATE users
        SET email = CASE
            WHEN lower(trim(email)) = 'default' THEN 'demo@reconcileai.test'
            WHEN position('@' in trim(email)) > 1 THEN lower(trim(email))
            ELSE 'legacy-' || id::text || '@users.invalid'
        END
        """
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.execute(
        """
        UPDATE users
        SET email = CASE
            WHEN email = 'demo@reconcileai.test' THEN 'default'
            ELSE 'legacy-' || id::text
        END
        """
    )
    op.alter_column(
        "users",
        "full_name",
        new_column_name="display_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "email",
        new_column_name="username",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.drop_column("users", "password_hash")
