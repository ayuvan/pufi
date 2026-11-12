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
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

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
    """
    iso_time = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
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
    return event


def verify_audit_integrity(db: Session, entity_id: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies the cryptographic integrity of the audit event log (optionally scoped to an entity_id).

    Returns:
        (is_valid, broken_event_id, failure_reason)
        - (True, None, None) if the hash chain is fully intact.
        - (False, event_id, reason) if any row was tampered with, modified, or omitted.
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
        return True, None, None

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
        # Genesis event can either have GENESIS_HASH or None for legacy compatibility
        if idx == 0:
            if ev.prev_hash and ev.prev_hash != GENESIS_HASH:
                return (
                    False,
                    ev.id,
                    f"Genesis event has invalid prev_hash: expected {GENESIS_HASH}, got {ev.prev_hash}",
                )
            expected_prev = ev.event_hash or ""
            # Verify event_hash recalculation if event_hash is populated
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
                    return (
                        False,
                        ev.id,
                        f"Tampered event data at id={ev.id}: hash mismatch",
                    )
            continue
            
        # Subsequent events must link to previous event's hash
        if ev.prev_hash != expected_prev:
            return (
                False,
                ev.id,
                f"Broken hash chain at event id={ev.id}: prev_hash ({ev.prev_hash}) does not match predecessor ({expected_prev})",
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
                return (
                    False,
                    ev.id,
                    f"Tampered event data at id={ev.id}: hash mismatch",
                )
        
        expected_prev = ev.event_hash or ""
        
    return True, None, None
