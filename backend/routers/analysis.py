"""
PUFI — Financial analysis router (Day 3).

Endpoints:
  POST /api/v1/batches/{batch_id}/analyze
      Run deterministic eligibility + cost analysis + AI advisory for a batch.

  GET  /api/v1/batches/{batch_id}/analysis
      Retrieve the most recent stored AI recommendation for a batch.

IMPORTANT:
  - Analysis is SIMULATED for Day 3.  No real payments are submitted.
  - The AI recommendation is advisory only and must not be treated as approval.
  - All monetary values are returned as strings to preserve Decimal precision.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from models.db import get_db
from models.entities import AiRecommendation, AuditEvent, BatchObligation, Obligation, PaymentBatch, Supplier
from schemas.analysis import (
    AiRecommendationOut,
    BatchAnalysisResponse,
    ProviderCostOut,
)
from services.ai_advisor import analyze_batch as ai_analyze_batch
from services.provider_registry import get_provider
from services.routing_engine import ObligationContext, route_obligation

logger = logging.getLogger("pufi.analysis")

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decimal_str(v: Optional[Decimal]) -> Optional[str]:
    """Serialise Decimal to string for JSON output, or None."""
    return str(v) if v is not None else None


def _dt_str(dt) -> Optional[str]:
    """Serialise datetime to ISO 8601 string, or None."""
    return dt.isoformat() if dt is not None else None


def _aggregate_amounts_by_currency(
    obligations: list[Obligation],
) -> dict[str, str]:
    """
    Sum obligation amounts grouped by currency.
    Returns dict of currency → Decimal string.
    """
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for obl in obligations:
        totals[obl.currency] += Decimal(str(obl.amount))
    return {currency: str(total) for currency, total in sorted(totals.items())}


def _get_recipient_type(supplier: Optional[Supplier]) -> str:
    """Return the supplier's recipient_reference_type, defaulting to EMAIL."""
    if supplier and hasattr(supplier, "recipient_reference_type"):
        return (supplier.recipient_reference_type or "EMAIL").upper()
    return "EMAIL"


def _get_recipient_currency(obligation: Obligation, supplier: Optional[Supplier]) -> str:
    """
    Determine the recipient currency.
    For Day 3: use supplier preferred_currency if set, else same as source.
    """
    if supplier and supplier.preferred_currency:
        return supplier.preferred_currency.upper()
    return obligation.currency.upper()


# ---------------------------------------------------------------------------
# POST /batches/{batch_id}/analyze
# ---------------------------------------------------------------------------

