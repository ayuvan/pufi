"""
PUFI — Obligation validation service (Day 2).

Validates individual import rows against business rules.
This module is deterministic — no AI, no network calls.

Rules applied (in order):
  1. Required fields present and non-empty.
  2. Amount parseable as Decimal and > 0.
  3. Currency is a recognised ISO 4217 code.
  4. due_at is a valid YYYY-MM-DD date.
  5. supplier_reference resolves to a known Supplier in the DB.
  6. (business_id, invoice_reference, supplier_id) is not already stored.

Returns a ValidationResult for each row.  The caller decides what to persist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from models.entities import Obligation, Supplier


# ---------------------------------------------------------------------------
# ISO 4217 currency allowlist
# ---------------------------------------------------------------------------

VALID_ISO_4217: frozenset[str] = frozenset({
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY",
    "HKD", "NZD", "SEK", "KRW", "SGD", "NOK", "MXN", "INR",
    "RUB", "ZAR", "TRY", "BRL", "TWD", "DKK", "PLN", "THB",
    "IDR", "HUF", "CZK", "ILS", "CLP", "PHP", "AED", "COP",
    "SAR", "MYR", "RON",
})


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    Outcome of validating one import row.

    Fields:
      valid     — True only when ALL checks passed and the row is not a duplicate.
      duplicate — True when the business key already exists in the DB.
                  A duplicate is NOT an error; it is a detected re-import.
      errors    — Human-readable list of validation problems (empty when valid=True).
      amount    — Parsed Decimal amount (None if parsing failed).
      due_at    — Parsed date (None if parsing failed).
      supplier  — Resolved Supplier ORM object (None if not found).
    """
    valid: bool = False
    duplicate: bool = False
    errors: list[str] = field(default_factory=list)
    amount: Optional[Decimal] = None
    due_at: Optional[date] = None
    supplier: Optional[Supplier] = None


# ---------------------------------------------------------------------------
# Validation function
# ---------------------------------------------------------------------------

def validate_import_row(
    *,
    business_id: str,
    supplier_reference: str,
    invoice_reference: str,
    amount_str: str,
    currency: str,
    due_at_str: str,
    db: Session,
) -> ValidationResult:
    """
    Validate one import row against business rules.

    Parameters are already stripped / uppercased by the Pydantic schema.
    Returns a ValidationResult; never raises.
    """
    result = ValidationResult()
    errors: list[str] = []

    # --- 1. Required field presence ---
    if not supplier_reference:
        errors.append("supplier_reference is required")
    if not invoice_reference:
        errors.append("invoice_reference is required")
    if not amount_str:
        errors.append("amount is required")
    if not currency:
        errors.append("currency is required")
    if not due_at_str:
        errors.append("due_at is required")

    # Abort early if any required field is missing — remaining checks would be meaningless
    if errors:
        result.errors = errors
        return result

    # --- 2. Amount: parseable Decimal > 0 ---
    try:
        amount = Decimal(amount_str)
        if amount <= Decimal("0"):
            errors.append(f"amount must be > 0 (got {amount_str!r})")
        else:
            result.amount = amount
    except InvalidOperation:
        errors.append(f"amount is not a valid decimal number (got {amount_str!r})")

    # --- 3. Currency: ISO 4217 allowlist ---
    if currency not in VALID_ISO_4217:
        errors.append(
            f"currency {currency!r} is not a recognised ISO 4217 code. "
            f"Note: PayPal Payouts does not support all currencies — "
            f"eligibility is checked at routing time."
        )

    # --- 4. Date: YYYY-MM-DD ---
    try:
        result.due_at = date.fromisoformat(due_at_str)
    except (ValueError, TypeError):
        errors.append(f"due_at must be YYYY-MM-DD (got {due_at_str!r})")

    # --- 5. Supplier lookup ---
    supplier = (
        db.query(Supplier)
        .filter(
            Supplier.business_id == business_id,
            Supplier.external_reference == supplier_reference,
        )
        .first()
    )
    if supplier is None:
        errors.append(
            f"supplier_reference {supplier_reference!r} not found for this business"
        )
    else:
        result.supplier = supplier

    # Bail out if any structural errors found — duplicate check requires supplier
    if errors:
        result.errors = errors
        return result

    # --- 6. Duplicate check: (business_id, invoice_reference, supplier_id) ---
    existing = (
        db.query(Obligation)
        .filter(
            Obligation.business_id == business_id,
            Obligation.invoice_reference == invoice_reference,
            Obligation.supplier_id == result.supplier.id,  # type: ignore[union-attr]
        )
        .first()
    )
    if existing is not None:
        result.duplicate = True
        return result  # duplicate: not an error, but not accepted either

    # All checks passed
    result.valid = True
    return result
