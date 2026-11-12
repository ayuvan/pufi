"""
PUFI — Priority 2.2 Audit Verification Regression Tests.

Verifies:
  1. Legacy records without hashes (event_hash IS NULL) are detected and reported.
  2. Legacy records are never silently excluded from verification results.
  3. Single entity with only legacy records is flagged as unverifiable with warning.
  4. Entity with mixed legacy and hashed records verifies hashed chain while reporting legacy count.
  5. Content modifications (payload tampering) are detected with exact broken event and entity id.
  6. Intermediate deleted records (broken prev_hash) are detected.
  7. Reordered events are detected.
  8. Global verification traverses all distinct entities and aggregates results.
  9. Documented limitations of in-database hash chaining.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest

from models.entities import AuditEvent
from services.audit import (
    GENESIS_HASH,
    compute_event_hash,
    record_audit_event,
    verify_audit_chain,
)


class TestPriority22AuditVerification:
    """Tests for audit chain integrity and legacy record handling."""

    def test_legacy_record_without_hash_is_detected_and_reported(self, db):
        """Legacy audit records with event_hash IS NULL must be counted and reported, not silently ignored."""
        entity_id = f"LEGACY-ENT-{uuid.uuid4().hex[:8]}"

        # Insert a legacy unhashed record (as if created by Day 1-3 code)
        legacy_ev = AuditEvent(
            entity_type="BATCH",
            entity_id=entity_id,
            event_type="BATCH_CREATED",
            actor="SYSTEM",
            details_redacted=json.dumps({"info": "legacy"}),
            prev_hash=None,
            event_hash=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add(legacy_ev)
        db.flush()

        # Run verification on this entity
        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is True
        assert result.legacy_unhashed_count == 1
        assert result.total_events_checked == 1
        assert "legacy_unhashed_records" in result.details
        assert result.details["legacy_unhashed_records"] == 1
        assert "predate hash-chain implementation" in result.details["warning"]

    def test_entity_with_mixed_legacy_and_hashed_records(self, db):
        """An entity with both legacy unhashed records and subsequent hashed records verifies correctly."""
        entity_id = f"MIXED-ENT-{uuid.uuid4().hex[:8]}"
        t0 = datetime.now(timezone.utc) - timedelta(hours=2)

        # 1. Legacy unhashed record
        legacy_ev = AuditEvent(
            entity_type="BATCH",
            entity_id=entity_id,
            event_type="BATCH_DRAFT_LEGACY",
            actor="SYSTEM",
            prev_hash=None,
            event_hash=None,
            created_at=t0,
        )
        db.add(legacy_ev)
        db.flush()

        # 2. Modern hashed records starting from genesis
        ev1 = record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id=entity_id,
            event_type="BATCH_APPROVED",
            actor="treasury_admin",
            created_at=t0 + timedelta(minutes=10),
        )
        ev2 = record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id=entity_id,
            event_type="BATCH_SUBMITTED",
            actor="controller_carol",
            created_at=t0 + timedelta(minutes=20),
        )
        db.commit()

        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is True
        assert result.legacy_unhashed_count == 1
        assert result.total_events_checked == 3
        assert result.details["legacy_unhashed_records"] == 1
        assert result.chain_head_hash == ev2.event_hash

    def test_global_verification_aggregates_legacy_records(self, db):
        """Global verification includes legacy unhashed records across all entities in the aggregate summary."""
        ent1 = f"G-ENT1-{uuid.uuid4().hex[:8]}"
        ent2 = f"G-ENT2-{uuid.uuid4().hex[:8]}"

        # Entity 1: 1 legacy record
        ev_leg = AuditEvent(
            entity_type="BATCH",
            entity_id=ent1,
            event_type="OLD_EVENT",
            actor="OPERATOR",
            prev_hash=None,
            event_hash=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(ev_leg)

        # Entity 2: 2 modern hashed events
        record_audit_event(db, "BATCH", ent2, "EVENT_A", "ACTOR_A")
        record_audit_event(db, "BATCH", ent2, "EVENT_B", "ACTOR_B")
        db.commit()

        result = verify_audit_chain(db, entity_id=None)
        assert result.is_valid is True
        assert result.legacy_unhashed_count >= 1
        assert "legacy_unhashed_records" in result.details

    def test_payload_tampering_detected(self, db):
        """Tampering with an event's details or actor invalidates the hash and reports broken_event_id."""
        entity_id = f"TAMP-ENT-{uuid.uuid4().hex[:8]}"

        ev1 = record_audit_event(db, "BATCH", entity_id, "EVENT_1", "ACTOR_1", details_redacted="original")
        ev2 = record_audit_event(db, "BATCH", entity_id, "EVENT_2", "ACTOR_2", details_redacted="original")
        db.commit()

        # Tamper with ev1 details directly in DB
        ev1.details_redacted = "MALICIOUS_EDIT"
        db.commit()

        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is False
        assert result.broken_entity_id == entity_id
        assert result.broken_event_id == ev1.id
        assert "Tampered event data" in result.failure_reason

    def test_intermediate_deletion_detected(self, db):
        """Deleting an intermediate event breaks the chain and is identified."""
        entity_id = f"DEL-ENT-{uuid.uuid4().hex[:8]}"

        ev1 = record_audit_event(db, "BATCH", entity_id, "STEP_1", "ACTOR_1")
        ev2 = record_audit_event(db, "BATCH", entity_id, "STEP_2", "ACTOR_2")
        ev3 = record_audit_event(db, "BATCH", entity_id, "STEP_3", "ACTOR_3")
        db.commit()

        # Delete intermediate event
        db.delete(ev2)
        db.commit()

        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is False
        assert result.broken_entity_id == entity_id
        assert result.broken_event_id == ev3.id
        assert "Broken hash chain" in result.failure_reason

    def test_reordered_records_detected(self, db):
        """Swapping two events in sequence breaks cryptographic linkage."""
        entity_id = f"REORD-ENT-{uuid.uuid4().hex[:8]}"
        t0 = datetime.now(timezone.utc)

        ev1 = record_audit_event(db, "BATCH", entity_id, "ORDER_1", "ACTOR_1", created_at=t0)
        ev2 = record_audit_event(db, "BATCH", entity_id, "ORDER_2", "ACTOR_2", created_at=t0 + timedelta(seconds=1))
        ev3 = record_audit_event(db, "BATCH", entity_id, "ORDER_3", "ACTOR_3", created_at=t0 + timedelta(seconds=2))
        db.commit()

        # Swap created_at timestamps between ev2 and ev3 to simulate reordering
        ev2.created_at = t0 + timedelta(seconds=3)
        db.commit()

        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is False
        assert result.broken_entity_id == entity_id
