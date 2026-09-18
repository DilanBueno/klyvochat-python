from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from config import settings

DB_PATH = Path(settings.DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_friend_columns()
    _ensure_message_columns()


def _ensure_message_columns() -> None:
    inspector = inspect(engine)
    if "messages" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("messages")}
    columns = {
        "msg_id": "VARCHAR(64)",
        "delivered": "BOOLEAN NOT NULL DEFAULT 0",
        "read": "BOOLEAN NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE messages ADD COLUMN {name} {definition}"))


def _ensure_friend_columns() -> None:
    inspector = inspect(engine)
    if "friends" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("friends")}
    columns = {
        "username": "VARCHAR(255)",
        "email": "VARCHAR(255)",
        "status": "VARCHAR(32) NOT NULL DEFAULT 'offline'",
    }
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE friends ADD COLUMN {name} {definition}"))


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
