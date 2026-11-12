"""
PUFI — FastAPI application entry point.

Registers:
  - CORS middleware (origins read from CORS_ORIGINS env var)
  - Correlation-ID middleware (every response carries X-Correlation-ID)
  - API routers under /api/v1

Database tables are created automatically on startup via SQLAlchemy
metadata (Base.metadata.create_all). Alembic migrations take over
for schema changes from Day 2 onward.
"""
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models.db import Base, engine  # load_dotenv() runs inside models/db.py
from models import entities  # noqa: F401 — registers ORM classes with Base
from routers import health, obligations, batches, analysis, execution, webhooks

logger = logging.getLogger("pufi")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables on startup (dev convenience).  Alembic for migrations."""
    Base.metadata.create_all(bind=engine)
    _validate_startup_credentials()
    yield
    # Nothing to tear down for SQLite dev setup


def _validate_startup_credentials() -> None:
    """
    Warn at startup if PayPal credentials appear to be placeholder values.

    Rules:
      - NEVER log the actual credential values.
      - Only log a WARNING if the values look like unset placeholders.
      - This is advisory only: the app continues running so the demo/simulation
        path still works without real PayPal credentials.
    """
    _PLACEHOLDER_SUBSTRINGS = (
        "your_", "placeholder", "example", "changeme", "xxx", "yyy", "zzz",
        "<", ">", "REPLACE", "INSERT", "TODO",
    )

    client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")

    def _looks_like_placeholder(value: str) -> bool:
        if not value or len(value) < 4:
            return True
        low = value.lower()
        return any(p in low for p in _PLACEHOLDER_SUBSTRINGS)

    warnings_issued = []
    if _looks_like_placeholder(client_id):
        warnings_issued.append("PAYPAL_CLIENT_ID")
    if _looks_like_placeholder(client_secret):
        warnings_issued.append("PAYPAL_CLIENT_SECRET")

    if warnings_issued:
        logger.warning(
            "⚠  PUFI STARTUP — PayPal credential(s) appear to be unset or "
            "placeholder values: %s.  "
            "PayPal Sandbox payouts will be unavailable.  "
            "Simulated providers remain fully functional.  "
            "Set real Sandbox credentials in backend/.env to enable PayPal.",
            ", ".join(warnings_issued),
        )
    else:
        logger.info(
            "✓ PUFI STARTUP — PayPal credential presence verified "
            "(values are NEVER logged).  Sandbox mode active."
        )


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PUFI API",
    version="0.1.0",
    description=(
        "Enterprise Payment Coordination Infrastructure — "
        "hackathon prototype. Not a bank, wallet, or payment rail."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS — origins read from CORS_ORIGINS env var; falls back to localhost dev defaults.
# Replace with an explicit production origin list before any public deployment.
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Propagate or generate a correlation ID for every request.
    The ID is echoed in the response header for debugging and audit.
    """
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    # H-3 fix: log the full traceback server-side; never expose internals in the response.
    logger.exception("Unhandled exception [corr=%s]: %s", correlation_id, exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            },
            "correlation_id": correlation_id,
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(obligations.router, prefix="/api/v1", tags=["obligations"])
app.include_router(batches.router, prefix="/api/v1", tags=["batches"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
