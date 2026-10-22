from sqlalchemy import text

from app.db.session import engine


def check_database_connection() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            database_version = connection.execute(text("SELECT version()")).scalar_one()
        return True, database_version
    except Exception as exc:  # pragma: no cover - defensive path for runtime failures
        return False, str(exc)
