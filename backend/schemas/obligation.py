"""
PUFI — Pydantic schemas for Obligation API responses.

Design rules:
  - Monetary amounts are returned as strings to preserve Decimal precision.
  - Currency codes are uppercase ISO 4217 strings (e.g. "USD").
  - Dates are returned as ISO 8601 strings (YYYY-MM-DD).
  - UUIDs are returned as strings.
  - No internal implementation details (ORM types, DB columns) leak here.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_serializer


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
