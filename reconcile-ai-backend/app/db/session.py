from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

from sqlalchemy import create_engine

settings = get_settings()
database_url = make_url(settings.database_url)
engine_options = {"pool_pre_ping": True}
if database_url.get_backend_name() == "postgresql":
    engine_options.update(
        connect_args={"connect_timeout": 10},
        pool_timeout=10,
    )

engine_options["pool_pre_ping"] = True

engine = create_engine(
    settings.database_url,
    echo=True,
    echo_pool="debug",
    hide_parameters=True,
    **engine_options,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
