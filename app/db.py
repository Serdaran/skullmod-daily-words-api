from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine, Session
from .config import settings


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


DATABASE_URL = normalize_database_url(settings.DATABASE_URL)


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
)

def init_db():
    from .models import User, DailyWord, PhysicalSkull, NFCScanLog  # tablo tanımları
    SQLModel.metadata.create_all(engine)
    ensure_user_account_columns()


def ensure_user_account_columns():
    if "sqlite" not in DATABASE_URL:
        return

    inspector = inspect(engine)
    if not inspector.has_table("user"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("user")}
    account_columns = {
        "email": "VARCHAR",
        "password_hash": "VARCHAR",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_type in account_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE user ADD COLUMN {column_name} {column_type}")
                )

def get_session():
    with Session(engine) as session:
        yield session
