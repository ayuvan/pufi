"""
PUFI — Day 1 / Day 2 test suite.

Tests are grouped by concern:
  1. Monetary precision (Decimal, NUMERIC, JSON serialisation)
  2. Database constraints (amount > 0, unique key, status CHECK)
  3. API endpoints (health, obligations list, pagination, filters)
  4. Seed idempotency
  5. State machine (valid/invalid transitions at DB level)

All tests use the in-memory SQLite DB from conftest.py — no dev DB touched.
"""
import pytest
from decimal import Decimal
from datetime import date

from sqlalchemy.exc import IntegrityError


# ===========================================================================
# 1. Monetary precision
# ===========================================================================

class TestDecimalPrecision:
    def test_decimal_stored_and_retrieved(self, seeded_db, db):
        """Amount stored as Decimal must be returned as Decimal from SQLAlchemy."""
        ob = seeded_db["ob1"]
        db.refresh(ob)
        assert isinstance(ob.amount, Decimal), (
            f"Expected Decimal from DB, got {type(ob.amount).__name__}"
        )

    def test_amount_exact_value_preserved(self, seeded_db, db):
        """The stored amount must equal the original value with 4dp precision."""
        ob = seeded_db["ob2"]
        db.refresh(ob)
        # 500.5000 must round-trip exactly — no float rounding
        assert ob.amount == Decimal("500.5000")

    def test_amount_serialized_as_string_in_api(self, client, seeded_db):
        """
        The obligations API must return 'amount' as a JSON string, not a number.
        A JSON number cannot represent Decimal precision without float conversion.
        """
        resp = client.get("/api/v1/obligations")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        for item in items:
            assert isinstance(item["amount"], str), (
                f"amount must be a string but got {type(item['amount']).__name__}: {item['amount']!r}"
            )


# ===========================================================================
# 2. Database constraints
# ===========================================================================

class TestDatabaseConstraints:
    def test_zero_amount_rejected_by_db(self, seeded_db, db):
        """amount=0 must raise IntegrityError (ck_obligation_amount_positive)."""
        from models.entities import Obligation
        with pytest.raises(IntegrityError):
            ob = Obligation(
                business_id="BIZ-TEST-001",
                supplier_id="SUP-TEST-A",
                invoice_reference="INV-ZERO",
                amount=Decimal("0.00"),
                currency="USD",
                due_at=date(2026, 12, 1),
                status="DRAFT",
                source_hash="zero-hash",
            )
            db.add(ob)
            db.flush()

    def test_negative_amount_rejected_by_db(self, seeded_db, db):
        """Negative amounts must be rejected by the amount > 0 check constraint."""
        from models.entities import Obligation
        with pytest.raises(IntegrityError):
            ob = Obligation(
                business_id="BIZ-TEST-001",
                supplier_id="SUP-TEST-A",
                invoice_reference="INV-NEG",
                amount=Decimal("-0.01"),
                currency="USD",
                due_at=date(2026, 12, 1),
                status="DRAFT",
                source_hash="neg-hash",
            )
            db.add(ob)
            db.flush()

    def test_unique_constraint_rejects_duplicate(self, seeded_db, db):
        """
        (business_id, invoice_reference, supplier_id) must be unique.
        Inserting the same invoice from the same supplier raises IntegrityError.
        """
        from models.entities import Obligation
        with pytest.raises(IntegrityError):
            dup = Obligation(
                business_id="BIZ-TEST-001",
                supplier_id="SUP-TEST-A",
                invoice_reference="INV-TEST-001",  # same as seeded ob1
                amount=Decimal("999.00"),
                currency="USD",
                due_at=date(2026, 12, 1),
                status="DRAFT",
                source_hash="dup-hash",
            )
            db.add(dup)
            db.flush()

    def test_different_supplier_same_invoice_allowed(self, seeded_db, db):
        """
        The same invoice_reference with a *different* supplier_id is allowed.
        Two distinct suppliers may legitimately share an invoice reference.
        """
        from models.entities import Obligation
        ob = Obligation(
            business_id="BIZ-TEST-001",
            supplier_id="SUP-TEST-B",         # different supplier
            invoice_reference="INV-TEST-001",  # same invoice ref as ob1
            amount=Decimal("250.00"),
            currency="USD",
            due_at=date(2026, 12, 1),
            status="DRAFT",
            source_hash="diff-sup-hash",
        )
        db.add(ob)
        db.flush()  # must not raise
        assert ob.id is not None

    def test_invalid_status_rejected_by_db(self, seeded_db, db):
        """
        H-2: status must be one of the 6 valid state-machine values.
        Any other string must raise IntegrityError (ck_obligation_status_valid).
        """
        from models.entities import Obligation
        ob = seeded_db["ob1"]
        ob.status = "INVENTED_STATUS"
        with pytest.raises(IntegrityError):
            db.flush()

    def test_all_valid_statuses_accepted(self, seeded_db, db):
        """Every state-machine status must be accepted by the CHECK constraint."""
        from models.entities import Obligation

        valid_statuses = ["DRAFT", "VALIDATED", "ON_HOLD", "READY", "CLOSED", "CANCELLED"]
        for i, status in enumerate(valid_statuses):
            ob = Obligation(
                business_id="BIZ-TEST-001",
                supplier_id="SUP-TEST-A",
                invoice_reference=f"INV-STATUS-{i}",
                amount=Decimal("100.00"),
                currency="USD",
                due_at=date(2026, 12, 1),
                status=status,
                source_hash=f"status-hash-{i}",
            )
            db.add(ob)
            db.flush()  # must not raise for any valid status
            db.expunge(ob)  # remove so the loop doesn't conflict


