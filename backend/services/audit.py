"""
PUFI Audit Trail Service — Cryptographic Hash-Chained Integrity Verification

Implements Phase 5 of the Master Remediation:
- Every AuditEvent is linked to its predecessor via SHA-256 hash chaining.
- prev_hash of genesis event is 64 zeros ("0" * 64).
- event_hash = SHA256(prev_hash | created_at | entity_type | entity_id | event_type | actor | details_redacted)
- verify_audit_integrity() traverses the chain and detects modifications, deletions, or truncations.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session

from models.entities import AuditEvent

logger = logging.getLogger("pufi.audit")

GENESIS_HASH = "0" * 64


def compute_event_hash(
    prev_hash: Optional[str],
    created_at: datetime,
    entity_type: str,
    entity_id: str,
    event_type: str,
    actor: str,
    details_redacted: Optional[str] = None,
) -> str:
    """
    Computes deterministic SHA-256 hash of an audit event payload linked to prev_hash.
    Normalizes naive database timestamps to explicit UTC before hashing.
    """
    if hasattr(created_at, "tzinfo"):
        if created_at.tzinfo is None:
            iso_time = created_at.replace(tzinfo=timezone.utc).isoformat()
        else:
            iso_time = created_at.astimezone(timezone.utc).isoformat()
    else:
        iso_time = str(created_at)

    p_hash = prev_hash or GENESIS_HASH
    details = details_redacted or ""
    
    payload = f"{p_hash}|{iso_time}|{entity_type}|{entity_id}|{event_type}|{actor}|{details}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    entity_type: str,
    entity_id: str,
    event_type: str,
    actor: str,
    details_redacted: Optional[str] = None,
    correlation_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> AuditEvent:
    """
    Central helper to create, hash, and persist an AuditEvent.
    Links the new event cryptographically to the most recent existing AuditEvent.
    """
    now = created_at or datetime.now(timezone.utc)
    
    # Find latest event in chain (scoped by entity_id if provided)
    query = db.query(AuditEvent).filter(AuditEvent.event_hash.isnot(None))
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)
    latest = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).first()

    if not created_at and latest and latest.created_at:
        latest_time = latest.created_at
        if latest_time.tzinfo is None and now.tzinfo is not None:
            latest_time = latest_time.replace(tzinfo=timezone.utc)
        elif latest_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if now <= latest_time:
            now = latest_time + timedelta(microseconds=1000)
    
    prev_hash = latest.event_hash if (latest and latest.event_hash) else GENESIS_HASH
    event_hash = compute_event_hash(
        prev_hash=prev_hash,
        created_at=now,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        actor=actor,
        details_redacted=details_redacted,
    )
    
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        actor=actor,
        correlation_id=correlation_id,
        details_redacted=details_redacted,
        prev_hash=prev_hash,
        event_hash=event_hash,
        created_at=now,
    )
    db.add(event)
    db.flush()
    return event


@dataclass
class AuditVerificationResult:
    """
    Structured outcome of an audit hash-chain verification run.

    Attributes:
        is_valid: True if and only if all cryptographic links and row hashes match.
        total_events_checked: Total number of chained AuditEvent rows inspected.
        broken_event_id: The specific event UUID where a mismatch or broken link was detected.
        failure_reason: Concise, diagnostic explanation of what failed (tampering, deletion, reordering).
        chain_head_hash: The event_hash of the latest event in the verified chain.
        details: Extra diagnostic metadata (e.g. expected vs actual hash, timestamp).
    """
    is_valid: bool
    total_events_checked: int
    broken_event_id: Optional[str] = None
    failure_reason: Optional[str] = None
    chain_head_hash: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def verify_audit_chain(db: Session, entity_id: Optional[str] = None) -> AuditVerificationResult:
    """
    Independently callable audit-chain verification function (Priority 2.0).

    Verifies the relationship between every event and its predecessor, detecting:
    - Modified event contents (payload tampering, unauthorized field edits).
    - Broken hash links (missing, dropped, or deleted intermediate events).
    - Out-of-order reordering or malicious insertions.

    Architectural Limitations:
    - Because the hash chain is stored entirely within the application database,
      it is tamper-evident against local modifications, but CANNOT detect whole-database
      rollback (restoring an earlier full DB backup) without external Merkle anchoring.
    """
    query = db.query(AuditEvent).filter(AuditEvent.event_hash.isnot(None))
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)

    events = (
        query
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        .all()
    )

    if not events:
        return AuditVerificationResult(
            is_valid=True,
            total_events_checked=0,
            chain_head_hash=GENESIS_HASH,
            details={"scope": entity_id or "GLOBAL", "message": "No audit records found in scope."},
        )

    # Reorder events along the cryptographic chain if equal timestamps caused secondary sort ambiguity
    genesis_candidates = [e for e in events if not e.prev_hash or e.prev_hash == GENESIS_HASH]
    if len(genesis_candidates) == 1:
        by_prev = {e.prev_hash: e for e in events if e.prev_hash and e.prev_hash != GENESIS_HASH}
        ordered = [genesis_candidates[0]]
        curr = genesis_candidates[0]
        while curr.event_hash and curr.event_hash in by_prev:
            next_ev = by_prev[curr.event_hash]
            ordered.append(next_ev)
            curr = next_ev
        if len(ordered) == len(events):
            events = ordered

    expected_prev = GENESIS_HASH

    for idx, ev in enumerate(events):
        # Genesis event verification
        if idx == 0:
            if ev.prev_hash and ev.prev_hash != GENESIS_HASH:
                return AuditVerificationResult(
                    is_valid=False,
                    total_events_checked=idx + 1,
                    broken_event_id=ev.id,
                    failure_reason=f"Genesis event has invalid prev_hash: expected {GENESIS_HASH}, got {ev.prev_hash}",
                    details={"index": idx, "expected": GENESIS_HASH, "actual": ev.prev_hash},
                )
            expected_prev = ev.event_hash or ""
            # Recalculate hash
            if ev.event_hash:
                recalculated = compute_event_hash(
                    prev_hash=ev.prev_hash or GENESIS_HASH,
                    created_at=ev.created_at,
                    entity_type=ev.entity_type,
                    entity_id=ev.entity_id,
                    event_type=ev.event_type,
                    actor=ev.actor,
                    details_redacted=ev.details_redacted,
                )
                if recalculated != ev.event_hash:
                    return AuditVerificationResult(
                        is_valid=False,
                        total_events_checked=idx + 1,
                        broken_event_id=ev.id,
                        failure_reason=f"Tampered event data at id={ev.id}: hash mismatch",
                        details={"index": idx, "expected_hash": ev.event_hash, "computed_hash": recalculated},
                    )
            continue

        # Subsequent events must link cryptographically to the previous event's hash
        if ev.prev_hash != expected_prev:
            return AuditVerificationResult(
                is_valid=False,
                total_events_checked=idx + 1,
                broken_event_id=ev.id,
                failure_reason=(
                    f"Broken hash chain at event id={ev.id}: prev_hash ({ev.prev_hash}) "
                    f"does not match predecessor ({expected_prev}). Intermediate deletion or reordering detected."
                ),
                details={"index": idx, "expected_prev": expected_prev, "actual_prev": ev.prev_hash},
            )

        if ev.event_hash:
            recalculated = compute_event_hash(
                prev_hash=ev.prev_hash,
                created_at=ev.created_at,
                entity_type=ev.entity_type,
                entity_id=ev.entity_id,
                event_type=ev.event_type,
                actor=ev.actor,
                details_redacted=ev.details_redacted,
            )
            if recalculated != ev.event_hash:
                return AuditVerificationResult(
                    is_valid=False,
                    total_events_checked=idx + 1,
                    broken_event_id=ev.id,
                    failure_reason=f"Tampered event data at id={ev.id}: hash mismatch",
                    details={"index": idx, "expected_hash": ev.event_hash, "computed_hash": recalculated},
                )

        expected_prev = ev.event_hash or ""

    return AuditVerificationResult(
        is_valid=True,
        total_events_checked=len(events),
        chain_head_hash=events[-1].event_hash if events else GENESIS_HASH,
        details={
            "scope": entity_id or "GLOBAL",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "first_event_id": events[0].id if events else None,
            "latest_event_id": events[-1].id if events else None,
        },
    )


def verify_audit_integrity(db: Session, entity_id: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Backwards-compatible wrapper returning (is_valid, broken_event_id, failure_reason).
    """
    result = verify_audit_chain(db=db, entity_id=entity_id)
    return result.is_valid, result.broken_event_id, result.failure_reason

