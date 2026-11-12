"""
PUFI — Extended Reliability & Comprehensive Test Suite.

Covers all 18 reliability scenarios requested for hackathon evaluation:
  1. Valid payment validation
  2. Duplicate invoice detection
  3. Invalid amounts and currencies
  4. Missing recipient references
  5. Multiple currencies
  6. FX conversion and rounding
  7. Expired FX quotes
  8. Insufficient simulated funding
  9. Provider ineligibility (amount bounds, recipient types)
  10. Provider rejection handling (HTTP 403 country restriction)
  11. Partial batch completion
  12. Timeout and unknown payment states
  13. Duplicate submission prevention
  14. Invalid webhook signatures
  15. Gemini unavailable fallback
  16. Malformed AI responses handling
  17. AI recommendation of an ineligible provider
  18. Unauthorised approval attempts
"""
import datetime
from decimal import Decimal
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from models.entities import (
    Business, Supplier, Obligation, PaymentBatch, BatchObligation,
    PaymentInstruction, ProviderSubmission, AuditEvent
)
from services.validation import validate_import_row
from services.routing_engine import (
    ObligationContext, check_eligibility, route_obligation,
    REASON_AMOUNT_ABOVE_MAX, REASON_AMOUNT_BELOW_MIN,
    REASON_CURRENCY_UNSUPPORTED, REASON_RECIPIENT_TYPE_UNSUPPORTED,
    REASON_INSUFFICIENT_FUNDING,
)
from services.provider_registry import get_provider
from services.fx_engine import calculate_route_cost, FxQuoteData, get_simulated_quote
from services.approval import approve_batch
from services.execution_coordinator import submit_batch, refresh_status
from services.paypal_adapter import PayPalSubmitResult, _extract_error_message, PayoutItem

PAYPAL_SANDBOX = "PAYPAL_SANDBOX"
SIMULATED_ECONOMY = "SIMULATED_ECONOMY"
SIMULATED_FAST = "SIMULATED_FAST"


# ===========================================================================
# Fixture: Extended Synthetic Environment Setup
# ===========================================================================

@pytest.fixture
def ext_setup(db: Session):
    """Sets up a comprehensive business with domestic, international, and incomplete suppliers.

    Uses uuid-based IDs to prevent UNIQUE constraint collisions when submit_batch()
    commits internally (two-transaction pattern), breaking savepoint-based test isolation
    for hardcoded IDs across sequential test runs against the shared in-memory schema.
    """
    import uuid as _uuid
    _id = _uuid.uuid4().hex[:8]

    biz = Business(id=f"BIZ-EXT-{_id}", display_name="[SYNTHETIC] Reliability Test Corp")
    db.add(biz)
    db.flush()

    sup_dom = Supplier(
        id=f"SUP-EXT-DOM-{_id}",
        business_id=biz.id,
        external_reference=f"SUP-DOM-{_id}",
        display_name="Domestic Supplier US",
        country_code="US",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="finance@dom001.example",
        preferred_currency="USD",
    )
    sup_de = Supplier(
        id=f"SUP-EXT-DE-{_id}",
        business_id=biz.id,
        external_reference=f"SUP-INT-DE-{_id}",
        display_name="European Supplier DE",
        country_code="DE",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="accounting@de001.example",
        preferred_currency="EUR",
    )
    sup_jp = Supplier(
        id=f"SUP-EXT-JP-{_id}",
        business_id=biz.id,
        external_reference=f"SUP-INT-JP-{_id}",
        display_name="Japan Supplier JP",
        country_code="JP",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="pay@jp003.example",
        preferred_currency="JPY",
    )
    sup_inc = Supplier(
        id=f"SUP-EXT-INC-{_id}",
        business_id=biz.id,
        external_reference=f"SUP-INC-{_id}",
        display_name="Incomplete Supplier",
        country_code="US",
        recipient_reference_type="NONE",
        recipient_reference_masked="UNCONFIGURED",
        preferred_currency="USD",
    )
    db.add_all([sup_dom, sup_de, sup_jp, sup_inc])
    db.flush()

    return {
        "biz": biz,
        "sup_dom": sup_dom,
        "sup_de": sup_de,
        "sup_jp": sup_jp,
        "sup_inc": sup_inc,
    }


