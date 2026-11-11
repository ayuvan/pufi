"""
PUFI — AI decision-support advisor (Day 3).

DESIGN RULES:
  - AI is ADVISORY ONLY.  It cannot approve, execute, or modify payments.
  - AI cannot recommend a provider outside the deterministic eligible-route set.
  - If the AI is unavailable or returns invalid output, the system degrades
    gracefully to a deterministic fallback.  No crash, no silent failure.
  - API key is NEVER logged or sent to the frontend.
  - Input sanitised before sending to the AI: no full PII, no account numbers,
    no raw credentials.
  - Response is validated against a schema before use.
  - Model: gemini-flash-latest (resolved by the API to the current stable Flash).

External dependency: google-genai >= 2.30.1
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("pufi.ai_advisor")


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class AiAnalysisResult:
    """
    Advisory output from the AI model, or a deterministic fallback.

    fallback_used=True whenever:
      - AI_API_KEY is not set
      - The AI service is unreachable
      - The AI response is malformed or invalid JSON
      - The AI recommends a provider NOT in the eligible set
    In every fallback case, the first eligible route (by deterministic ranking)
    is used as the recommended_route.
    """
    summary: str
    recommended_route: Optional[str]
    reasoning_factors: list[str]
    warnings: list[str]
    requires_human_review: bool
    evidence_fields: list[str]
    fallback_used: bool
    fallback_reason: Optional[str]
    model_name: str


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------

def _build_sanitized_context(
    batch_reference: str,
    total_obligations: int,
    total_by_currency: dict[str, str],
    eligible_routes: list[dict],
    excluded_routes: list[dict],
) -> dict:
    """
    Build a sanitised, PII-free context dict to send to the AI.

    Contains only:
      - Batch reference (not internal IDs)
      - Aggregate totals by currency
      - Provider names, environments, cost estimates
      - Exclusion reason codes
    Does NOT contain:
      - Recipient names, emails, phone numbers
      - Internal obligation IDs
      - Funding account details
      - API credentials
    """
    return {
        "batch_reference": batch_reference,
        "total_obligations": total_obligations,
        "total_by_currency": total_by_currency,
        "eligible_routes": [
            {
                "provider_code": r.get("provider_code"),
                "display_name": r.get("display_name"),
                "environment": r.get("environment"),
                "total_estimated_cost": r.get("total_estimated_cost"),
                "provider_fee": r.get("provider_fee"),
                "fx_spread_cost": r.get("fx_spread_cost"),
                "estimated_processing_hours": r.get("estimated_processing_hours"),
                "quote_label": r.get("quote_label"),
                "warnings": r.get("warnings", []),
            }
            for r in eligible_routes
        ],
        "excluded_routes": [
            {
                "provider_code": r.get("provider_code"),
                "exclusion_reasons": r.get("exclusion_reasons", []),
            }
            for r in excluded_routes
        ],
    }


def _hash_context(context: dict) -> str:
    """SHA-256 of the JSON-serialised context (for audit reproducibility)."""
    raw = json.dumps(context, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fallback helper
# ---------------------------------------------------------------------------

def _make_fallback(
    reason: str,
    eligible_route_codes: list[str],
    model_name: str,
) -> AiAnalysisResult:
    recommended = eligible_route_codes[0] if eligible_route_codes else None
    return AiAnalysisResult(
        summary=(
            "AI assistance is currently unavailable. "
            "Deterministic routing analysis is shown below. "
            "Human review is recommended before proceeding."
        ),
        recommended_route=recommended,
        reasoning_factors=[
            "Fallback to deterministic top-ranked route.",
            "AI was not consulted — see fallback_reason for details.",
        ],
        warnings=["AI service unavailable — results are deterministic only."],
        requires_human_review=True,
        evidence_fields=[],
        fallback_used=True,
        fallback_reason=reason,
        model_name=model_name,
    )


# ---------------------------------------------------------------------------
# Main advisor function
# ---------------------------------------------------------------------------

def analyze_batch(
    batch_reference: str,
    total_obligations: int,
    total_by_currency: dict[str, str],
    eligible_routes: list[dict],
    excluded_routes: list[dict],
    eligible_route_codes: list[str],
) -> tuple[AiAnalysisResult, str]:
    """
    Call the AI for advisory analysis of a batch routing decision.

    Parameters
    ----------
    batch_reference      : Human-readable batch reference (not internal ID).
    total_obligations    : Number of obligations in the batch.
    total_by_currency    : Dict of currency → total amount string.
    eligible_routes      : List of dicts describing eligible provider routes.
    excluded_routes      : List of dicts describing excluded providers.
    eligible_route_codes : List of provider codes from the deterministic engine.
                           AI recommendation MUST be in this list.

    Returns
    -------
    (AiAnalysisResult, input_summary_hash)
    """
    model_name = os.getenv("AI_MODEL", "gemini-3.8-flash")

    # --- Check API key ---
    api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("AI_API_KEY not set — using deterministic fallback")
        ctx = _build_sanitized_context(
            batch_reference, total_obligations, total_by_currency,
            eligible_routes, excluded_routes,
        )
        return _make_fallback("AI_API_KEY not configured", eligible_route_codes, model_name), \
               _hash_context(ctx)

    # --- No eligible routes — nothing for AI to recommend ---
    if not eligible_route_codes:
        ctx = _build_sanitized_context(
            batch_reference, total_obligations, total_by_currency,
            eligible_routes, excluded_routes,
        )
        return AiAnalysisResult(
            summary=(
                "No eligible payment routes were found for this batch. "
                "All providers were excluded by the deterministic eligibility engine. "
                "Human review is required."
            ),
            recommended_route=None,
            reasoning_factors=["No routes passed deterministic eligibility checks."],
            warnings=["All providers excluded — cannot recommend a route."],
            requires_human_review=True,
            evidence_fields=[],
            fallback_used=False,
            fallback_reason=None,
            model_name=model_name,
        ), _hash_context(ctx)

    # --- Build sanitised context ---
    ctx = _build_sanitized_context(
        batch_reference, total_obligations, total_by_currency,
        eligible_routes, excluded_routes,
    )
    input_hash = _hash_context(ctx)

    # --- Construct prompt ---
    prompt = f"""You are a financial operations analyst assistant for PUFI, an enterprise payment
