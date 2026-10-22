from collections.abc import Generator
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import AUTH_COOKIE_NAME
from app.db.models import User
from app.db.session import get_db
from app.main import app


def _test_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def register_postgres_functions(connection, _record) -> None:
        connection.create_function("gen_random_uuid", 0, lambda: uuid4().hex)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE users (
                id CHAR(32) PRIMARY KEY DEFAULT (gen_random_uuid()),
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255),
                is_active BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_users_email UNIQUE (email)
            )
            """
        )
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_auth_registration_login_current_user_and_logout() -> None:
    session_factory = _test_session_factory()

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            registration = client.post(
                "/api/v1/auth/register",
                headers={"Origin": "http://localhost:8443"},
                json={
                    "full_name": "  Alex   Morgan ",
                    "email": " Alex@Example.com ",
                    "password": "correct-horse-battery",
                },
            )

            assert registration.status_code == 201
            assert registration.json()["user"]["email"] == "alex@example.com"
            assert registration.json()["user"]["full_name"] == "Alex Morgan"
            assert "password_hash" not in registration.json()["user"]
            assert "password" not in registration.json()["user"]
            cookie = registration.cookies.get(AUTH_COOKIE_NAME)
            assert cookie
            assert "httponly" in registration.headers["set-cookie"].lower()

            with session_factory() as session:
                user = session.query(User).filter_by(email="alex@example.com").one()
                assert user.password_hash is not None
                assert user.password_hash != "correct-horse-battery"
                assert user.password_hash.startswith("$argon2id$")

            current_user = client.get("/api/v1/auth/me")
            assert current_user.status_code == 200
            assert current_user.json()["email"] == "alex@example.com"

            duplicate = client.post(
                "/api/v1/auth/register",
                headers={"Origin": "http://localhost:8443"},
                json={
                    "full_name": "Alex Morgan",
                    "email": "ALEX@example.com",
                    "password": "correct-horse-battery",
                },
            )
            assert duplicate.status_code == 409

            logout = client.post(
                "/api/v1/auth/logout",
                headers={"Origin": "http://localhost:8443"},
            )
            assert logout.status_code == 204
            assert client.get("/api/v1/auth/me").status_code == 401

            bad_login = client.post(
                "/api/v1/auth/login",
                headers={"Origin": "http://localhost:8443"},
                json={"email": "alex@example.com", "password": "incorrect"},
            )
            assert bad_login.status_code == 401
            assert bad_login.json()["detail"] == "Invalid email or password."

            good_login = client.post(
                "/api/v1/auth/login",
                headers={"Origin": "http://localhost:8443"},
                json={
                    "email": " ALEX@example.com ",
                    "password": "correct-horse-battery",
                },
            )
            assert good_login.status_code == 200
            assert client.get("/api/v1/auth/me").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_auth_requires_valid_active_user_and_allowed_origin() -> None:
    session_factory = _test_session_factory()

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with session_factory() as session:
            session.add(
                User(
                    full_name="Inactive User",
                    email="inactive@example.com",
                    password_hash=None,
                    is_active=False,
                )
            )
            session.commit()

        with TestClient(app) as client:
            assert client.get("/api/v1/auth/me").status_code == 401
            inactive_login = client.post(
                "/api/v1/auth/login",
                headers={"Origin": "http://localhost:8443"},
                json={"email": "inactive@example.com", "password": "password"},
            )
            assert inactive_login.status_code == 401

            rejected_origin = client.post(
                "/api/v1/auth/register",
                headers={"Origin": "https://untrusted.example"},
                json={
                    "full_name": "Alex Morgan",
                    "email": "alex@example.com",
                    "password": "correct-horse-battery",
                },
            )
            assert rejected_origin.status_code == 403
    finally:
        app.dependency_overrides.clear()
