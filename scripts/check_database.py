import sys
from pathlib import Path

from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import DATABASE_URL, engine, init_db
from app.models import User


def main() -> None:
    init_db()
    with Session(engine) as session:
        user_count = len(session.exec(select(User.user_id)).all())

    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    print(f"Database OK: {safe_url}")
    print(f"Users: {user_count}")


if __name__ == "__main__":
    main()
