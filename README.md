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
