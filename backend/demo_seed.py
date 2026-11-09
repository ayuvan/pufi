"""
PUFI — Demo seed script (Day 4).

Creates a complete demo dataset usable for testing the full Day 3–4 workflow:
  1. Business + Suppliers (reuses or creates)
  2. Valid USD obligations (through the validation service)
  3. A PaymentBatch containing those validated obligations
  4. Runs analysis (POST /analyze) to store an AiRecommendation

Usage:
    cd backend
    python demo_seed.py

This script is IDEMPOTENT: re-running it skips creation if the demo batch
(batch_reference="DEMO-BATCH-DAY4") already exists.

IMPORTANT:
  - All data is SYNTHETIC. Never use real financial records.
  - Demo records are labelled "SYNTHETIC DEMO DATA".
  - This script is for development and demonstration only.
  - Do NOT run against a production database.
"""
import json
import os
import sys
import hashlib
from decimal import Decimal
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from models.db import Base, engine, SessionLocal
from models.entities import (
    Business, Supplier, Obligation,
    PaymentBatch, BatchObligation, AiRecommendation,
)
from services.validation import validate_import_row

DEMO_BATCH_REFERENCE = "DEMO-BATCH-DAY4"
DEMO_BUSINESS_ID = "BIZ-DEMO-DAY4-001"
DEMO_BUSINESS_NAME = "[SYNTHETIC DEMO] Acme Enterprise"


# ---------------------------------------------------------------------------
# Synthetic supplier definitions
# ---------------------------------------------------------------------------

DEMO_SUPPLIERS = [
    {
        "id": "SUP-DEMO-001",
        "external_reference": "DEMO-SUP-001",
        "display_name": "[SYNTHETIC] Alpha Supplies Inc.",
        "country_code": "US",
        "recipient_reference_type": "EMAIL",
        "recipient_reference_masked": "a***@alphasupplies.example.com",
        "preferred_currency": "USD",
    },
    {
        "id": "SUP-DEMO-002",
        "external_reference": "DEMO-SUP-002",
        "display_name": "[SYNTHETIC] Beta Components Ltd.",
        "country_code": "US",
        "recipient_reference_type": "EMAIL",
        "recipient_reference_masked": "b***@betacomponents.example.com",
        "preferred_currency": "USD",
    },
    {
        "id": "SUP-DEMO-003",
        "external_reference": "DEMO-SUP-003",
        "display_name": "[SYNTHETIC] Gamma Services LLC",
        "country_code": "US",
        "recipient_reference_type": "EMAIL",
        "recipient_reference_masked": "g***@gammaservices.example.com",
        "preferred_currency": "USD",
    },
]


# ---------------------------------------------------------------------------
# Synthetic obligation definitions (all USD, all VALIDATED after seeding)
# ---------------------------------------------------------------------------

DEMO_OBLIGATIONS = [
    {
        "supplier_reference": "DEMO-SUP-001",
        "invoice_reference": "DEMO-INV-DAY4-001",
        "amount": "500.00",
        "currency": "USD",
        "due_at": "2026-12-31",
        "notes": "[SYNTHETIC DEMO DATA] Alpha supplies invoice",
    },
    {
        "supplier_reference": "DEMO-SUP-002",
        "invoice_reference": "DEMO-INV-DAY4-002",
        "amount": "750.00",
        "currency": "USD",
        "due_at": "2026-12-31",
        "notes": "[SYNTHETIC DEMO DATA] Beta components invoice",
    },
    {
        "supplier_reference": "DEMO-SUP-003",
        "invoice_reference": "DEMO-INV-DAY4-003",
        "amount": "1000.00",
        "currency": "USD",
        "due_at": "2026-12-31",
        "notes": "[SYNTHETIC DEMO DATA] Gamma services invoice",
    },
]


