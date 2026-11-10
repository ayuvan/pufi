"""
PUFI — Extended Synthetic Dataset Generator & Seed Script.

Generates a reproducible, mathematically validated synthetic dataset
for reliability testing and hackathon demonstration.

Categories generated:
  - 100 valid supplier obligations (USD, standard amounts, US suppliers)
  - 20 duplicate obligations (same supplier + invoice_reference as valid ones)
  - 15 invalid obligations (zero/negative amounts, bad currencies, invalid dates, unknown suppliers)
  - 20 international obligations (EUR, GBP, JPY, CAD across foreign suppliers)
  - 10 unusually large obligations ($100k - $750k USD to test provider limits)
  - 10 incomplete obligations (suppliers with missing/masked recipient details)

Strict financial rules:
  - All amounts generated using Python Decimal.
  - Fixed random seed (42) for 100% reproducibility.
  - Clearly labelled [SYNTHETIC] with zero real PII or live payment details.

Usage:
  python extended_seed.py                 # Generates JSON dataset file
  python extended_seed.py --seed          # Seeds into database
  python extended_seed.py --seed --force  # Overwrites existing DB tables
"""
import argparse
import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
import random
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

SEED = 42
OUTPUT_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "synthetic_data", "extended_synthetic_dataset.json"
)

# Standard test dates in 2026
BASE_DATE = datetime.date(2026, 11, 15)