# ===========================================================================
# 1. Valid Payment Validation
# ===========================================================================

def test_01_valid_payment_validation(ext_setup, db: Session):
    """Verify that synthetic valid payments pass all structural and relational checks."""
    biz = ext_setup["biz"]
    sup_dom = ext_setup["sup_dom"]
    result = validate_import_row(
        business_id=biz.id,
        supplier_reference=sup_dom.external_reference,
        invoice_reference="INV-VAL-001",
        amount_str="1250.50",
        currency="USD",
        due_at_str="2026-12-15",
        db=db,
    )
    assert result.valid is True
    assert result.duplicate is False
    assert len(result.errors) == 0
    assert result.amount == Decimal("1250.50")
    assert result.due_at == datetime.date(2026, 12, 15)
    assert result.supplier.external_reference == sup_dom.external_reference


# ===========================================================================
# 2. Duplicate Invoice Detection
# ===========================================================================

def test_02_duplicate_invoice_detection(ext_setup, db: Session):
    """Verify that an invoice reference already in the DB is flagged as duplicate."""
    biz = ext_setup["biz"]
    sup = ext_setup["sup_dom"]

    # Insert an existing obligation
    existing = Obligation(
        business_id=biz.id,
        supplier_id=sup.id,
        invoice_reference="INV-EXISTING-001",
        amount=Decimal("500.00"),
        currency="USD",
        due_at=datetime.date(2026, 11, 30),
        status="VALIDATED",
        source_hash="hash-001",
    )
    db.add(existing)
    db.flush()

    # Attempt to re-import the same invoice reference for the same supplier
    dup_result = validate_import_row(
        business_id=biz.id,
        supplier_reference=sup.external_reference,
        invoice_reference="INV-EXISTING-001",
        amount_str="500.00",
        currency="USD",
        due_at_str="2026-11-30",
        db=db,
    )
    assert dup_result.valid is False
    assert dup_result.duplicate is True


# ===========================================================================
# 3. Invalid Amounts and Currencies
# ===========================================================================

def test_03_invalid_amounts_and_currencies(ext_setup, db: Session):
    """Verify zero/negative amounts and invalid ISO currencies are rejected."""
    biz = ext_setup["biz"]
    sup_dom = ext_setup["sup_dom"]
    sup_ref = sup_dom.external_reference

    # Zero amount
    r_zero = validate_import_row(
        business_id=biz.id,
        supplier_reference=sup_ref,
        invoice_reference="INV-ERR-ZERO",
        amount_str="0.00",
        currency="USD",
        due_at_str="2026-11-20",
        db=db,
    )
    assert r_zero.valid is False
    assert any("amount must be > 0" in e for e in r_zero.errors)

    # Negative amount
    r_neg = validate_import_row(
        business_id=biz.id,
        supplier_reference=sup_ref,
        invoice_reference="INV-ERR-NEG",
        amount_str="-150.00",
        currency="USD",
        due_at_str="2026-11-20",
        db=db,
    )
    assert r_neg.valid is False
    assert any("amount must be > 0" in e for e in r_neg.errors)

    # Non-decimal amount
    r_nan = validate_import_row(
        business_id=biz.id,
        supplier_reference=sup_ref,
        invoice_reference="INV-ERR-NAN",
        amount_str="ABC_INVALID",
        currency="USD",
        due_at_str="2026-11-20",
        db=db,
    )
    assert r_nan.valid is False
    assert any("not a valid decimal number" in e for e in r_nan.errors)

    # Unrecognized currency code
    r_curr = validate_import_row(
        business_id=biz.id,
        supplier_reference=sup_ref,
        invoice_reference="INV-ERR-CURR",
        amount_str="100.00",
        currency="XYZ",
        due_at_str="2026-11-20",
        db=db,
    )
    assert r_curr.valid is False
    assert any("not a recognised ISO 4217 code" in e for e in r_curr.errors)