def seed_demo() -> None:
    print("=" * 60)
    print("PUFI Demo Seed — Synthetic Demo Data for Day 4")
    print("=" * 60)
    print()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # --- Check idempotency: skip if demo batch already exists ---
        existing_batch = (
            db.query(PaymentBatch)
            .filter(PaymentBatch.batch_reference == DEMO_BATCH_REFERENCE)
            .first()
        )
        if existing_batch:
            print(f"[SKIP] Demo batch already exists.")
            print(f"  Batch ID    : {existing_batch.id}")
            print(f"  Reference   : {existing_batch.batch_reference}")
            print(f"  Status      : {existing_batch.status}")
            print()
            print("Rerun with --force to delete and recreate the demo batch.")
            # Check for --force flag
            if "--force" not in sys.argv:
                _print_summary(existing_batch.id)
                return
            # Force: delete existing demo data
            print("[FORCE] Deleting existing demo data...")
            db.query(BatchObligation).filter(
                BatchObligation.batch_id == existing_batch.id
            ).delete()
            db.query(AiRecommendation).filter(
                AiRecommendation.batch_id == existing_batch.id
            ).delete()
            db.delete(existing_batch)
            # Delete demo obligations
            for obs in DEMO_OBLIGATIONS:
                sup = db.query(Supplier).filter(
                    Supplier.external_reference == obs["supplier_reference"],
                    Supplier.business_id == DEMO_BUSINESS_ID,
                ).first()
                if sup:
                    ob = db.query(Obligation).filter(
                        Obligation.business_id == DEMO_BUSINESS_ID,
                        Obligation.supplier_id == sup.id,
                        Obligation.invoice_reference == obs["invoice_reference"],
                    ).first()
                    if ob:
                        db.delete(ob)
            db.commit()
            print("[FORCE] Done.")
            print()

        # --- Ensure business exists ---
        business = db.query(Business).filter(Business.id == DEMO_BUSINESS_ID).first()
        if not business:
            print(f"[1/5] Creating demo business: {DEMO_BUSINESS_NAME}")
            business = Business(id=DEMO_BUSINESS_ID, display_name=DEMO_BUSINESS_NAME)
            db.add(business)
            db.commit()
        else:
            print(f"[1/5] Business already exists: {DEMO_BUSINESS_ID}")

        # --- Ensure suppliers exist ---
        print(f"[2/5] Ensuring {len(DEMO_SUPPLIERS)} demo suppliers...")
        supplier_map: dict[str, Supplier] = {}
        for s in DEMO_SUPPLIERS:
            existing = db.query(Supplier).filter(
                Supplier.id == s["id"]
            ).first()
            if not existing:
                sup = Supplier(
                    id=s["id"],
                    business_id=DEMO_BUSINESS_ID,
                    external_reference=s["external_reference"],
                    display_name=s["display_name"],
                    country_code=s["country_code"],
                    recipient_reference_type=s["recipient_reference_type"],
                    recipient_reference_masked=s["recipient_reference_masked"],
                    preferred_currency=s.get("preferred_currency"),
                )
                db.add(sup)
                db.commit()
                supplier_map[s["external_reference"]] = sup
                print(f"      Created: {s['display_name']}")
            else:
                supplier_map[s["external_reference"]] = existing
                print(f"      Exists:  {s['display_name']}")

        # --- Create obligations via validation service ---
        print(f"[3/5] Creating and validating {len(DEMO_OBLIGATIONS)} demo obligations...")
        validated_obligation_ids: list[str] = []

        for row in DEMO_OBLIGATIONS:
            # Check if already exists
            sup = supplier_map.get(row["supplier_reference"])
            if not sup:
                print(f"      WARN: supplier {row['supplier_reference']!r} not found — skipping")
                continue

            existing_ob = db.query(Obligation).filter(
                Obligation.business_id == DEMO_BUSINESS_ID,
                Obligation.supplier_id == sup.id,
                Obligation.invoice_reference == row["invoice_reference"],
            ).first()

            if existing_ob:
                if existing_ob.status == "VALIDATED":
                    validated_obligation_ids.append(existing_ob.id)
                    print(f"      Exists (VALIDATED): {row['invoice_reference']}")
                else:
                    print(f"      Exists (status={existing_ob.status!r}): {row['invoice_reference']} — skipping")
                continue

            # Validate through service (enforces business rules)
            result = validate_import_row(
                business_id=DEMO_BUSINESS_ID,
                supplier_reference=row["supplier_reference"],
                invoice_reference=row["invoice_reference"],
                amount_str=row["amount"],
                currency=row["currency"],
                due_at_str=row["due_at"],
                db=db,
            )

            if not result.valid:
                print(f"      INVALID: {row['invoice_reference']} — {result.errors}")
                continue

            if result.duplicate:
                print(f"      DUPLICATE: {row['invoice_reference']}")
                continue

            # Compute source_hash
            hash_input = f"{row['supplier_reference']}|{row['invoice_reference']}|{row['amount']}|{row['currency']}|{row['due_at']}"
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            ob = Obligation(
                business_id=DEMO_BUSINESS_ID,
                supplier_id=result.supplier.id,
                invoice_reference=row["invoice_reference"],
                amount=result.amount,
                currency=row["currency"].upper(),
                due_at=result.due_at,
                status="VALIDATED",    # Pre-validated for demo
                source_hash=source_hash,
                notes=row.get("notes"),
            )
            db.add(ob)
            db.commit()
            db.refresh(ob)
            validated_obligation_ids.append(ob.id)
            print(f"      Created (VALIDATED): {row['invoice_reference']} — {row['amount']} {row['currency']}")

        if not validated_obligation_ids:
            print("\nERROR: No validated obligations created. Demo seed aborted.")
            return

        # --- Create PaymentBatch ---
        print(f"[4/5] Creating demo PaymentBatch '{DEMO_BATCH_REFERENCE}'...")
        batch = PaymentBatch(
            business_id=DEMO_BUSINESS_ID,
            batch_reference=DEMO_BATCH_REFERENCE,
            status="DRAFT",
            notes="[SYNTHETIC DEMO DATA] Day 4 demo batch for PUFI prototype.",
        )
        db.add(batch)
        db.flush()

        for ob_id in validated_obligation_ids:
            db.add(BatchObligation(batch_id=batch.id, obligation_id=ob_id))

        db.commit()
        db.refresh(batch)
        print(f"      Batch ID: {batch.id}")
        print(f"      Obligations linked: {len(validated_obligation_ids)}")

        # --- Run analysis via the routing engine directly ---
        print("[5/5] Running financial analysis on demo batch...")
        try:
            _run_analysis(batch.id, db)
            print("      Analysis complete — AiRecommendation stored.")
        except Exception as exc:
            print(f"      WARN: Analysis failed ({exc}). Batch is still usable but approval will require re-running analysis via API.")

        db.commit()

        _print_summary(batch.id)

    except Exception as exc:
        db.rollback()
        print(f"\nERROR: {exc}")
        raise
    finally:
        db.close()


