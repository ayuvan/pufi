"""
PUFI — Health check router.

GET /api/v1/health
  Returns service status and version.  Used by the frontend connection check
  and any future monitoring infrastructure.
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    correlation_id: str


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health_check(request: Request) -> HealthResponse:
    """
    Returns 200 OK with service status.
    The frontend polls this on startup to confirm the backend is reachable.
    """
    return HealthResponse(
        status="ok",
        version="0.1.0",
        correlation_id=getattr(request.state, "correlation_id", "unknown"),
    )
