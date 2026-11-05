"""
PUFI — Database engine, session factory, and declarative base.

Uses SQLite for local development (DATABASE_URL=sqlite:///./pufi_dev.db).
Switch to PostgreSQL by changing DATABASE_URL in .env — no code changes required.

IMPORTANT: Never use binary floating-point for monetary arithmetic.
           All amounts are stored as NUMERIC(19,4) and handled with Python Decimal.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./pufi_dev.db")

# SQLite requires check_same_thread=False for multi-threaded FastAPI usage.
# PostgreSQL does not need this argument.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    # Echo SQL in development — set to False in production
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
)

# Enable WAL mode on SQLite for better concurrency during the demo.
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        # H-1 fix: enforce FK constraints (SQLite disables them by default)
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM entities.
    __allow_unmapped__ permits legacy Column() style annotations alongside
    SQLAlchemy 2.x — avoiding full Mapped[] refactor before Day 2.
    """
    __allow_unmapped__ = True


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    Guarantees the session is closed even if the handler raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