# ===========================================================================
# 3. API — health endpoint
# ===========================================================================

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_response_shape(self, client):
        body = client.get("/api/v1/health").json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "correlation_id" in body

    def test_health_includes_correlation_id_header(self, client):
        resp = client.get("/api/v1/health")
        assert "x-correlation-id" in resp.headers


# ===========================================================================
# 4. API — obligations list
# ===========================================================================

class TestObligationsListEndpoint:
    BIZ = "BIZ-TEST-001"  # matches seeded_db fixture

    def test_obligations_list_returns_200(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}")
        assert resp.status_code == 200

    def test_obligations_list_returns_seeded_count(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}")
        body = resp.json()
        assert body["total"] == 2  # seeded_db inserts 2 obligations

    def test_obligations_response_shape(self, client, seeded_db):
        body = client.get(f"/api/v1/obligations?business_id={self.BIZ}").json()
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        item = body["items"][0]
        for field in ("id", "invoice_reference", "amount", "currency", "due_at", "status", "supplier"):
            assert field in item, f"Missing field: {field}"

    def test_obligations_status_filter_draft(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}&status=DRAFT")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "DRAFT"

    def test_obligations_status_filter_validated(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}&status=VALIDATED")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "VALIDATED"

    def test_obligations_status_filter_nonexistent(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}&status=CANCELLED")
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_obligations_pagination_limit(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}&limit=1")
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["total"] == 2  # total unchanged by limit

    def test_obligations_pagination_offset(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}&limit=1&offset=1")
        body = resp.json()
        assert len(body["items"]) == 1

    def test_obligations_pagination_beyond_end(self, client, seeded_db):
        resp = client.get(f"/api/v1/obligations?business_id={self.BIZ}&offset=100")
        body = resp.json()
        assert len(body["items"]) == 0
        assert body["total"] == 2

    def test_obligations_includes_supplier_name(self, client, seeded_db):
        body = client.get(f"/api/v1/obligations?business_id={self.BIZ}").json()
        item = body["items"][0]
        assert "display_name" in item["supplier"]
        assert item["supplier"]["display_name"] != ""

    def test_obligations_response_includes_correlation_id(self, client, seeded_db):
        body = client.get(f"/api/v1/obligations?business_id={self.BIZ}").json()
        assert "correlation_id" in body

    def test_obligations_limit_too_large_rejected(self, client, seeded_db):
        """limit > 200 must return 422 Unprocessable Entity."""
        resp = client.get("/api/v1/obligations?limit=999")
        assert resp.status_code == 422

    def test_obligations_negative_offset_rejected(self, client, seeded_db):
        """offset < 0 must return 422."""
        resp = client.get("/api/v1/obligations?offset=-1")
        assert resp.status_code == 422
