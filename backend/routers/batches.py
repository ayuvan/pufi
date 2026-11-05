"""
PUFI — Payment Batches router (Day 2).

Endpoints:
  POST /api/v1/batches            — create a batch from validated obligation IDs
  GET  /api/v1/batches/{batch_id} — get batch detail with obligations list

A batch groups validated obligations for a single payment run.
Only VALIDATED obligations may be added to a batch.
Approval and submission are Day 4 features.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from models.db import get_db
from models.entities import BatchObligation, Obligation, PaymentBatch
from schemas.obligation import BatchCreateRequest, BatchObligationSummary, BatchOut

logger = logging.getLogger("pufi.batches")

router = APIRouter()


def _get_default_business_id(db: Session) -> str:
    """Return the first business ID (prototype: single-tenant)."""
    from models.entities import Business
    biz = db.query(Business).first()
    return biz.id if biz else "BIZ-ACME-001"


# ===========================================================================
# POST /batches
# ===========================================================================

@router.post(
    "/batches",
    response_model=BatchOut,
    status_code=201,
    summary="Create a payment batch",
    description=(
        "Creates a DRAFT payment batch from a list of VALIDATED obligation IDs. "
        "Only VALIDATED obligations are eligible. DRAFT, ON_HOLD, or already-batched "
        "obligations are rejected with a 422 error listing the offending IDs."
    ),
)
def create_batch(
    request: Request,
    body: BatchCreateRequest,
    db: Session = Depends(get_db),
) -> BatchOut:
    business_id = _get_default_business_id(db)

    # --- Validate all obligation IDs before creating anything ---
    obligation_ids = list(dict.fromkeys(body.obligation_ids))  # deduplicate, preserve order

    obligations = (
        db.query(Obligation)
        .options(joinedload(Obligation.supplier))
        .filter(Obligation.id.in_(obligation_ids))
        .all()
    )

    found_ids = {ob.id for ob in obligations}
    missing = [oid for oid in obligation_ids if oid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"error": "OBLIGATION_NOT_FOUND", "ids": missing},
        )

    # Only VALIDATED obligations may be batched
    not_validated = [ob.id for ob in obligations if ob.status != "VALIDATED"]
    if not_validated:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "OBLIGATION_NOT_VALIDATED",
                "message": "Only VALIDATED obligations can be added to a batch.",
                "ids": not_validated,
            },
        )

    # Check batch_reference uniqueness for this business
    existing_batch = (
        db.query(PaymentBatch)
        .filter(
            PaymentBatch.business_id == business_id,
            PaymentBatch.batch_reference == body.batch_reference,
        )
        .first()
    )
    if existing_batch:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "BATCH_REFERENCE_EXISTS",
                "message": f"Batch reference {body.batch_reference!r} already exists.",
            },
        )

    # --- Create the batch ---
    batch = PaymentBatch(
        business_id=business_id,
        batch_reference=body.batch_reference,
        status="DRAFT",
        notes=body.notes,
    )
    db.add(batch)
    db.flush()  # get the generated batch.id

    # --- Link obligations ---
    for ob in obligations:
        link = BatchObligation(
            batch_id=batch.id,
            obligation_id=ob.id,
        )
        db.add(link)

    db.commit()
    db.refresh(batch)

    logger.info(
        "Batch created [corr=%s]: batch_id=%s ref=%r obligations=%d",
        getattr(request.state, "correlation_id", "unknown"),
        batch.id,
        batch.batch_reference,
        len(obligations),
    )

    return _batch_to_schema(batch, obligations, db)


# ===========================================================================
# GET /batches/{batch_id}
# ===========================================================================

@router.get(
    "/batches/{batch_id}",
    response_model=BatchOut,
    summary="Get batch detail",
    description="Returns a batch with its full list of linked obligations.",
)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
) -> BatchOut:
    batch = (
        db.query(PaymentBatch)
        .options(
            joinedload(PaymentBatch.batch_obligations)
            .joinedload(BatchObligation.obligation)
            .joinedload(Obligation.supplier)
        )
        .filter(PaymentBatch.id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail={"error": "BATCH_NOT_FOUND"})

    obligations = [bo.obligation for bo in batch.batch_obligations]
    return _batch_to_schema(batch, obligations, db)


# ===========================================================================
# Helper
# ===========================================================================

def _batch_to_schema(
    batch: PaymentBatch,
    obligations: list[Obligation],
    db: Session,
) -> BatchOut:
    """Convert a PaymentBatch ORM object to its API schema."""
    # Reload batch_obligations to get added_at timestamps
    db.refresh(batch)
    bo_map = {bo.obligation_id: bo for bo in batch.batch_obligations}

    obligation_summaries = [
        BatchObligationSummary(
            obligation_id=ob.id,
            invoice_reference=ob.invoice_reference,
            amount=str(ob.amount),
            currency=ob.currency,
            supplier_name=ob.supplier.display_name if ob.supplier else "Unknown",
            added_at=bo_map[ob.id].added_at if ob.id in bo_map else batch.created_at,
        )
        for ob in obligations
    ]

    return BatchOut(
        id=batch.id,
        batch_reference=batch.batch_reference,
        status=batch.status,
        notes=batch.notes,
        created_at=batch.created_at,
        approved_by=batch.approved_by,
        approved_at=batch.approved_at,
        obligation_count=len(obligations),
        obligations=obligation_summaries,
    )