@router.post(
    "/batches/{batch_id}/analyze",
    response_model=BatchAnalysisResponse,
    summary="Analyse a batch for eligible payment routes (SIMULATED)",
)
def analyze_batch_endpoint(
    batch_id: str,
    request: Request,
    strategy: str = Query(
        default="LOWEST_COST",
        description="Routing strategy: LOWEST_COST | FASTEST | BALANCED",
    ),
    db: Session = Depends(get_db),
) -> BatchAnalysisResponse:
    """
    Run deterministic eligibility and cost analysis for all obligations in a batch.

    - Checks each obligation against all enabled providers.
    - Calculates estimated costs (SIMULATED FX rates, labelled explicitly).
    - Calls AI advisor for an explanatory recommendation (advisory only).
    - Stores the AI recommendation for audit.

    Returns BatchAnalysisResponse with provider routes and AI advisory.
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # --- Load batch ---
    batch = (
        db.query(PaymentBatch)
        .filter(PaymentBatch.id == batch_id)
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id!r} not found.")

    # --- Load obligations ---
    batch_obligation_rows = (
        db.query(BatchObligation)
        .filter(BatchObligation.batch_id == batch_id)
        .all()
    )
    if not batch_obligation_rows:
        raise HTTPException(
            status_code=422,
            detail=f"Batch {batch_id!r} has no obligations.",
        )

    obligation_ids = [bo.obligation_id for bo in batch_obligation_rows]
    obligations = (
        db.query(Obligation)
        .options(joinedload(Obligation.supplier))
        .filter(Obligation.id.in_(obligation_ids))
        .all()
    )

    # --- Aggregate amounts by currency ---
    total_by_currency = _aggregate_amounts_by_currency(obligations)
    total_obligations = len(obligations)

    # --- Run routing for each obligation, then aggregate by provider ---
    # For Day 3 we analyse each obligation independently and merge the results.
    # The batch-level view shows the union of eligible/excluded providers.

    provider_eligible: dict[str, list] = {}   # code → list of cost results
    provider_excluded: dict[str, list] = {}   # code → list of reasons

    for obl in obligations:
        supplier = obl.supplier
        obl_ctx = ObligationContext(
            obligation_id=obl.id,
            source_amount=Decimal(str(obl.amount)),
            source_currency=obl.currency.upper(),
            recipient_currency=_get_recipient_currency(obl, supplier),
            recipient_type=_get_recipient_type(supplier),
        )
        routing_result = route_obligation(obl_ctx, strategy=strategy)

        for er in routing_result.eligible_routes:
            if er.provider_code not in provider_eligible:
                provider_eligible[er.provider_code] = []
            provider_eligible[er.provider_code].append(er)

        for ex in routing_result.excluded_routes:
            if ex.provider_code not in provider_excluded:
                provider_excluded[ex.provider_code] = []
            # Only add distinct reasons
            existing_reasons = provider_excluded[ex.provider_code]
            for reason in ex.exclusion_reasons:
                if reason not in existing_reasons:
                    existing_reasons.append(reason)

    # --- Build provider routes for response ---
    provider_routes: list[ProviderCostOut] = []
    eligible_route_codes: list[str] = []

    # Process eligible providers
    for provider_code, results in provider_eligible.items():
        if provider_code in provider_excluded:
            # Mixed: eligible for some obligations, excluded for others.
            # Mark as eligible (conservative — user can drill down per obligation).
            pass

        # Aggregate cost across obligations (sum of fees)
        total_provider_fee = sum(
            (r.cost.provider_fee for r in results if r.cost), Decimal("0")
        )
        total_fx_spread = sum(
            (r.cost.fx_spread_cost for r in results if r.cost), Decimal("0")
        )
        total_cost = sum(
            (r.cost.total_estimated_cost for r in results if r.cost), Decimal("0")
        )
        total_recipient = sum(
            (r.cost.estimated_recipient_amount for r in results if r.cost), Decimal("0")
        )
        all_warnings: list[str] = []
        for r in results:
            if r.cost:
                all_warnings.extend(r.cost.warnings)

        # Representative cost from first result for FX display
        first_cost = results[0].cost if results[0].cost else None
        prov = get_provider(provider_code)

        eligible_route_codes.append(provider_code)
        provider_routes.append(
            ProviderCostOut(
                provider_code=provider_code,
                display_name=results[0].display_name,
                environment=results[0].environment,
                is_simulated=results[0].is_simulated,
                eligible=True,
                exclusion_reasons=[],
                provider_fee=_decimal_str(total_provider_fee),
                fx_spread_cost=_decimal_str(total_fx_spread),
                total_estimated_cost=_decimal_str(total_cost),
                estimated_recipient_amount=_decimal_str(total_recipient),
                recipient_currency=(first_cost.recipient_currency if first_cost else None),
                quote_rate=_decimal_str(first_cost.quote_rate if first_cost else None),
                effective_rate=_decimal_str(first_cost.effective_rate if first_cost else None),
                quote_label=(first_cost.quote_label if first_cost else "N/A"),
                quote_source=(first_cost.quote_source if first_cost else "N/A"),
                quoted_at=_dt_str(first_cost.quoted_at if first_cost else None),
                expires_at=_dt_str(first_cost.expires_at if first_cost else None),
                warnings=list(set(all_warnings)),
                estimated_processing_hours=(prov.estimated_processing_hours if prov else None),
            )
        )

    # Process exclusively excluded providers
    for provider_code, reasons in provider_excluded.items():
        if provider_code in provider_eligible:
            continue  # already added as eligible
        prov = get_provider(provider_code)
        display_name = prov.display_name if prov else provider_code
        environment = prov.environment if prov else "UNKNOWN"
        is_simulated = prov.is_simulated if prov else True

        provider_routes.append(
            ProviderCostOut(
                provider_code=provider_code,
                display_name=display_name,
                environment=environment,
                is_simulated=is_simulated,
                eligible=False,
                exclusion_reasons=reasons,
            )
        )

    # --- AI advisory ---
    # Build serialisable dicts for the AI context (no DB objects)
    eligible_route_dicts = [
        {
            "provider_code": r.provider_code,
            "display_name": r.display_name,
            "environment": r.environment,
            "total_estimated_cost": r.total_estimated_cost,
            "provider_fee": r.provider_fee,
            "fx_spread_cost": r.fx_spread_cost,
            "estimated_processing_hours": r.estimated_processing_hours,
            "quote_label": r.quote_label,
            "warnings": r.warnings,
        }
        for r in provider_routes if r.eligible
    ]
    excluded_route_dicts = [
        {
            "provider_code": r.provider_code,
            "exclusion_reasons": r.exclusion_reasons,
        }
        for r in provider_routes if not r.eligible
    ]

    ai_result, input_hash = ai_analyze_batch(
        batch_reference=batch.batch_reference,
        total_obligations=total_obligations,
        total_by_currency=total_by_currency,
        eligible_routes=eligible_route_dicts,
        excluded_routes=excluded_route_dicts,
        eligible_route_codes=eligible_route_codes,
    )

    # --- Persist AI recommendation ---
    try:
        ai_rec = AiRecommendation(
            batch_id=batch_id,
            model_name=ai_result.model_name,
            input_summary_hash=input_hash,
            recommendation_json=json.dumps(
                {
                    "summary": ai_result.summary,
                    "recommended_route": ai_result.recommended_route,
                    "reasoning_factors": ai_result.reasoning_factors,
                    "warnings": ai_result.warnings,
                    "requires_human_review": ai_result.requires_human_review,
                    "evidence_fields": ai_result.evidence_fields,
                    "fallback_used": ai_result.fallback_used,
                    "fallback_reason": ai_result.fallback_reason,
                },
                default=str,
            ),
            fallback_used=ai_result.fallback_used,
            fallback_reason=ai_result.fallback_reason,
        )
        db.add(ai_rec)
        db.flush()  # flush into session; test harness rolls back, production commits via middleware
        # Write audit event for analysis completion
        db.add(AuditEvent(
            entity_type="BATCH",
            entity_id=batch_id,
            event_type="ANALYSIS_COMPLETED",
            actor="SYSTEM",
            correlation_id=correlation_id,
            details_redacted=json.dumps({
                "total_obligations": total_obligations,
                "eligible_providers": eligible_route_codes,
                "fallback_used": ai_result.fallback_used,
                "model_name": ai_result.model_name,
            }),
        ))
    except Exception as exc:
        # Persistence failure must not break the analysis response
        logger.warning("Failed to persist AI recommendation: %s", exc)
        db.rollback()

    ai_out = AiRecommendationOut(
        summary=ai_result.summary,
        recommended_route=ai_result.recommended_route,
        reasoning_factors=ai_result.reasoning_factors,
        warnings=ai_result.warnings,
        requires_human_review=ai_result.requires_human_review,
        evidence_fields=ai_result.evidence_fields,
        fallback_used=ai_result.fallback_used,
        fallback_reason=ai_result.fallback_reason,
        model_name=ai_result.model_name,
    )

    return BatchAnalysisResponse(
        batch_id=batch_id,
        batch_reference=batch.batch_reference,
        total_obligations=total_obligations,
        total_amount_by_currency=total_by_currency,
        provider_routes=provider_routes,
        ai_recommendation=ai_out,
        routing_strategy=strategy.upper(),
        correlation_id=correlation_id,
        analysis_label="SIMULATED",
        funding_snapshot_label="SIMULATED",
    )


# ---------------------------------------------------------------------------
# GET /batches/{batch_id}/analysis
# ---------------------------------------------------------------------------

@router.get(
    "/batches/{batch_id}/analysis",
    summary="Get the most recent stored AI recommendation for a batch",
)
def get_batch_analysis(
    batch_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns the most recently stored AI recommendation for a batch.
    If none exists, returns 404.
    """
    rec = (
        db.query(AiRecommendation)
        .filter(AiRecommendation.batch_id == batch_id)
        .order_by(AiRecommendation.created_at.desc())
        .first()
    )
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for batch {batch_id!r}. Run POST /analyze first.",
        )
    return {
        "batch_id": batch_id,
        "model_name": rec.model_name,
        "fallback_used": rec.fallback_used,
        "fallback_reason": rec.fallback_reason,
        "created_at": rec.created_at.isoformat(),
        "recommendation": json.loads(rec.recommendation_json),
    }
