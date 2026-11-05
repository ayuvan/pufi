# PUFI --- Enterprise Payment Coordination Infrastructure

> Hackathon prototype \| PayPal Developer Platform + AI

PUFI is a prototype enterprise payment-coordination layer. It helps a
business organize payment obligations, validate payment instructions,
compare eligible provider routes, model foreign-exchange costs, submit
supported payment operations through PayPal Sandbox, and reconcile
provider responses against an internal audit ledger.

PUFI is **not a bank, wallet, money transmitter, settlement network, or
replacement for PayPal**. It does not hold customer funds. The hackathon
build uses PayPal Sandbox and clearly labelled simulated providers and
settlement records.

## Hackathon fit

The supplied hackathon brief requires: 1. Meaningful integration with at
least one PayPal technology, API, SDK, product, or developer capability.
2. Meaningful incorporation of AI into the experience or functionality.
3. A working prototype or proof of concept. 4. Sufficient documentation
for judges. 5. Compliance with the official rules.

Sponsor tools are optional. PUFI's planned core integration is PayPal's
Payouts API in Sandbox, subject to account, product, recipient, and
country eligibility. The AI feature is an explainable decision-support
layer; deterministic rules remain responsible for payment eligibility
and execution controls.

## Core demonstration

A business imports a batch of supplier obligations. PUFI validates the
records, detects duplicates, calculates illustrative FX and
provider-cost scenarios, checks route eligibility, and presents an
explainable recommendation. An authorized user can submit a supported
test payout to PayPal Sandbox. Other provider routes remain simulated.
PUFI records each state transition and reconciles provider responses.

## Planned stack

-   Frontend: React + TypeScript
-   Backend: Python + FastAPI
-   Persistence: PostgreSQL (SQLite may be used temporarily for local
    development)
-   Provider integration: PayPal REST API / Payouts API Sandbox
-   AI: model or AI platform selected for the hackathon; constrained to
    recommendations, explanations, and anomaly flags
-   Optional later: Redis + Celery if asynchronous processing is
    justified

Do not add infrastructure merely for appearance. Keep the first working
vertical slice small.

## Repository layout

``` text
PUFI/
├── README.md
├── MASTER_HANDOFF.md
├── AGENTS.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── .gitignore
├── frontend/
├── backend/
├── data/
│   └── synthetic_data/
└── docs/
    ├── financial_architecture.md
    ├── api_specification.md
    ├── security_model.md
    └── proposal_requirements.md
```

## Local development

Exact commands will be added after the first implementation milestone
establishes the package manager, database approach, and environment
configuration.

General sequence: 1. Install supported Python and Node.js versions. 2.
Copy `.env.example` to `.env` and fill only the required local values.
3. Start the backend. 4. Start the frontend. 5. Load synthetic supplier
obligations. 6. Run the deterministic simulation before connecting
PayPal Sandbox.

Never commit `.env`, API secrets, access tokens, private keys, or real
customer data.

## Current status

This repository is a documentation-first project. No production
integration is claimed. The implementation plan identifies what must be
built and tested before any feature is described as complete.

## Important terminology

-   **Obligation:** what the business says it owes a supplier.
-   **Payment instruction:** a request to a provider to attempt a
    payment.
-   **Provider response:** the provider's reported status.
-   **Settlement:** completion through the relevant financial
    institution or provider rails. A PUFI database status is not proof
    of settlement.
-   **Simulation:** a modelled outcome, never real money movement.
-   **AI recommendation:** advisory output that must be validated by
    deterministic controls and human approval.

## Official references

-   PayPal REST API getting started:
    https://developer.paypal.com/api/get-started/
-   PayPal REST API authentication:
    https://developer.paypal.com/api/rest/authentication
-   PayPal Payouts API:
    https://developer.paypal.com/docs/payouts/standard/
-   PayPal Payouts API reference:
    https://developer.paypal.com/api/payments.payouts-batch/v1/
-   PayPal webhooks: https://developer.paypal.com/api/rest/webhooks/


---

## Day 4: Approval & PayPal Sandbox Execution

### Setup PayPal Credentials (optional)

1. Copy `.env.example` to `backend/.env`.
2. Set your PayPal Sandbox client_id and secret:
   ```
   PAYPAL_MODE=sandbox
   PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id_here
   PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret_here
   ```
3. If credentials are absent, PUFI operates in **simulated mode** (no real PayPal calls are made and results are clearly labelled `SIMULATED`).

> **Note:** `PAYPAL_MODE=sandbox` is the only accepted value. Production mode is not supported in this prototype.

### Demo workflow

Run the following commands from the project root to exercise the full Day 4 workflow:

```powershell
# 1. Seed synthetic base data (13 draft obligations)
cd backend ; .venv\Scripts\python seed.py

# 2. Create the demo batch (prints actual batch ID — do NOT hardcode it)
cd backend ; .venv\Scripts\python demo_seed.py
# Example output:
#   Batch ID : 1cc14a1c-aa96-4902-8a78-b987f932265e
#   Batch Reference : DEMO-BATCH-DAY4

# 3. Start backend
cd backend ; .venv\Scripts\uvicorn main:app --reload

# 4. Start frontend (dev)
cd frontend ; pnpm dev
```

Then open `http://localhost:5173` and:
- Go to **Batches → Create Batch** (or navigate directly to the demo batch via the Analysis page).
- Click **View Approval & Execution** on the created batch.
- Run financial analysis, review eligible providers and AI advisory.
- Complete the approval form and click **Approve for Sandbox Submission**.
- Click **Submit to PayPal Sandbox** (requires credentials) or observe simulated mode.
- Click **Refresh Status** to poll item-level statuses.

### API quick reference

```
POST /api/v1/batches/{id}/analyze?strategy=LOWEST_COST
POST /api/v1/batches/{id}/approve
POST /api/v1/batches/{id}/submit
POST /api/v1/batches/{id}/refresh-status
GET  /api/v1/batches/{id}/instructions
GET  /api/v1/batches/{id}/audit
```

### Batch lifecycle

```
DRAFT → VALIDATED → ANALYZED → APPROVED → SUBMITTED → PROCESSING → COMPLETED
                                                                   → PARTIALLY_COMPLETED
                                                                   → FAILED
```

### Financial constraints

- All amounts use Python `Decimal` / SQLite `NUMERIC`. Never binary float.
- Every amount has an explicit ISO currency code.
- PayPal Payouts support USD only in this prototype.
- Simulated provider results are explicitly labelled `SIMULATED`.
- AI advisory cannot approve batches, modify amounts, or override eligibility.
- Submission to PayPal creates a Sandbox payout (test-only). No real funds move.

### Running tests

```powershell
cd backend ; .venv\Scripts\python -m pytest tests/ -v
# Expected: 107 passed
```
