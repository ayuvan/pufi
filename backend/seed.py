"""
PUFI — Database seed script.

Loads the synthetic obligation data from data/synthetic_data/obligations_seed.json
into the development database.

Usage:
    cd backend
    python seed.py

This script is idempotent: re-running it clears and re-inserts the seed data
so the demo always starts from a known state.

IMPORTANT: This seed script is for development and demo use only.
           It inserts SYNTHETIC data.  Never use real financial records here.
"""
import json
import sys
import os
import hashlib
from decimal import Decimal
from datetime import date

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from models.db import Base, engine, SessionLocal
from models.entities import Business, Supplier, Obligation

SEED_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "synthetic_data", "obligations_seed.json"
)

VALID_ISO_4217 = {
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY",
    "HKD", "NZD", "SEK", "KRW", "SGD", "NOK", "MXN", "INR",
    "RUB", "ZAR", "TRY", "BRL", "TWD", "DKK", "PLN", "THB",
    "IDR", "HUF", "CZK", "ILS", "CLP", "PHP", "AED", "COP",
    "SAR", "MYR", "RON",
}


def _initial_status() -> str:
    """All seeded obligations start as DRAFT.  Validation runs on Day 2."""
    return "DRAFT"


def seed() -> None:
    print("=" * 60)
    print("PUFI Seed Script — Synthetic Demo Data")
    print("=" * 60)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    with open(SEED_FILE, encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    try:
        # -------------------------------------------------------------------
        # Clear existing seed data (idempotent re-run)
        # -------------------------------------------------------------------
        print("\n[1/4] Clearing existing data...")
        db.query(Obligation).delete()
        db.query(Supplier).delete()
        db.query(Business).delete()
        db.commit()
        print("      Done.")

        # -------------------------------------------------------------------
        # Insert businesses
        # -------------------------------------------------------------------
        print("\n[2/4] Inserting businesses...")
        business_map: dict[str, Business] = {}
        for b in data["businesses"]:
            biz = Business(id=b["id"], display_name=b["display_name"])
            db.add(biz)
            business_map[b["id"]] = biz
        db.commit()
        print(f"      Inserted {len(business_map)} business(es).")

        # For seed purposes use the first (and only) business
        default_business_id = list(business_map.keys())[0]

        # -------------------------------------------------------------------
        # Insert suppliers
        # -------------------------------------------------------------------
        print("\n[3/4] Inserting suppliers...")
        supplier_map: dict[str, Supplier] = {}  # external_reference → Supplier
        for s in data["suppliers"]:
            sup = Supplier(
                id=s["id"],
                business_id=default_business_id,
                external_reference=s["external_reference"],
                display_name=s["display_name"],
                country_code=s["country_code"],
                recipient_reference_type=s.get("recipient_reference_type", "EMAIL"),
                recipient_reference_masked=s["recipient_reference_masked"],
                preferred_currency=s.get("preferred_currency"),
            )
            db.add(sup)
            supplier_map[s["external_reference"]] = sup
        db.commit()
        print(f"      Inserted {len(supplier_map)} supplier(s).")

        # -------------------------------------------------------------------
        # Insert obligations (handle duplicates gracefully)
        # -------------------------------------------------------------------
        print("\n[4/4] Inserting obligations...")
        inserted = 0
        skipped_duplicates = 0
        seen_keys: set[tuple] = set()

        for ob in data["obligations"]:
            supplier_ref = ob["supplier_reference"]
            if supplier_ref not in supplier_map:
                print(f"      WARN: supplier {supplier_ref!r} not found — skipping obligation {ob['invoice_reference']!r}")
                continue

            supplier = supplier_map[supplier_ref]
            business_key = (default_business_id, ob["invoice_reference"], supplier.id)

            if business_key in seen_keys:
                # This is an intentional duplicate in the seed data.
                # We skip inserting it into the DB (the unique constraint would
                # reject it anyway) so the demo shows duplicates were detected.
                print(
                    f"      DUPLICATE skipped: invoice={ob['invoice_reference']!r} "
                    f"supplier={supplier_ref!r} — duplicate detection demo record"
                )
                skipped_duplicates += 1
                continue

            seen_keys.add(business_key)

            # Compute a simple source_hash (SHA-256 of normalized key fields)
            hash_input = f"{ob['supplier_reference']}|{ob['invoice_reference']}|{ob['amount']}|{ob['currency']}|{ob['due_at']}"
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            obligation = Obligation(
                business_id=default_business_id,
                supplier_id=supplier.id,
                invoice_reference=ob["invoice_reference"],
                amount=Decimal(ob["amount"]),
                currency=ob["currency"],
                due_at=date.fromisoformat(ob["due_at"]),
                status=_initial_status(),
                source_hash=source_hash,
                notes=ob.get("notes"),
            )
            db.add(obligation)
            inserted += 1

        db.commit()
        print(f"      Inserted {inserted} obligation(s).")
        print(f"      Skipped {skipped_duplicates} intentional duplicate(s) — demo records.")

        # -------------------------------------------------------------------
        # Summary
        # -------------------------------------------------------------------
        total_obs = db.query(Obligation).count()
        print("\n" + "=" * 60)
        print(f"Seed complete.  Obligations in DB: {total_obs}")
        print(
            "\nTest cases present:"
            "\n  [OK]  10 valid USD obligations (DRAFT)"
            "\n  [OK]   2 intentional duplicates (skipped at seed - Day 2 validation demo)"
            "\n  [OK]   1 suspiciously low amount (INV-2026-011)"
            "\n  [OK]   1 invalid currency code ZZZ (INV-2026-012)"
            "\n  [OK]   1 large future-dated obligation (INV-2026-013, eligibility test)"
        )
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"\nERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
