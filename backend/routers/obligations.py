"""
PUFI — Obligations router.

Day 1 endpoints:
  GET /api/v1/obligations   — paginated list of obligations with supplier info

Day 2 endpoints added here:
  POST /api/v1/obligations/import  — import JSON obligations
  POST /api/v1/batches             — create batch from obligation IDs
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload

from models.db import get_db
from models.entities import Obligation
from schemas.obligation import ObligationListResponse, ObligationOut

router = APIRouter()


@router.get(
    "/obligations",
    response_model=ObligationListResponse,
    summary="List payment obligations",
    description=(
        "Returns a paginated list of obligations with their supplier details "
        "and current status.  Obligations are ordered newest-first."
    ),
)
def list_obligations(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    status: str = Query(default=None, description="Filter by status (e.g. DRAFT, VALIDATED)"),
    db: Session = Depends(get_db),
) -> ObligationListResponse:
    """
    Returns obligations ordered by created_at descending.

    Query parameters:
      limit  — max records per page (1–200, default 50)
      offset — pagination offset (default 0)
      status — optional status filter
    """
    query = db.query(Obligation).options(joinedload(Obligation.supplier))

    if status:
        query = query.filter(Obligation.status == status.upper())

    total: int = query.count()
    items: list[Obligation] = (
        query.order_by(Obligation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ObligationListResponse(
        items=[ObligationOut.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
        correlation_id=getattr(request.state, "correlation_id", "unknown"),
    )
