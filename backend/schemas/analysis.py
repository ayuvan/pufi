"""
PUFI — Pydantic schemas for financial analysis (Day 3).

All monetary values are serialised as strings (not floats) to prevent
floating-point precision loss in JSON responses.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class FxAssumptionsOut(BaseModel):
    """FX quote details shown in the UI."""
    base_currency: str
    quote_currency: str
    mid_rate: Optional[str]        # Decimal as string
    spread_bps: Optional[str]
    effective_rate: Optional[str]
    quote_label: str               # "SIMULATED" | "LIVE" | "N/A" | "UNAVAILABLE"
    quote_source: str
    quoted_at: Optional[str]       # ISO 8601
    expires_at: Optional[str]      # ISO 8601


class ProviderCostOut(BaseModel):
    """
    One provider's eligibility result + cost breakdown for the UI.

    Monetary fields are strings to preserve Decimal precision.
    """
    provider_code: str
    display_name: str
    environment: str               # "SANDBOX" | "SIMULATED"
    is_simulated: bool
    eligible: bool
    exclusion_reasons: list[str]

    # Populated only when eligible=True
    provider_fee: Optional[str] = None
    fx_spread_cost: Optional[str] = None
    total_estimated_cost: Optional[str] = None
    estimated_recipient_amount: Optional[str] = None
    recipient_currency: Optional[str] = None
    quote_rate: Optional[str] = None
    effective_rate: Optional[str] = None
    quote_label: str = "N/A"
    quote_source: str = "N/A"
    quoted_at: Optional[str] = None
    expires_at: Optional[str] = None
    warnings: list[str] = []
    estimated_processing_hours: Optional[int] = None


class AiRecommendationOut(BaseModel):
    """Advisory AI output returned to the UI."""
    summary: str
    recommended_route: Optional[str]
    reasoning_factors: list[str]
    warnings: list[str]
    requires_human_review: bool
    evidence_fields: list[str]
    fallback_used: bool
    fallback_reason: Optional[str]
    model_name: str


class BatchAnalysisResponse(BaseModel):
    """
    Full financial analysis result for one batch.

    analysis_label is always "SIMULATED" for Day 3 (no live provider calls).
    """
    batch_id: str
    batch_reference: str
    total_obligations: int
    total_amount_by_currency: dict[str, str]   # currency → Decimal string
    provider_routes: list[ProviderCostOut]
    ai_recommendation: Optional[AiRecommendationOut]
    routing_strategy: str
    correlation_id: str
    analysis_label: str = "SIMULATED"
    funding_snapshot_label: str = "SIMULATED"
    disclaimer: str = (
        "All estimates are SIMULATED for prototype purposes. "
        "No real money movement has occurred. "
        "AI recommendations are advisory only and require human approval."
    )