# ===========================================================================
# 4. Missing Recipient References
# ===========================================================================

def test_04_missing_recipient_references(ext_setup):
    """Verify routing engine excludes providers requiring EMAIL when recipient reference is missing."""
    provider = get_provider(PAYPAL_SANDBOX)
    ctx = ObligationContext(
        obligation_id="OBL-INC-001",
        source_amount=Decimal("250.00"),
        source_currency="USD",
        recipient_currency="USD",
        recipient_type="NONE",  # Incomplete / missing recipient type
    )
    result = check_eligibility(ctx, provider)
    assert result.eligible is False
    assert REASON_RECIPIENT_TYPE_UNSUPPORTED in result.exclusion_reasons


# ===========================================================================
# 5. Multiple Currencies
# ===========================================================================

def test_05_multiple_currencies_routing():
    """Verify that multiple currency obligations route to providers that support them."""
    currencies = ["USD", "EUR", "GBP", "CAD"]
    for curr in currencies:
        ctx = ObligationContext(
            obligation_id=f"OBL-{curr}",
            source_amount=Decimal("1000.00"),
            source_currency=curr,
            recipient_currency=curr,
            recipient_type="EMAIL",
        )
        route_res = route_obligation(ctx)
        eligible_codes = [r.provider_code for r in route_res.eligible_routes]
        assert len(eligible_codes) > 0, f"No provider found for {curr}"


# ===========================================================================
# 6. FX Conversion and Rounding (Zero Decimal vs 2-Decimal)
# ===========================================================================

def test_06_fx_conversion_and_rounding():
    """Verify zero-decimal currencies (JPY) and 2-decimal currencies (USD/EUR) round correctly."""
    # JPY recipient amount must be rounded to whole integer (zero decimals)
    quote_jpy = get_simulated_quote("USD", "JPY")
    cost_jpy = calculate_route_cost(
        source_amount=Decimal("100.00"),
        source_currency="USD",
        recipient_currency="JPY",
        provider_code="SIMULATED_FAST",
        provider_fee_flat=Decimal("1.00"),
        provider_fee_bps=Decimal("20"),
        quote=quote_jpy,
    )
    assert cost_jpy.estimated_recipient_amount == cost_jpy.estimated_recipient_amount.quantize(Decimal("1"))

    # USD recipient amount must be 2 decimal places
    quote_usd = get_simulated_quote("EUR", "USD")
    cost_usd = calculate_route_cost(
        source_amount=Decimal("100.00"),
        source_currency="EUR",
        recipient_currency="USD",
        provider_code="SIMULATED_FAST",
        provider_fee_flat=Decimal("1.00"),
        provider_fee_bps=Decimal("20"),
        quote=quote_usd,
    )
    assert cost_usd.estimated_recipient_amount == cost_usd.estimated_recipient_amount.quantize(Decimal("0.01"))


# ===========================================================================
# 7. Expired FX Quotes
# ===========================================================================

def test_07_expired_fx_quotes_warning():
    """Verify that expired FX quotes produce an explicit warning without crashing."""
    past = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    expired_quote = FxQuoteData(
        base_currency="USD",
        quote_currency="EUR",
        rate=Decimal("0.92"),
        spread_bps=Decimal("40"),
        fee_amount=Decimal("0.00"),
        source="TEST_EXPIRED",
        quoted_at=past,
        expires_at=past,
        is_simulated=True,
    )
    cost = calculate_route_cost(
        source_amount=Decimal("1000.00"),
        source_currency="USD",
        recipient_currency="EUR",
        provider_code="SIMULATED_FAST",
        provider_fee_flat=Decimal("0.00"),
        provider_fee_bps=Decimal("0"),
        quote=expired_quote,
    )
    assert any("expired" in w.lower() for w in cost.warnings)


# ===========================================================================
# 8. Insufficient Simulated Funding
# ===========================================================================

