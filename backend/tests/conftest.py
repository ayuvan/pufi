"""
PUFI — pytest shared fixtures.

Strategy:
  - DB fixtures use a pure in-memory SQLite engine, completely isolated from
    the development database.
  - The API client uses httpx.AsyncClient + ASGITransport, which works
    correctly with Starlette 0.41+ (avoids BaseHTTPMiddleware deadlock).
  - The production `app` from main.py is reused, but its get_db dependency
    is overridden to use the per-test rolled-back DB session.
  - Each test gets a rolled-back DB session for full isolation.
"""
import sys
import os

# Ensure backend/ is on sys.path regardless of where pytest is invoked from
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Point the app at the in-memory test DB BEFORE importing main.py
os.environ["DATABASE_URL"] = "sqlite://"

import pytest
import anyio
from decimal import Decimal
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# In-memory database (one engine for the whole session)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(test_engine, "connect")
def _set_fk_pragma(dbapi_conn, _):
    """Enable FK enforcement — mirrors the fix applied to the production engine."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ---------------------------------------------------------------------------
# Schema: created once per session, dropped after all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    from models.db import Base
    import models.entities  # noqa: F401 — register ORM classes with Base
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# ---------------------------------------------------------------------------
# Per-test DB session with rollback (savepoint for inner rollbacks)
# ---------------------------------------------------------------------------

@pytest.fixture()
def db() -> Session:
    """
    Transactional DB session rolled back after every test.
    Uses a savepoint so that IntegrityError rollbacks inside the test
    don't destroy the outer transaction used for cleanup.
    """
    conn = test_engine.connect()
    outer_tx = conn.begin()
    session = TestSessionLocal(bind=conn)
    session.begin_nested()  # savepoint

    yield session

    session.close()
    outer_tx.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def seeded_db(db):
    """One Business, two Suppliers, two Obligations pre-inserted."""
    from models.entities import Business, Supplier, Obligation

    biz = Business(id="BIZ-TEST-001", display_name="Test Corp")
    db.add(biz)
    db.flush()

    sup_a = Supplier(
        id="SUP-TEST-A",
        business_id="BIZ-TEST-001",
        external_reference="EXT-A",
        display_name="Supplier Alpha",
        country_code="US",
        recipient_reference_masked="a***@example.com",
    )
    sup_b = Supplier(
        id="SUP-TEST-B",
        business_id="BIZ-TEST-001",
        external_reference="EXT-B",
        display_name="Supplier Beta",
        country_code="DE",
        recipient_reference_masked="b***@example.com",
    )
    db.add_all([sup_a, sup_b])
    db.flush()

    ob1 = Obligation(
        business_id="BIZ-TEST-001",
        supplier_id="SUP-TEST-A",
        invoice_reference="INV-TEST-001",
        amount=Decimal("1000.00"),
        currency="USD",
        due_at=date(2026, 12, 31),
        status="DRAFT",
        source_hash="aaa",
    )
    ob2 = Obligation(
        business_id="BIZ-TEST-001",
        supplier_id="SUP-TEST-B",
        invoice_reference="INV-TEST-002",
        amount=Decimal("500.5000"),
        currency="EUR",
        due_at=date(2026, 11, 30),
        status="VALIDATED",
        source_hash="bbb",
    )
    db.add_all([ob1, ob2])
    db.flush()

    return {"business": biz, "sup_a": sup_a, "sup_b": sup_b, "ob1": ob1, "ob2": ob2}


# ---------------------------------------------------------------------------
# Synchronous HTTP client using httpx + ASGITransport (no middleware deadlock)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db):
    """
    Synchronous httpx client wired to the FastAPI ASGI app via ASGITransport.

    Why not TestClient?  Starlette ≥ 0.41 + BaseHTTPMiddleware can deadlock
    inside the anyio thread-pool used by TestClient's sync wrapper.
    httpx.Client(transport=ASGITransport(...)) runs the ASGI app directly
    in the same thread without the anyio event-loop bridge, avoiding the hang.

    The production app's get_db dependency is overridden to inject the
    per-test rolled-back session.
    """
    from main import app
    from models.db import get_db

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    # httpx.ASGITransport is async-only in httpx>=0.23; use starlette TestClient instead.
    # The middleware deadlock is avoided because main.py uses @app.middleware("http")
    # decorator style (not BaseHTTPMiddleware subclass), which is safe with TestClient.
    # The lifespan deadlock is avoided because DATABASE_URL=sqlite:// is set before
    # import, so create_all runs against the same in-memory engine used by the tests.
    from starlette.testclient import TestClient as _TestClient
    with _TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
