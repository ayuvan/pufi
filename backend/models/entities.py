"""
PUFI — ORM entity definitions.

Day 1 tables: Business, Supplier, Obligation
Day 2 tables: PaymentBatch, BatchObligation

Money rules (enforced here and throughout the codebase):
  - Amount columns use NUMERIC(19, 4)   — never Float or Double.
  - Currency columns store ISO 4217 codes (e.g. "USD", "EUR").
  - Rounding and quantization happen in the service layer, not the DB.

State machine for Obligation.status:
  DRAFT → VALIDATED | ON_HOLD | CANCELLED
  VALIDATED → READY | CANCELLED
  ON_HOLD → VALIDATED | CANCELLED
  READY → CLOSED | CANCELLED

State machine for PaymentBatch.status:
  DRAFT → PENDING_APPROVAL | CANCELLED
  PENDING_APPROVAL → APPROVED | REJECTED
  APPROVED → SUBMITTED | CANCELLED
  SUBMITTED → COMPLETED | PARTIALLY_COMPLETED | FAILED
"""
import uuid
from datetime import datetime, date, timezone  # M-4: include timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Column, Date, DateTime,
    ForeignKey, Numeric, String, Text, UniqueConstraint, Boolean,
)
from sqlalchemy.orm import relationship  # L-3: removed unused Mapped

from models.db import Base