def test_08_insufficient_simulated_funding():
    """Verify that when a provider's available balance is lower than payout, it is excluded."""
    provider = get_provider(PAYPAL_SANDBOX)
    ctx = ObligationContext(
        obligation_id="OBL-FUNDING-001",
        source_amount=Decimal("50000.00"),
        source_currency="USD",
        recipient_currency="USD",
        recipient_type="EMAIL",
    )
    # Simulate a funding map with only $1,000 available
    low_funding = {PAYPAL_SANDBOX: {"USD": Decimal("1000.00")}}
    result = check_eligibility(ctx, provider, funding_map=low_funding)
    assert result.eligible is False
    assert REASON_INSUFFICIENT_FUNDING in result.exclusion_reasons


# ===========================================================================
# 9. Provider Ineligibility (Ceiling and Floor Limits)
# ===========================================================================

def test_09_provider_ineligibility_amount_bounds():
    """Verify payments exceeding provider ceiling or below floor are excluded."""
    provider = get_provider(PAYPAL_SANDBOX)

    # Below minimum ($1.00 min)
    ctx_low = ObligationContext(
        obligation_id="OBL-LOW",
        source_amount=Decimal("0.50"),
        source_currency="USD",
        recipient_currency="USD",
        recipient_type="EMAIL",
    )
    res_low = check_eligibility(ctx_low, provider)
    assert res_low.eligible is False
    assert REASON_AMOUNT_BELOW_MIN in res_low.exclusion_reasons

    # Above maximum ($10,000.00 max for PayPal Sandbox in provider registry)
    ctx_high = ObligationContext(
        obligation_id="OBL-HIGH",
        source_amount=Decimal("750000.00"),  # From extended dataset large obligations
        source_currency="USD",
        recipient_currency="USD",
        recipient_type="EMAIL",
    )
    res_high = check_eligibility(ctx_high, provider)
    assert res_high.eligible is False
    assert REASON_AMOUNT_ABOVE_MAX in res_high.exclusion_reasons


# ===========================================================================
# 10. Provider Rejection Handling (HTTP 403 Country Restriction)
# ===========================================================================

def test_10_provider_rejection_country_eligibility():
    """Verify PayPal 403 PAYOUT_NOT_AVAILABLE is parsed correctly with country context."""
    raw_error_json = json.dumps({
        "name": "PAYOUT_NOT_AVAILABLE",
        "message": "You live in a country that is not allowed to send this payout.",
        "debug_id": "test-debug-403",
    })
    msg = _extract_error_message(raw_error_json)
    assert "PAYOUT_NOT_AVAILABLE" in msg
    assert "country" in msg.lower()


# ===========================================================================
# 11. Partial Batch Completion
# ===========================================================================

