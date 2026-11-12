"""
PUFI — Load & High-Volume Scalability Tests.

Benchmarks batch processing, row validation, and deterministic route
evaluation across 100, 1,000, and 10,000 records.

Measures actual wall-clock execution time and system environment metrics.
"""
from decimal import Decimal
import os
import platform
import sys
import time

import pytest
from sqlalchemy.orm import Session

from models.entities import Business, Supplier, Obligation, PaymentBatch, BatchObligation
from services.validation import validate_import_row
from services.routing_engine import ObligationContext, route_obligation


def get_environment_info() -> dict:
    """Capture runtime system environment details for benchmark logging."""
    return {
        "os": platform.platform(),
        "python_version": sys.version.split()[0],
        "processor": platform.processor(),
        "machine": platform.machine(),
    }


@pytest.fixture
def load_test_context(db: Session):
    """Seed base business and suppliers for high-volume load tests."""
    biz = Business(id="BIZ-LOAD-001", display_name="[LOAD-TEST] High Volume Corp")
    sup1 = Supplier(
        id="SUP-LOAD-001",
        business_id=biz.id,
        external_reference="SUP-LOAD-001",
        display_name="High Volume Supplier 1",
        country_code="US",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="load1@example.com",
        preferred_currency="USD",
    )
    sup2 = Supplier(
        id="SUP-LOAD-002",
        business_id=biz.id,
        external_reference="SUP-LOAD-002",
        display_name="High Volume Supplier 2",
        country_code="DE",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="load2@example.com",
        preferred_currency="EUR",
    )
    db.add_all([biz, sup1, sup2])
    db.flush()
    return {"biz": biz, "sup1": sup1, "sup2": sup2}


@pytest.mark.parametrize("record_count", [100, 1000, 10000])
def test_batch_validation_and_routing_performance(record_count, load_test_context, db: Session):
    """
    Benchmark ingestion, validation, and routing of N records.
    Tests 100, 1,000, and 10,000 obligation records.
    """
    biz = load_test_context["biz"]
    sup = load_test_context["sup1"]

    env = get_environment_info()

    # 1. Validation Benchmark
    t0_val = time.perf_counter()
    valid_count = 0
    for i in range(1, record_count + 1):
        res = validate_import_row(
            business_id=biz.id,
            supplier_reference="SUP-LOAD-001",
            invoice_reference=f"INV-LOAD-{record_count}-{i:06d}",
            amount_str="150.00",
            currency="USD",
            due_at_str="2026-12-31",
            db=db,
        )
        if res.valid:
            valid_count += 1
    t1_val = time.perf_counter()
    duration_val = t1_val - t0_val

    assert valid_count == record_count

    # 2. Routing Engine Benchmark
    t0_route = time.perf_counter()
    routed_count = 0
    for i in range(1, record_count + 1):
        ctx = ObligationContext(
            obligation_id=f"OBL-BENCH-{i}",
            source_amount=Decimal("150.00"),
            source_currency="USD",
            recipient_currency="USD",
            recipient_type="EMAIL",
        )
        route_res = route_obligation(ctx, strategy="LOWEST_COST")
        if len(route_res.eligible_routes) > 0:
            routed_count += 1
    t1_route = time.perf_counter()
    duration_route = t1_route - t0_route

    assert routed_count == record_count

    # Throughput calculations
    val_rate = record_count / duration_val if duration_val > 0 else 0
    route_rate = record_count / duration_route if duration_route > 0 else 0

    print(
        f"\n[LOAD TEST RESULTS] Records: {record_count:,} | "
        f"Validation: {duration_val:.4f}s ({val_rate:,.1f} rec/s) | "
        f"Routing: {duration_route:.4f}s ({route_rate:,.1f} rec/s) | "
        f"Env: {env['os']} / Py {env['python_version']}"
    )

    # Sanity thresholds: 10,000 records must complete within reasonable time
    if record_count == 100:
        assert duration_val < 10.0
    elif record_count == 1000:
        assert duration_val < 30.0
    elif record_count == 10000:
        assert duration_val < 120.0
