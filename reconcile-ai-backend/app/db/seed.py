from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal

DEMO_USER_EMAIL = "demo@reconcileai.test"


def seed_default_user() -> dict[str, str | bool]:
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == DEMO_USER_EMAIL))
        if user is None:
            session.add(
                User(
                    full_name="Default User",
                    email=DEMO_USER_EMAIL,
                )
            )
            session.commit()
            return {"status": "inserted", "email": DEMO_USER_EMAIL}

        return {"status": "exists", "email": user.email}


if __name__ == "__main__":
    print(seed_default_user())