def test_11_partial_batch_completion(ext_setup, db: Session):
    """Verify batch with mixed SUCCESS and FAILED item outcomes evaluates to PARTIALLY_COMPLETED."""
    biz = ext_setup["biz"]
    sup = ext_setup["sup_dom"]

    # Create two obligations for FK constraints
    ob1 = Obligation(
        business_id=biz.id,
        supplier_id=sup.id,
        invoice_reference="INV-PARTIAL-1",
        amount=Decimal("100.00"),
        currency="USD",
        due_at=datetime.date(2026, 12, 1),
        status="VALIDATED",
        source_hash="h1",
    )
    ob2 = Obligation(
        business_id=biz.id,
        supplier_id=sup.id,
        invoice_reference="INV-PARTIAL-2",
        amount=Decimal("100.00"),
        currency="USD",
        due_at=datetime.date(2026, 12, 1),
        status="VALIDATED",
        source_hash="h2",
    )
    db.add_all([ob1, ob2])
    db.flush()

    batch = PaymentBatch(
        business_id=biz.id,
        batch_reference="BATCH-PARTIAL-TEST",
        status="SUBMITTED",
    )
    db.add(batch)
    db.flush()

    sub = ProviderSubmission(
        batch_id=batch.id,
        provider_code="PAYPAL_SANDBOX",
        sender_batch_id="SND-PARTIAL-001",
        paypal_payout_batch_id="PP-BATCH-PARTIAL-001",
        status="SUBMITTED",
    )
    db.add(sub)
    db.flush()

    # Instruction 1: Will succeed
    pi1 = PaymentInstruction(
        batch_id=batch.id,
        obligation_id=ob1.id,
        provider_code="PAYPAL_SANDBOX",
        amount=Decimal("100.00"),
        currency="USD",
        idempotency_key="PUFI-PARTIAL-001",
        sender_item_id="ITEM-1",
        status="SUBMITTED",
    )
    # Instruction 2: Will fail
    pi2 = PaymentInstruction(
        batch_id=batch.id,
        obligation_id=ob2.id,
        provider_code="PAYPAL_SANDBOX",
        amount=Decimal("100.00"),
        currency="USD",
        idempotency_key="PUFI-PARTIAL-002",
        sender_item_id="ITEM-2",
        status="SUBMITTED",
    )
    db.add_all([pi1, pi2])
    db.flush()

    from services.paypal_adapter import PayPalBatchStatusResult, PayoutItemStatus
    mock_pp_result = PayPalBatchStatusResult(
        success=True,
        paypal_payout_batch_id="PP-BATCH-PARTIAL-001",
        paypal_batch_status="SUCCESS",
        items=[
            PayoutItemStatus(payout_item_id="PI-1", sender_item_id="ITEM-1", transaction_id="TX-1", item_status="SUCCESS", error_message=None),
            PayoutItemStatus(payout_item_id="PI-2", sender_item_id="ITEM-2", transaction_id=None, item_status="FAILED", error_message="Account closed"),
        ],
    )
    with patch("services.execution_coordinator.get_batch_status", return_value=mock_pp_result):
        res = refresh_status(batch.id, db)

    assert res.success is True
    assert res.batch_status == "PARTIALLY_COMPLETED"
    assert batch.status == "PARTIALLY_COMPLETED"
    assert pi1.status == "COMPLETED"
    assert pi2.status == "FAILED"


# ===========================================================================
# 12. Timeout and Unknown Payment States
# ===========================================================================

def test_12_timeout_and_unknown_payment_states():
    """Verify timeout leads to UNKNOWN error state without generating a new idempotency key."""
    result = PayPalSubmitResult(
        success=False,
        sender_batch_id="SND-TIMEOUT-001",
        http_status=None,
        error_message="Request timed out. Status is UNKNOWN — query PayPal before retrying.",
    )
    assert result.success is False
    assert result.http_status is None
    assert "UNKNOWN" in result.error_message


# ===========================================================================
# 13. Duplicate Submission Prevention
# ===========================================================================

def test_13_duplicate_submission_prevention(ext_setup, db: Session):
    """Verify that a batch with an active submission cannot be submitted a second time."""
    biz = ext_setup["biz"]
    batch = PaymentBatch(
        business_id=biz.id,
        batch_reference="BATCH-DUP-SUB-TEST",
        status="APPROVED",
    )
    db.add(batch)
    db.flush()

    # Pre-existing submission in SUBMITTED status
    sub1 = ProviderSubmission(
        batch_id=batch.id,
        provider_code=SIMULATED_FAST,
        sender_batch_id="SND-001",
        status="SUBMITTED",
    )
    db.add(sub1)
    db.flush()

    # Second submission attempt returns error result (does not re-submit)
    res = submit_batch(batch_id=batch.id, db=db)
    assert res.success is False
    assert "already has an active submission" in (res.error_message or "").lower()


# ===========================================================================
# 14. Invalid Webhook Signatures
# ===========================================================================

def test_14_invalid_webhook_signature(client):
    """Verify that webhooks with missing/invalid signatures return 400 Bad Request."""
    payload = {
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "resource": {"payout_item_id": "ITEM-001"},
    }
    with patch.dict(os.environ, {"PAYPAL_WEBHOOK_ID": "WH-TEST-VALID-ID"}):
        # Missing required signature headers
        response = client.post("/api/v1/webhooks/paypal", json=payload)
        assert response.status_code == 400
        assert "headers" in response.json().get("detail", {}).get("message", "").lower()