def generate_extended_dataset() -> dict:
    """Generate the complete synthetic dataset deterministically."""
    rng = random.Random(SEED)

    business = {
        "id": "biz-synth-001",
        "display_name": "[SYNTHETIC] Nexus Global Enterprises Ltd",
    }

    # 1. Generate Synthetic Suppliers
    # Standard domestic suppliers
    suppliers = [
        {
            "id": f"sup-synth-dom-{i:03d}",
            "external_reference": f"SUP-DOM-{i:03d}",
            "display_name": f"[SYNTHETIC] Acme Logistics Group {i}",
            "country_code": "US",
            "recipient_reference_type": "EMAIL",
            "recipient_reference_masked": f"finance.dom{i}@synthetic-acme.example",
            "preferred_currency": "USD",
        }
        for i in range(1, 11)
    ]

    # International suppliers
    int_countries = [
        ("DE", "EUR", "GmbH"),
        ("GB", "GBP", "Ltd"),
        ("JP", "JPY", "Corp"),
        ("CA", "CAD", "Inc"),
        ("AU", "AUD", "Pty"),
    ]
    for i, (country, curr, suffix) in enumerate(int_countries, start=1):
        suppliers.append({
            "id": f"sup-synth-int-{i:03d}",
            "external_reference": f"SUP-INT-{i:03d}",
            "display_name": f"[SYNTHETIC] International Partner {country} {suffix}",
            "country_code": country,
            "recipient_reference_type": "EMAIL",
            "recipient_reference_masked": f"pay.{country.lower()}@synthetic-global.example",
            "preferred_currency": curr,
        })

    # Incomplete suppliers (lacking valid recipient reference or unconfigured)
    for i in range(1, 4):
        suppliers.append({
            "id": f"sup-synth-inc-{i:03d}",
            "external_reference": f"SUP-INC-{i:03d}",
            "display_name": f"[SYNTHETIC] Incomplete Supplier {i}",
            "country_code": "US",
            "recipient_reference_type": "NONE",
            "recipient_reference_masked": "UNCONFIGURED",
            "preferred_currency": "USD",
        })

    # 2. 100 Valid Supplier Obligations
    valid_obligations = []
    for i in range(1, 101):
        sup = suppliers[(i - 1) % 10]  # round-robin US domestic suppliers
        # Amounts between $25.00 and $48,500.00
        cents = rng.randint(2500, 4850000)
        amt = (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        due = BASE_DATE + datetime.timedelta(days=rng.randint(1, 45))
        valid_obligations.append({
            "category": "VALID",
            "supplier_reference": sup["external_reference"],
            "invoice_reference": f"INV-SYNTH-VAL-{i:04d}",
            "amount": str(amt),
            "currency": "USD",
            "due_at": due.isoformat(),
            "notes": f"[SYNTHETIC] Valid operational invoice #{i:04d}",
        })

    # 3. 20 Duplicate Obligations (exact duplicates of first 20 valid ones)
    duplicate_obligations = []
    for i in range(20):
        target = valid_obligations[i]
        duplicate_obligations.append({
            "category": "DUPLICATE",
            "supplier_reference": target["supplier_reference"],
            "invoice_reference": target["invoice_reference"],
            "amount": target["amount"],
            "currency": target["currency"],
            "due_at": target["due_at"],
            "notes": f"[SYNTHETIC] Intentional duplicate of {target['invoice_reference']}",
        })

    # 4. 15 Invalid Obligations
    invalid_obligations = [
        # Zero / Negative / Non-decimal amounts
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-001",
            "invoice_reference": "INV-SYNTH-INV-001",
            "amount": "0.00",
            "currency": "USD",
            "due_at": "2026-11-20",
            "expected_error": "amount must be > 0",
            "notes": "[SYNTHETIC] Zero amount invalid test",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-002",
            "invoice_reference": "INV-SYNTH-INV-002",
            "amount": "-450.00",
            "currency": "USD",
            "due_at": "2026-11-20",
            "expected_error": "amount must be > 0",
            "notes": "[SYNTHETIC] Negative amount invalid test",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-003",
            "invoice_reference": "INV-SYNTH-INV-003",
            "amount": "NOT_A_NUMBER",
            "currency": "USD",
            "due_at": "2026-11-20",
            "expected_error": "amount is not a valid decimal number",
            "notes": "[SYNTHETIC] Corrupted decimal test",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-004",
            "invoice_reference": "INV-SYNTH-INV-004",
            "amount": "-0.01",
            "currency": "USD",
            "due_at": "2026-11-20",
            "expected_error": "amount must be > 0",
            "notes": "[SYNTHETIC] Fractional negative amount",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-005",
            "invoice_reference": "INV-SYNTH-INV-005",
            "amount": "0",
            "currency": "USD",
            "due_at": "2026-11-20",
            "expected_error": "amount must be > 0",
            "notes": "[SYNTHETIC] Zero integer amount",
        },
        # Invalid currency codes
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-001",
            "invoice_reference": "INV-SYNTH-INV-006",
            "amount": "1250.00",
            "currency": "XYZ",
            "due_at": "2026-11-20",
            "expected_error": "currency 'XYZ' is not a recognised ISO 4217 code",
            "notes": "[SYNTHETIC] Non-existent currency code",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-002",
            "invoice_reference": "INV-SYNTH-INV-007",
            "amount": "980.00",
            "currency": "USDD",
            "due_at": "2026-11-20",
            "expected_error": "currency 'USDD' is not a recognised ISO 4217 code",
            "notes": "[SYNTHETIC] 4-letter invalid currency",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-003",
            "invoice_reference": "INV-SYNTH-INV-008",
            "amount": "340.00",
            "currency": "123",
            "due_at": "2026-11-20",
            "expected_error": "currency '123' is not a recognised ISO 4217 code",
            "notes": "[SYNTHETIC] Numeric currency code",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-004",
            "invoice_reference": "INV-SYNTH-INV-009",
            "amount": "500.00",
            "currency": "",
            "due_at": "2026-11-20",
            "expected_error": "currency is required",
            "notes": "[SYNTHETIC] Empty currency string",
        },
        # Invalid dates
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-001",
            "invoice_reference": "INV-SYNTH-INV-010",
            "amount": "750.00",
            "currency": "USD",
            "due_at": "2026-13-45",
            "expected_error": "due_at must be YYYY-MM-DD",
            "notes": "[SYNTHETIC] Out of range date",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-002",
            "invoice_reference": "INV-SYNTH-INV-011",
            "amount": "820.00",
            "currency": "USD",
            "due_at": "not-a-date",
            "expected_error": "due_at must be YYYY-MM-DD",
            "notes": "[SYNTHETIC] Malformed text date",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-DOM-003",
            "invoice_reference": "INV-SYNTH-INV-012",
            "amount": "1100.00",
            "currency": "USD",
            "due_at": "2026/11/20",
            "expected_error": "due_at must be YYYY-MM-DD",
            "notes": "[SYNTHETIC] Slash formatted date",
        },
        # Unknown / missing suppliers
        {
            "category": "INVALID",
            "supplier_reference": "SUP-NONEXISTENT-999",
            "invoice_reference": "INV-SYNTH-INV-013",
            "amount": "1450.00",
            "currency": "USD",
            "due_at": "2026-11-25",
            "expected_error": "supplier_reference 'SUP-NONEXISTENT-999' not found",
            "notes": "[SYNTHETIC] Unknown supplier reference",
        },
        {
            "category": "INVALID",
            "supplier_reference": "SUP-ORPHAN-001",
            "invoice_reference": "INV-SYNTH-INV-014",
            "amount": "2300.00",
            "currency": "USD",
            "due_at": "2026-11-25",
            "expected_error": "supplier_reference 'SUP-ORPHAN-001' not found",
            "notes": "[SYNTHETIC] Unregistered supplier reference",
        },
        {
            "category": "INVALID",
            "supplier_reference": "",
            "invoice_reference": "INV-SYNTH-INV-015",
            "amount": "500.00",
            "currency": "USD",
            "due_at": "2026-11-25",
            "expected_error": "supplier_reference is required",
            "notes": "[SYNTHETIC] Empty supplier reference",
        },
    ]

    # 5. 20 International Payment Obligations
    international_obligations = []
    int_specs = [
        ("SUP-INT-001", "EUR", [1200, 2450, 5800, 14200]),
        ("SUP-INT-002", "GBP", [850, 1900, 4200, 9600]),
        ("SUP-INT-003", "JPY", [150000, 320000, 850000, 1200000]),
        ("SUP-INT-004", "CAD", [1600, 3100, 7500, 18000]),
        ("SUP-INT-005", "AUD", [1400, 2900, 6800, 15500]),
    ]
    int_count = 1
    for sup_ref, curr, amounts in int_specs:
        for amt_int in amounts:
            due = BASE_DATE + datetime.timedelta(days=rng.randint(5, 30))
            amt = Decimal(amt_int).quantize(Decimal("1") if curr == "JPY" else Decimal("0.01"))
            international_obligations.append({
                "category": "INTERNATIONAL",
                "supplier_reference": sup_ref,
                "invoice_reference": f"INV-SYNTH-INT-{int_count:04d}",
                "amount": str(amt),
                "currency": curr,
                "due_at": due.isoformat(),
                "notes": f"[SYNTHETIC] International {curr} settlement obligation",
            })
            int_count += 1

    # 6. 10 Unusually Large Payment Obligations ($100k to $750k USD)
    large_obligations = []
    large_amounts = [
        "100000.00", "125000.00", "150000.00", "200000.00", "250000.00",
        "300000.00", "400000.00", "500000.00", "650000.00", "750000.00",
    ]
    for i, amt_str in enumerate(large_amounts, start=1):
        sup = suppliers[i % 5]
        due = BASE_DATE + datetime.timedelta(days=rng.randint(10, 60))
        large_obligations.append({
            "category": "LARGE",
            "supplier_reference": sup["external_reference"],
            "invoice_reference": f"INV-SYNTH-LRG-{i:04d}",
            "amount": amt_str,
            "currency": "USD",
            "due_at": due.isoformat(),
            "notes": f"[SYNTHETIC] Large treasury capital expenditure #{i:04d}",
        })

    # 7. 10 Incomplete Supplier Obligations
    incomplete_obligations = []
    for i in range(1, 11):
        sup_ref = f"SUP-INC-{( (i - 1) % 3 ) + 1:03d}"
        amt = Decimal(rng.randint(500, 4500)).quantize(Decimal("0.01"))
        due = BASE_DATE + datetime.timedelta(days=rng.randint(3, 20))
        incomplete_obligations.append({
            "category": "INCOMPLETE",
            "supplier_reference": sup_ref,
            "invoice_reference": f"INV-SYNTH-INC-{i:04d}",
            "amount": str(amt),
            "currency": "USD",
            "due_at": due.isoformat(),
            "notes": f"[SYNTHETIC] Obligation with missing/unconfigured recipient details #{i:04d}",
        })

    dataset = {
        "_metadata": {
            "label": "SYNTHETIC",
            "seed": SEED,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "description": "PUFI extended synthetic dataset for reliability, validation, and load testing.",
            "counts": {
                "valid": len(valid_obligations),
                "duplicate": len(duplicate_obligations),
                "invalid": len(invalid_obligations),
                "international": len(international_obligations),
                "large": len(large_obligations),
                "incomplete": len(incomplete_obligations),
                "total_obligations": (
                    len(valid_obligations) + len(duplicate_obligations) + len(invalid_obligations) +
                    len(international_obligations) + len(large_obligations) + len(incomplete_obligations)
                ),
            },
        },
        "business": business,
        "suppliers": suppliers,
        "obligations": {
            "valid": valid_obligations,
            "duplicate": duplicate_obligations,
            "invalid": invalid_obligations,
            "international": international_obligations,
            "large": large_obligations,
            "incomplete": incomplete_obligations,
        },
    }
    return dataset