coordination system. Your role is ADVISORY ONLY — you cannot approve, execute, or modify payments.

You have been provided with a deterministic analysis of payment routing options for a batch.
Your task is to explain the options clearly, identify any concerns, and recommend one of the
ELIGIBLE routes provided. You MUST NOT recommend any provider that is not in the eligible list.

BATCH CONTEXT:
{json.dumps(ctx, indent=2, default=str)}

ELIGIBLE PROVIDER CODES (you MUST choose one of these for recommended_route):
{json.dumps(eligible_route_codes)}

Respond with a JSON object matching this exact schema:
{{
  "summary": "<2-3 sentence plain-language explanation of the routing situation>",
  "recommended_route": "<one provider_code from the eligible list above>",
  "reasoning_factors": ["<factor 1>", "<factor 2>", ...],
  "warnings": ["<warning 1>", ...],
  "requires_human_review": <true|false>,
  "evidence_fields": ["<field names from context that influenced the recommendation>"]
}}

RULES:
- recommended_route must be one of: {eligible_route_codes}
- Do NOT invent FX rates, provider fees, or capabilities
- Do NOT approve or execute any payment
- If any route is SIMULATED or SANDBOX, note it clearly in warnings
- If the batch is large or complex, set requires_human_review to true
"""

    # --- Call AI ---
    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text
        if not raw_text:
            raise ValueError("AI returned empty response")

        parsed = json.loads(raw_text)

    except ImportError as exc:
        logger.warning("google-genai not installed: %s", exc)
        return _make_fallback(f"SDK not installed: {exc}", eligible_route_codes, model_name), input_hash

    except Exception as exc:
        logger.warning("AI call failed [%s]: %s", type(exc).__name__, exc)
        return _make_fallback(f"AI call failed: {type(exc).__name__}", eligible_route_codes, model_name), input_hash

    # --- Validate response ---
    try:
        recommended = str(parsed.get("recommended_route", "")).strip()
        if recommended not in eligible_route_codes:
            logger.warning(
                "AI recommended %r which is NOT in eligible routes %r — falling back",
                recommended, eligible_route_codes,
            )
            return _make_fallback(
                f"AI recommended ineligible route: {recommended!r}",
                eligible_route_codes,
                model_name,
            ), input_hash

        result = AiAnalysisResult(
            summary=str(parsed.get("summary", "No summary provided.")),
            recommended_route=recommended,
            reasoning_factors=[str(f) for f in parsed.get("reasoning_factors", [])],
            warnings=[str(w) for w in parsed.get("warnings", [])],
            requires_human_review=bool(parsed.get("requires_human_review", True)),
            evidence_fields=[str(e) for e in parsed.get("evidence_fields", [])],
            fallback_used=False,
            fallback_reason=None,
            model_name=model_name,
        )
        return result, input_hash

    except Exception as exc:
        logger.warning("AI response validation failed: %s", exc)
        return _make_fallback(
            f"Response validation failed: {type(exc).__name__}",
            eligible_route_codes,
            model_name,
        ), input_hash