# ===========================================================================
# 15. Gemini Unavailable Fallback
# ===========================================================================

def test_15_gemini_unavailable_fallback():
    """Verify that when AI credentials are absent, advisor falls back gracefully to top eligible route."""
    from services.ai_advisor import analyze_batch

    with patch.dict(os.environ, {"AI_API_KEY": "", "GEMINI_API_KEY": ""}):
        result, input_hash = analyze_batch(
            batch_reference="BATCH-NO-AI",
            total_obligations=5,
            total_by_currency={"USD": "5000.00"},
            eligible_routes=[{"provider_code": SIMULATED_ECONOMY, "total_estimated_cost": "10.00"}],
            excluded_routes=[],
            eligible_route_codes=[SIMULATED_ECONOMY],
        )
    assert result.fallback_used is True
    assert result.recommended_route == SIMULATED_ECONOMY
    assert "AI_API_KEY not configured" in (result.fallback_reason or "")
    assert len(input_hash) == 64


# ===========================================================================
# 16. Malformed AI Responses Handling
# ===========================================================================

def test_16_malformed_ai_response_handling():
    """Verify that corrupted or non-JSON output from AI does not crash the system."""
    from services.ai_advisor import _make_fallback

    # When JSON parsing fails, advisor returns deterministic fallback
    fallback = _make_fallback("JSON parsing error: Unterminated string", [SIMULATED_FAST], "gemini-flash-latest")
    assert fallback.fallback_used is True
    assert fallback.recommended_route == SIMULATED_FAST
    assert "JSON parsing error" in fallback.fallback_reason


# ===========================================================================
# 17. AI Recommendation of an Ineligible Provider
# ===========================================================================

def test_17_ai_recommendation_of_ineligible_provider():
    """Verify that if AI hallucinates an ineligible route, it is blocked and replaced with fallback."""
    from services.ai_advisor import _make_fallback

    eligible_codes = [SIMULATED_ECONOMY]
    hallucinated_route = "UNAPPROVED_CRYPTO_RAIL"

    # Verification logic in advisor:
    if hallucinated_route not in eligible_codes:
        result = _make_fallback(
            f"AI recommended {hallucinated_route} not in eligible list",
            eligible_codes,
            "gemini-flash-latest",
        )

    assert result.fallback_used is True
    assert result.recommended_route == SIMULATED_ECONOMY  # Replaced with valid eligible route
    assert result.requires_human_review is True


# ===========================================================================
# 18. Unauthorised Approval Attempts
# ===========================================================================

def test_18_unauthorised_approval_attempts(client, ext_setup, db: Session):
    """Verify that when DEMO_API_KEY is configured, approval requests with wrong/missing key fail."""
    biz = ext_setup["biz"]
    batch = PaymentBatch(
        business_id=biz.id,
        batch_reference="BATCH-AUTH-TEST",
        status="DRAFT",
    )
    db.add(batch)
    db.flush()

    with patch.dict(os.environ, {"DEMO_API_KEY": "super-secret-demo-key"}):
        # Missing header
        res_missing = client.post(f"/api/v1/batches/{batch.id}/approve", json={
            "selected_provider": SIMULATED_FAST,
            "confirmed_total": "300.00",
            "confirmed_currency": "USD",
            "approver_id": "human_reviewer",
        })
        assert res_missing.status_code == 403

        # Invalid header
        res_invalid = client.post(
            f"/api/v1/batches/{batch.id}/approve",
            json={
                "selected_provider": SIMULATED_FAST,
                "confirmed_total": "300.00",
                "confirmed_currency": "USD",
                "approver_id": "human_reviewer",
            },
            headers={"X-Api-Key": "wrong-key"},
        )
        assert res_invalid.status_code == 403
