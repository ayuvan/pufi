"""
PUFI — Obligations router.

Day 1 endpoints:
  GET /api/v1/obligations   — paginated list of obligations with supplier info

Day 2 endpoints:
  POST /api/v1/obligations/import  — import JSON obligations with per-row validation
"""
import hashlib
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload

from models.db import get_db
from models.entities import Obligation
from schemas.obligation import (
    ImportResponse, ImportRowResult, ImportResultStatus,
    ObligationImportRow, ObligationListResponse, ObligationOut,
)
from services.validation import validate_import_row

router = APIRouter()

# ---------------------------------------------------------------------------
# Default business_id for the prototype
# (Day 3 adds real auth; for now every import is owned by the first business)
# ---------------------------------------------------------------------------

_DEFAULT_BUSINESS_ID = "BIZ-ACME-001"


def _get_default_business_id(db: Session) -> str:
    """Return the first business ID in the DB (prototype: single-tenant)."""
    from models.entities import Business
    biz = db.query(Business).first()
    return biz.id if biz else _DEFAULT_BUSINESS_ID


# ===========================================================================
# GET /obligations
# ===========================================================================

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
    business_id: str = Query(default=None, description="Filter by business ID (optional)"),
    db: Session = Depends(get_db),
) -> ObligationListResponse:
    """
    Returns obligations ordered by created_at descending.

    Query parameters:
      limit       — max records per page (1–200, default 50)
      offset      — pagination offset (default 0)
      status      — optional status filter
      business_id — optional business ID filter
    """
    query = db.query(Obligation).options(joinedload(Obligation.supplier))

    if business_id:
        query = query.filter(Obligation.business_id == business_id)

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


# ===========================================================================
# POST /obligations/import
# ===========================================================================

@router.post(
    "/obligations/import",
    response_model=ImportResponse,
    status_code=200,
    summary="Import obligation rows",
    description=(
        "Accepts a JSON array of obligation rows, validates each one, "
        "and inserts ACCEPTED rows as DRAFT obligations. "
        "DUPLICATE and INVALID rows are reported per-row but not inserted. "
        "Returns per-row results so the caller can display validation feedback."
    ),
)
def import_obligations(
    request: Request,
    rows: list[ObligationImportRow],
    db: Session = Depends(get_db),
) -> ImportResponse:
    """
    Per-row import logic:

    ACCEPTED  — All validation checks passed; inserted as DRAFT obligation.
    DUPLICATE — (business_id, invoice_reference, supplier_id) already exists.
                Not an error, but NOT inserted again.
    INVALID   — One or more validation checks failed; never inserted.

    Rules:
      - amount must be a parseable Decimal > 0
      - currency must be in the ISO 4217 allowlist
      - due_at must be YYYY-MM-DD
      - supplier_reference must resolve to a known Supplier
      - business key (business_id, invoice_reference, supplier_id) must be unique
    """
    business_id = _get_default_business_id(db)
    correlation_id = getattr(request.state, "correlation_id", "unknown")

    results: list[ImportRowResult] = []
    accepted = duplicate = invalid = 0

    # Track keys seen in this batch to detect within-batch duplicates before
    # they hit the DB unique constraint.
    seen_keys: set[tuple[str, str, str]] = set()

    for idx, row in enumerate(rows):
        # Within-batch duplicate check (before DB lookup)
        # We need the supplier ID for the key — resolve it first
        from models.entities import Supplier as _Supplier
        sup = (
            db.query(_Supplier)
            .filter(
                _Supplier.business_id == business_id,
                _Supplier.external_reference == row.supplier_reference,
            )
            .first()
        )
        batch_key = (business_id, row.invoice_reference, sup.id if sup else "")

        if sup and batch_key in seen_keys:
            results.append(ImportRowResult(
                row_index=idx,
                invoice_reference=row.invoice_reference,
                supplier_reference=row.supplier_reference,
                status=ImportResultStatus.DUPLICATE,
                reason="Duplicate row within this import batch",
            ))
            duplicate += 1
            continue

        result = validate_import_row(
            business_id=business_id,
            supplier_reference=row.supplier_reference,
            invoice_reference=row.invoice_reference,
            amount_str=row.amount,
            currency=row.currency,
            due_at_str=row.due_at,
            db=db,
        )

        if result.duplicate:
            results.append(ImportRowResult(
                row_index=idx,
                invoice_reference=row.invoice_reference,
                supplier_reference=row.supplier_reference,
                status=ImportResultStatus.DUPLICATE,
                reason="Already exists in the database",
            ))
            duplicate += 1

        elif not result.valid:
            results.append(ImportRowResult(
                row_index=idx,
                invoice_reference=row.invoice_reference,
                supplier_reference=row.supplier_reference,
                status=ImportResultStatus.INVALID,
                reason="; ".join(result.errors),
            ))
            invalid += 1

        else:
            # --- Insert as DRAFT obligation ---
            assert result.amount is not None
            assert result.due_at is not None
            assert result.supplier is not None

            hash_input = (
                f"{row.supplier_reference}|{row.invoice_reference}"
                f"|{row.amount}|{row.currency}|{row.due_at}"
            )
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            ob = Obligation(
                business_id=business_id,
                supplier_id=result.supplier.id,
                invoice_reference=row.invoice_reference,
                amount=result.amount,
                currency=row.currency,
                due_at=result.due_at,
                status="DRAFT",
                source_hash=source_hash,
                notes=row.notes,
            )
            db.add(ob)
            db.flush()  # get generated id before committing

            seen_keys.add((business_id, row.invoice_reference, result.supplier.id))

            results.append(ImportRowResult(
                row_index=idx,
                invoice_reference=row.invoice_reference,
                supplier_reference=row.supplier_reference,
                status=ImportResultStatus.ACCEPTED,
                obligation_id=ob.id,
            ))
            accepted += 1

    db.commit()

    return ImportResponse(
        total_rows=len(rows),
        accepted=accepted,
        duplicate=duplicate,
        invalid=invalid,
        results=results,
        correlation_id=correlation_id,
    )
