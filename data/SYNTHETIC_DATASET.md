# PUFI Extended Synthetic Dataset Documentation

> **Classification:** SYNTHETIC ONLY  
> **Generation Seed:** `42` (Deterministic & Reproducible)  
> **Currency Precision:** Arbitrary-precision Python `Decimal` / SQLite `NUMERIC(19, 4)`  
> **Compliance:** Zero real customer, supplier, bank, or payment details.

---

## 1. Overview & Purpose

The PUFI Extended Synthetic Dataset is designed to validate the reliability, mathematical correctness, edge-case resilience, and load characteristics of the PUFI enterprise payment coordination infrastructure.

All suppliers, business entities, invoice references, and recipient endpoints are synthetic fictional constructs. Real credentials and live money movement are strictly excluded.

---

## 2. Dataset Composition

| Category | Count | Purpose & Validation Target | Key Characteristics |
|---|---|---|---|
| **Valid Obligations** | 100 | Core batch creation, standard domestic disbursement | USD amounts ($25.00 to $48,500.00), US suppliers, future due dates |
| **Duplicate Invoices** | 20 | Ingestion deduplication & DB unique constraint validation | Identical `(business_id, invoice_reference, supplier_id)` pairs |
| **Invalid Obligations** | 15 | Negative amounts, malformed decimals, invalid currencies, broken dates, orphan suppliers | 5 bad amounts, 4 invalid currencies (e.g. `XYZ`, `USDD`), 3 bad dates, 3 unknown suppliers |
| **International Payments** | 20 | Multi-currency FX spread modeling, provider eligibility filtering | Non-USD currencies (EUR, GBP, JPY, CAD, AUD) across foreign entity types |
| **Large Obligations** | 10 | Treasury limits, provider ceiling bounds, multi-approver requirements | $100,000.00 to $750,000.00 USD obligations |
| **Incomplete Suppliers** | 10 | Incomplete vendor records, missing payout endpoints | Recipient reference type `NONE`, masked reference `UNCONFIGURED` |
| **Total Obligations** | **175** | Comprehensive end-to-end reliability verification | All generated deterministically |

---

## 3. Entity Schemas

### Synthetic Business
- **ID:** `biz-synth-001`
- **Display Name:** `[SYNTHETIC] Nexus Global Enterprises Ltd`

### Synthetic Suppliers (18 Total)
1. **Domestic US Suppliers (10):** `SUP-DOM-001` to `SUP-DOM-010` (US, Email recipient, USD preferred)
2. **International Suppliers (5):**
   - `SUP-INT-001` (DE / EUR / GmbH)
   - `SUP-INT-002` (GB / GBP / Ltd)
   - `SUP-INT-003` (JP / JPY / Corp)
   - `SUP-INT-004` (CA / CAD / Inc)
   - `SUP-INT-005` (AU / AUD / Pty)
3. **Incomplete Suppliers (3):** `SUP-INC-001` to `SUP-INC-003` (US, Type `NONE`, Unconfigured)

---

## 4. How to Generate or Regenerate

The dataset is generated via `backend/extended_seed.py` using Python's pseudo-random number generator initialized with seed `42`:

```bash
cd backend

# 1. Regenerate JSON dataset only:
python extended_seed.py

# 2. Seed directly into the SQLite database:
python extended_seed.py --seed

# 3. Clean and reseed:
python extended_seed.py --seed --force
```

Target output file:
`data/synthetic_data/extended_synthetic_dataset.json`