def _run_analysis(batch_id: str, db) -> None:
    """
    Run the routing engine and store an AiRecommendation for the demo batch.
    This mirrors what POST /analyze does, so the batch is ready for approval.
    """
    import json as _json
    from decimal import Decimal as D
    from collections import defaultdict

    from models.entities import BatchObligation, Obligation, AiRecommendation
    from services.routing_engine import ObligationContext, route_obligation
    from services.ai_advisor import analyze_batch as ai_analyze_batch

    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    batch_obs = db.query(BatchObligation).filter(BatchObligation.batch_id == batch_id).all()
    obligation_ids = [bo.obligation_id for bo in batch_obs]
    obligations = db.query(Obligation).filter(Obligation.id.in_(obligation_ids)).all()

    # Aggregate amounts
    totals: dict[str, D] = defaultdict(D)
    for ob in obligations:
        totals[ob.currency] += D(str(ob.amount))
    total_by_currency = {c: str(v) for c, v in totals.items()}

    # Route each obligation
    provider_eligible: dict[str, list] = {}
    provider_excluded: dict[str, list] = {}

    for ob in obligations:
        ctx = ObligationContext(
            obligation_id=ob.id,
            source_amount=D(str(ob.amount)),
            source_currency=ob.currency.upper(),
            recipient_currency="USD",
            recipient_type="EMAIL",
        )
        routing = route_obligation(ctx, strategy="LOWEST_COST")
        for er in routing.eligible_routes:
            provider_eligible.setdefault(er.provider_code, []).append(er)
        for ex in routing.excluded_routes:
            provider_excluded.setdefault(ex.provider_code, []).extend(
                r for r in ex.exclusion_reasons if r not in provider_excluded.get(ex.provider_code, [])
            )

    eligible_codes = list(provider_eligible.keys())
    eligible_route_dicts = []
    for code, results in provider_eligible.items():
        total_cost = sum((r.cost.total_estimated_cost for r in results if r.cost), D("0"))
        eligible_route_dicts.append({
            "provider_code": code,
            "display_name": results[0].display_name,
            "environment": results[0].environment,
            "total_estimated_cost": str(total_cost),
            "provider_fee": str(sum((r.cost.provider_fee for r in results if r.cost), D("0"))),
            "fx_spread_cost": str(sum((r.cost.fx_spread_cost for r in results if r.cost), D("0"))),
            "estimated_processing_hours": None,
            "quote_label": "SIMULATED",
            "warnings": [],
        })

    excluded_route_dicts = [
        {"provider_code": code, "exclusion_reasons": reasons}
        for code, reasons in provider_excluded.items()
        if code not in provider_eligible
    ]

    ai_result, input_hash = ai_analyze_batch(
        batch_reference=batch.batch_reference,
        total_obligations=len(obligations),
        total_by_currency=total_by_currency,
        eligible_routes=eligible_route_dicts,
        excluded_routes=excluded_route_dicts,
        eligible_route_codes=eligible_codes,
    )

    ai_rec = AiRecommendation(
        batch_id=batch_id,
        model_name=ai_result.model_name,
        input_summary_hash=input_hash,
        recommendation_json=_json.dumps({
            "summary": ai_result.summary,
            "recommended_route": ai_result.recommended_route,
            "reasoning_factors": ai_result.reasoning_factors,
            "warnings": ai_result.warnings,
            "requires_human_review": ai_result.requires_human_review,
            "evidence_fields": {
                "eligible_route_codes": eligible_codes,
                "raw_fields": ai_result.evidence_fields,
            },
            "fallback_used": ai_result.fallback_used,
            "fallback_reason": ai_result.fallback_reason,
        }, default=str),
        fallback_used=ai_result.fallback_used,
        fallback_reason=ai_result.fallback_reason,
    )
    db.add(ai_rec)
    db.flush()


def _print_summary(batch_id: str) -> None:
    print()
    print("=" * 60)
    print("DEMO SEED COMPLETE")
    print("=" * 60)
    print(f"  Batch ID        : {batch_id}")
    print(f"  Batch Reference : {DEMO_BATCH_REFERENCE}")
    print()
    print("NEXT STEPS:")
    print(f"  1. Start the backend: uvicorn main:app --reload")
    print(f"  2. Open the Analysis page with batch ID: {batch_id}")
    print(f"  3. Approve the batch: POST /api/v1/batches/{batch_id}/approve")
    print(f"  4. Submit to PayPal Sandbox: POST /api/v1/batches/{batch_id}/submit")
    print(f"  5. Refresh status: POST /api/v1/batches/{batch_id}/refresh-status")
    print()
    print("NOTE: All data is SYNTHETIC. No real money is involved.")
    print("=" * 60)


if __name__ == "__main__":
    seed_demo()