def save_dataset_file(filepath: str = OUTPUT_JSON_PATH) -> dict:
    dataset = generate_extended_dataset()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    print(f"Saved extended synthetic dataset to: {filepath}")
    counts = dataset["_metadata"]["counts"]
    print(f"Summary counts:")
    for k, v in counts.items():
        print(f"  - {k}: {v}")
    return dataset


def seed_database(force: bool = False):
    """Seed the generated dataset into the SQLite development database."""
    from models.db import Base, engine, SessionLocal
    from models.entities import Business, Supplier, Obligation

    dataset = generate_extended_dataset()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        biz_data = dataset["business"]
        existing_biz = db.query(Business).filter(Business.id == biz_data["id"]).first()
        if existing_biz and not force:
            print(f"Business {biz_data['id']} already exists. Use --force to recreate.")
            return

        if force:
            print("Clearing synthetic test data from database...")
            db.query(Obligation).filter(Obligation.invoice_reference.like("INV-SYNTH-%")).delete(synchronize_session=False)
            db.query(Supplier).filter(Supplier.external_reference.like("SUP-%")).delete(synchronize_session=False)
            if existing_biz:
                db.delete(existing_biz)
            db.commit()

        # Insert business
        biz = Business(id=biz_data["id"], display_name=biz_data["display_name"])
        db.add(biz)
        db.flush()

        # Insert suppliers
        for s in dataset["suppliers"]:
            sup = Supplier(
                id=s["id"],
                business_id=biz.id,
                external_reference=s["external_reference"],
                display_name=s["display_name"],
                country_code=s["country_code"],
                recipient_reference_type=s["recipient_reference_type"],
                recipient_reference_masked=s["recipient_reference_masked"],
                preferred_currency=s["preferred_currency"],
            )
            db.add(sup)
        db.flush()

        # Insert valid obligations
        inserted_count = 0
        for obl_data in dataset["obligations"]["valid"]:
            sup = db.query(Supplier).filter(Supplier.external_reference == obl_data["supplier_reference"]).first()
            raw_hash = f"{biz.id}:{sup.id}:{obl_data['invoice_reference']}:{obl_data['amount']}"
            source_hash = hashlib.sha256(raw_hash.encode()).hexdigest()
            obl = Obligation(
                business_id=biz.id,
                supplier_id=sup.id,
                invoice_reference=obl_data["invoice_reference"],
                amount=Decimal(obl_data["amount"]),
                currency=obl_data["currency"],
                due_at=datetime.date.fromisoformat(obl_data["due_at"]),
                status="VALIDATED",
                source_hash=source_hash,
                notes=obl_data["notes"],
            )
            db.add(obl)
            inserted_count += 1

        db.commit()
        print(f"Successfully seeded {inserted_count} VALID obligations into business {biz.id}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PUFI Extended Synthetic Dataset Generator")
    parser.add_argument("--seed", action="store_true", help="Seed data into database")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing test data")
    parser.add_argument("--output", type=str, default=OUTPUT_JSON_PATH, help="Path for JSON output")
    args = parser.parse_args()

    save_dataset_file(args.output)
    if args.seed:
        seed_database(force=args.force)
