"""
PUFI — Pydantic schemas for Obligation and Batch API responses.

Design rules:
  - Monetary amounts are returned as strings to preserve Decimal precision.
  - Currency codes are uppercase ISO 4217 strings (e.g. "USD").
  - Dates are returned as ISO 8601 strings (YYYY-MM-DD).
  - UUIDs are returned as strings.
  - No internal implementation details (ORM types, DB columns) leak here.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_serializer, field_validator


# ===========================================================================
# Shared / existing schemas
# ===========================================================================

class SupplierSummary(BaseModel):
    """Minimal supplier information embedded in obligation responses."""
    id: str
    external_reference: str
    display_name: str
    country_code: str

    model_config = {"from_attributes": True}


class ObligationOut(BaseModel):
    """
    Full obligation representation returned by the API.
    amount is serialized as a string to avoid floating-point representation issues.
    """
    id: str
    invoice_reference: str
    amount: Decimal
    currency: str
    due_at: date
    status: str
    notes: Optional[str]
    created_at: datetime
    supplier: SupplierSummary

    model_config = {"from_attributes": True}

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal, _info) -> str:
        """Return amount as a fixed-decimal string, e.g. '1250.0000'."""
        return str(value)

    @field_serializer("due_at")
    def serialize_due_at(self, value: date, _info) -> str:
        return value.isoformat()

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime, _info) -> str:
        return value.isoformat()


class ObligationListResponse(BaseModel):
    """Paginated list of obligations."""
    items: list[ObligationOut]
    total: int
    limit: int
    offset: int
    correlation_id: str


# ===========================================================================
# Day 2: Import schemas
# ===========================================================================

class ObligationImportRow(BaseModel):
    """
    One row in a JSON import payload.

    All amounts arrive as strings to avoid float precision issues in transit.
    The API normalises them to Decimal before validation.
    """
    supplier_reference: str = Field(..., description="Supplier external_reference (e.g. SUP-001)")
    invoice_reference: str = Field(..., description="Invoice identifier (e.g. INV-2026-999)")
    amount: str = Field(..., description="Amount as a string (e.g. '1250.00')")
    currency: str = Field(..., description="ISO 4217 currency code (e.g. 'USD')")
    due_at: str = Field(..., description="Due date in YYYY-MM-DD format")
    notes: Optional[str] = Field(default=None)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("supplier_reference", "invoice_reference")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ImportResultStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    INVALID = "INVALID"


class ImportRowResult(BaseModel):
    """Result for a single row in an import batch."""
    row_index: int
    invoice_reference: str
    supplier_reference: str
    status: ImportResultStatus
    reason: Optional[str] = None
    obligation_id: Optional[str] = None  # set only when ACCEPTED


class ImportResponse(BaseModel):
    """Response from POST /obligations/import."""
    total_rows: int
    accepted: int
    duplicate: int
    invalid: int
    results: list[ImportRowResult]
    correlation_id: str


# ===========================================================================
# Day 2: Batch schemas
# ===========================================================================

class BatchCreateRequest(BaseModel):
    """Request body for POST /batches."""
    batch_reference: str = Field(..., description="Human-readable batch name (e.g. BATCH-2026-001)")
    obligation_ids: list[str] = Field(..., min_length=1, description="List of VALIDATED obligation IDs")
    notes: Optional[str] = None


class BatchObligationSummary(BaseModel):
    """Obligation summary embedded in batch detail responses."""
    obligation_id: str
    invoice_reference: str
    amount: str         # already serialized as string
    currency: str
    supplier_name: str
    added_at: datetime

    @field_serializer("added_at")
    def serialize_added_at(self, value: datetime, _info) -> str:
        return value.isoformat()


class BatchOut(BaseModel):
    """Batch detail response."""
    id: str
    batch_reference: str
    status: str
    notes: Optional[str]
    created_at: datetime
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    obligation_count: int
    obligations: list[BatchObligationSummary]

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime, _info) -> str:
        return value.isoformat()

    @field_serializer("approved_at")
    def serialize_approved_at(self, value: Optional[datetime], _info) -> Optional[str]:
        return value.isoformat() if value else None
