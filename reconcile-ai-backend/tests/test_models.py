from app.db import Base
from app.db.models import EntityMapping, User
from sqlalchemy import UniqueConstraint


def test_database_models_are_registered() -> None:
    expected_tables = {
        "users",
        "reconciliation_runs",
        "import_files",
        "bank_transactions",
        "ledger_entries",
        "match_candidates",
        "reconciliation_results",
        "entity_mappings",
        "exceptions",
        "audit_history",
    }

    actual_tables = {table.name for table in Base.metadata.sorted_tables}

    assert expected_tables.issubset(actual_tables)


def test_user_model_has_login_fields_without_plaintext_password() -> None:
    columns = User.__table__.c

    assert {"id", "full_name", "email", "password_hash", "is_active", "created_at"} <= set(
        columns.keys()
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("email",)
        for constraint in User.__table__.constraints
    )
    assert columns.password_hash.nullable


def test_entity_mappings_are_owned_and_unique_per_user() -> None:
    columns = EntityMapping.__table__.c

    assert "owner_user_id" in columns
    assert not columns.owner_user_id.nullable
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns)
        == ("owner_user_id", "source_name")
        for constraint in EntityMapping.__table__.constraints
    )