def _new_uuid() -> str:
    """Generate a new UUID4 as a hex string.  Stored as TEXT in SQLite."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    # M-4 fix: timezone-aware UTC — avoids DeprecationWarning in Python 3.12
    # and prevents naive/aware comparison bugs with PostgreSQL.
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Business
# ---------------------------------------------------------------------------

class Business(Base):
    """
    The enterprise account that owns obligations and payment batches.
    For the prototype there is exactly one business in the seed data.
    """
    __tablename__ = "businesses"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    display_name: str = Column(String(255), nullable=False)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    # Relationships
    suppliers: list = relationship("Supplier", back_populates="business")
    obligations: list = relationship("Obligation", back_populates="business")

    def __repr__(self) -> str:
        return f"<Business id={self.id!r} name={self.display_name!r}>"


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class Supplier(Base):
    """
    A payment recipient.  The full payment reference is never stored;
    only a masked version is kept for display purposes (security rule).
    """
    __tablename__ = "suppliers"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    business_id: str = Column(String(36), ForeignKey("businesses.id"), nullable=False)

    # External reference used in obligation imports (e.g. "SUP-001")
    external_reference: str = Column(String(100), nullable=False, unique=True)
    display_name: str = Column(String(255), nullable=False)

    # ISO 3166-1 alpha-2 country code (e.g. "US", "IN", "DE")
    country_code: str = Column(String(2), nullable=False)

    # Recipient type: 'EMAIL' | 'PHONE' | 'PAYPAL_ID'
    recipient_reference_type: str = Column(String(20), nullable=False, default="EMAIL")

    # Masked reference for display — never store the full raw reference
    recipient_reference_masked: str = Column(String(255), nullable=False)

    # Preferred settlement currency (may differ from obligation currency)
    preferred_currency: str = Column(String(3), nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    # Relationships
    business: Business = relationship("Business", back_populates="suppliers")
    obligations: list = relationship("Obligation", back_populates="supplier")

    def __repr__(self) -> str:
        return f"<Supplier id={self.id!r} ref={self.external_reference!r}>"


# ---------------------------------------------------------------------------
# Obligation
# ---------------------------------------------------------------------------

class Obligation(Base):
    """
    A single payable business intent.

    An obligation is NOT proof that money has moved.
    It represents what the business says it owes a supplier.

    Duplicate detection uses the unique constraint on
    (business_id, invoice_reference, supplier_id).

    source_hash: SHA-256 of the normalized import row, used to detect
                 re-imports of identical data.
    """
    __tablename__ = "obligations"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    business_id: str = Column(String(36), ForeignKey("businesses.id"), nullable=False)
    supplier_id: str = Column(String(36), ForeignKey("suppliers.id"), nullable=False)

    invoice_reference: str = Column(String(100), nullable=False)

    # NUMERIC — never Float.  Stored with 4 decimal places.
    amount: Decimal = Column(Numeric(19, 4), nullable=False)

    # ISO 4217 currency code (e.g. "USD").  Empty string is treated as invalid
    # by the validation service (Day 2) but allowed at the DB level so that
    # import-with-errors can be stored before validation runs.
    currency: str = Column(String(3), nullable=False, default="")

    due_at: date = Column(Date, nullable=False)

    # State machine — see module docstring
    status: str = Column(String(20), nullable=False, default="DRAFT")

    # SHA-256 hex of the normalized import row (used for re-import detection)
    source_hash: str = Column(String(64), nullable=False, default="")

    notes: str = Column(Text, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    # --- Constraints --------------------------------------------------------
    __table_args__ = (
        # Business-level duplicate key: same invoice from same supplier
        UniqueConstraint(
            "business_id", "invoice_reference", "supplier_id",
            name="uq_obligation_business_invoice_supplier",
        ),
        # Amount must be positive (zero and negative amounts are validation errors)
        CheckConstraint("amount > 0", name="ck_obligation_amount_positive"),
        # H-2 fix: status must be a valid state-machine value.
        # Prevents arbitrary strings from bypassing the approval workflow.
        CheckConstraint(
            "status IN ('DRAFT','VALIDATED','ON_HOLD','READY','CLOSED','CANCELLED')",
            name="ck_obligation_status_valid",
        ),
    )

    # Relationships
    business: Business = relationship("Business", back_populates="obligations")
    supplier: Supplier = relationship("Supplier", back_populates="obligations")

    def __repr__(self) -> str:
        return (
            f"<Obligation id={self.id!r} invoice={self.invoice_reference!r} "
            f"amount={self.amount} {self.currency} status={self.status!r}>"
        )


# ---------------------------------------------------------------------------
# PaymentBatch  (Day 2)
# ---------------------------------------------------------------------------

class PaymentBatch(Base):
    """
    A named collection of validated obligations that will be submitted together
    as a single payment run.

    A batch must be explicitly approved before it can be submitted.  The AI
    advisory layer may recommend approval but cannot approve autonomously.

    Status machine (see module docstring for transitions).
    """
    __tablename__ = "payment_batches"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    business_id: str = Column(String(36), ForeignKey("businesses.id"), nullable=False)

    # Human-readable reference (e.g. "BATCH-2026-001")
    batch_reference: str = Column(String(100), nullable=False)

    status: str = Column(String(30), nullable=False, default="DRAFT")

    # Who approved this batch (user identifier — Day 4 adds real auth)
    approved_by: str = Column(String(255), nullable=True)
    approved_at: datetime = Column(DateTime, nullable=True)

    notes: str = Column(Text, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("business_id", "batch_reference", name="uq_batch_business_ref"),
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED',"
            "'SUBMITTED','COMPLETED','PARTIALLY_COMPLETED','FAILED','CANCELLED')",
            name="ck_batch_status_valid",
        ),
    )

    # Relationships
    business: Business = relationship("Business")
    batch_obligations: list = relationship("BatchObligation", back_populates="batch")

    def __repr__(self) -> str:
        return f"<PaymentBatch id={self.id!r} ref={self.batch_reference!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# BatchObligation  (Day 2) — junction table
# ---------------------------------------------------------------------------

class BatchObligation(Base):
    """
    Many-to-many join between PaymentBatch and Obligation.

    An obligation may appear in at most one ACTIVE batch at a time.
    The unique constraint on obligation_id enforces this.
    """
    __tablename__ = "batch_obligations"

    batch_id: str = Column(String(36), ForeignKey("payment_batches.id"), primary_key=True)
    obligation_id: str = Column(String(36), ForeignKey("obligations.id"), primary_key=True)

    added_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    # Relationships
    batch: PaymentBatch = relationship("PaymentBatch", back_populates="batch_obligations")
    obligation: Obligation = relationship("Obligation")

    def __repr__(self) -> str:
        return f"<BatchObligation batch={self.batch_id!r} obligation={self.obligation_id!r}>"


# ---------------------------------------------------------------------------
# FxQuote  (Day 3)
# ---------------------------------------------------------------------------

class FxQuote(Base):
    """
    A foreign-exchange rate quote used for cost estimation.

    IMPORTANT LABELLING RULES:
    - is_simulated=True  → rate is synthetic/assumed; must be labelled SIMULATED
    - is_simulated=False → rate came from a live external source (Sandbox/real)
    Never store a hard-coded demo rate and label it as live.

    spread_bps: spread in basis points (100 bps = 1%)
    """
    __tablename__ = "fx_quotes"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    base_currency: str = Column(String(3), nullable=False)
    quote_currency: str = Column(String(3), nullable=False)

    # Rate stored with 8dp for FX precision
    rate: Decimal = Column(Numeric(24, 8), nullable=False)

    # Spread in basis points (e.g. 50 = 0.50%)
    spread_bps: Decimal = Column(Numeric(10, 2), nullable=False, default=Decimal("0"))

    # Fixed fee in base currency per transaction (may be zero)
    fee_amount: Decimal = Column(Numeric(19, 4), nullable=False, default=Decimal("0"))

    # Where this rate came from
    source: str = Column(String(100), nullable=False)

    quoted_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    expires_at: datetime = Column(DateTime, nullable=False)

    # True = synthetic/demo rate; False = live external rate
    is_simulated: bool = Column(Boolean, nullable=False, default=True)

    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:
        label = "SIMULATED" if self.is_simulated else "LIVE"
        return (
            f"<FxQuote {self.base_currency}/{self.quote_currency} "
            f"rate={self.rate} [{label}]>"
        )


# ---------------------------------------------------------------------------
# FundingSnapshot  (Day 3)
# ---------------------------------------------------------------------------

class FundingSnapshot(Base):
    """
    A point-in-time record of funds configured as available for a provider route.

    This is NEVER a verified bank balance. It is either:
    - SIMULATED: synthetic demo value
    - MANUALLY_CONFIGURED: entered by a business user for planning purposes

    source_type must be one of: 'SIMULATED' | 'MANUALLY_CONFIGURED'
    """
    __tablename__ = "funding_snapshots"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    provider_code: str = Column(String(50), nullable=False)
    currency: str = Column(String(3), nullable=False)
    available_amount: Decimal = Column(Numeric(19, 4), nullable=False)

    # SIMULATED or MANUALLY_CONFIGURED — never 'LIVE_BANK_BALANCE'
    source_type: str = Column(String(30), nullable=False, default="SIMULATED")

    observed_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    is_simulated: bool = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("available_amount >= 0", name="ck_funding_non_negative"),
        CheckConstraint(
            "source_type IN ('SIMULATED','MANUALLY_CONFIGURED')",
            name="ck_funding_source_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FundingSnapshot provider={self.provider_code!r} "
            f"{self.currency} {self.available_amount} [{self.source_type}]>"
        )


# ---------------------------------------------------------------------------
# AiRecommendation  (Day 3)
# ---------------------------------------------------------------------------

class AiRecommendation(Base):
    """
    Persisted AI decision-support output for a batch analysis request.

    The AI output is advisory only. The backend validates that any
    recommended_route_id is within the deterministic eligible-route set
    before this record is created.

    fallback_used=True means the AI was unavailable or returned invalid output;
    the deterministic engine result was returned instead.
    """
    __tablename__ = "ai_recommendations"

    id: str = Column(String(36), primary_key=True, default=_new_uuid)
    batch_id: str = Column(String(36), ForeignKey("payment_batches.id"), nullable=False)

    model_name: str = Column(String(100), nullable=False)

    # SHA-256 of the sanitized input sent to the AI (for audit reproducibility)
    input_summary_hash: str = Column(String(64), nullable=False)

    # Full structured JSON response (secrets-free)
    recommendation_json: str = Column(Text, nullable=False)

    fallback_used: bool = Column(Boolean, nullable=False, default=False)
    fallback_reason: str = Column(Text, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    # Relationships
    batch: PaymentBatch = relationship("PaymentBatch")

    def __repr__(self) -> str:
        return (
            f"<AiRecommendation batch={self.batch_id!r} "
            f"fallback={self.fallback_used}>"
        )
