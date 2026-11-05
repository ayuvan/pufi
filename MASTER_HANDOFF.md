# PUFI --- Master Handoff Document

**Purpose:** Single source of truth for the product concept, decisions,
architecture, scope, risks, milestones, and hackathon demonstration.

**Status:** Architecture direction agreed; implementation not yet
verified.

## 1. Product definition

PUFI (working name: **Enterprise Payment Coordination Infrastructure**)
is an enterprise-facing coordination layer designed to organize and
analyze complex payment workloads across supported payment providers.

It is not intended to replace PayPal, create a new bank, hold customer
balances, or independently settle funds. Its value hypothesis is that a
business may benefit from one workflow that combines obligation
management, validation, funding-aware planning, provider eligibility,
cost/FX analysis, execution tracking, and reconciliation.

## 2. Originating problem and use cases

The original idea explored several payment experiences: - Buying
products directly from social media through a PayPal-powered checkout
experience. - Paying many suppliers or farms through preconfigured
payment pathways. - Cross-border business payments where an American
company pays suppliers in India and needs currency conversion. -
Organizing employee or contractor payouts. - Improving the handling of
large enterprise payment workloads, transaction costs, and operational
reliability.

For this hackathon, the scope is narrowed to the most coherent technical
foundation: **enterprise bulk-payment coordination and reconciliation**.
Social commerce checkout and a full employee wallet/payroll product are
future product directions, not first-week deliverables.

## 3. Objectives

The prototype should demonstrate: 1. **Coordination:** one enterprise
workflow for multiple payment obligations. 2. **Cost visibility:**
transparent comparison of known or simulated provider fees and FX
assumptions. 3. **Eligibility-aware routing:** only recommend routes
that pass explicit constraints. 4. **Integrity:** prevent accidental
duplicate instruction submission and preserve an audit trail. 5.
**Operational visibility:** track each obligation, instruction, provider
response, and reconciliation result. 6. **AI assistance:** explain
trade-offs and flag unusual patterns without controlling money movement.

Do not claim that PUFI increases the settlement capacity of PayPal or
any bank. Coordination can improve workload management; it cannot create
liquidity, provider authorization, or settlement capacity.

## 4. Hackathon requirements from the supplied screenshots

The project must: - Build or update an application integrating the
PayPal developer platform using the free Sandbox environment. -
Integrate an AI tool, model, or platform of choice. - Meaningfully
integrate at least one PayPal technology/API/SDK/product/developer
capability. - Meaningfully incorporate AI into the experience or
functionality. - Demonstrate a working prototype or proof of concept. -
Be documented sufficiently for judges. - Comply with official rules.

Sponsor tools listed in the brief are optional, not mandatory: AG Grid,
APIMatic, Astropods, Bryntum, Channel3, Elastic, KERNEL, Postman,
Render, and Zapier. Do not add one unless it materially helps and is
available in time.

## 5. Agreed technical direction

-   Combined provider model: PayPal Sandbox integration plus simulated
    external providers.
-   Web-first prototype: React + TypeScript frontend, Python + FastAPI
    backend.
-   Database: PostgreSQL target; SQLite acceptable as a temporary
    local-development shortcut if documented.
-   AI: decision-support and explanation, constrained by deterministic
    rules.
-   Optional asynchronous infrastructure: Redis/Celery only if needed
    after the vertical slice works.
-   Git repository with incremental commits.
-   Antigravity as primary coding agent; Codex/ChatGPT for architecture
    review, debugging, and prompt preparation.

Android Studio/Kotlin is not required for this web-first PUFI prototype.
Do not create a second mobile app unless the hackathon requirements or
team decision changes.

## 6. Product workflow

1.  Business user imports or creates obligations.
2.  PUFI normalizes amounts, currencies, recipient references, due
    dates, and business metadata.
3.  Validation checks required fields, recipient format, amount bounds,
    duplicate obligation keys, and policy constraints.
4.  Liquidity planner receives an explicitly configured funding
    snapshot. For the prototype this is synthetic or manually entered;
    it is not a live bank balance.
5.  Provider capability registry describes each route's supported
    currencies, recipient types, limits, fees, and whether it is live
    Sandbox or simulated.
6.  Cost engine calculates comparable estimated cost using documented
    assumptions.
7.  AI produces a structured recommendation and human-readable
    explanation from sanitized, bounded inputs.
8.  Deterministic policy engine independently checks eligibility and
    constraints.
9.  Human approval is required before a Sandbox payout submission.
10. Provider adapter submits supported requests or a simulator records a
    simulated outcome.
11. PUFI stores request identifiers, provider references, responses, and
    state transitions.
12. Reconciliation compares expected instruction state with provider
    status and flags unresolved differences.

## 7. Financial architecture concepts

### Obligation ledger

Records the business's payable intent. An obligation is not proof that
money has moved.

### Payment instruction

An instruction derived from one or more obligations and submitted to a
provider. It has its own unique internal identifier and idempotency key.

### Funding / liquidity snapshot

A time-stamped representation of funds the business says are available
for a route. In the prototype, it is synthetic or manually configured.
Never call it a verified bank balance.

### Provider capability registry

Stores provider-specific supported operations, currencies, recipient
types, limits, fee models, and environment labels. Unknown capabilities
default to unavailable.

### FX quote model

Stores source, quote timestamp, base/quote currency, rate, spread/fee
assumption, expiry, and whether the quote is live or simulated. Never
label a hard-coded demo rate as a live rate.

### Routing optimizer

Filters ineligible routes first, then compares eligible routes using
explicit criteria such as estimated cost, expected processing time,
operational risk, and available simulated funding. It must not route
based solely on an AI-generated answer.

### Execution coordinator

Uses provider-specific adapters. It tracks submission, acknowledgement,
processing, success, denial, cancellation, timeout, and unknown states
without assuming that an HTTP success means final settlement.

### Reconciliation engine

Compares internal instruction records with provider batch/item details
and available webhook events. Differences are placed into an exception
queue for review.

## 8. AI design

Working feature name: **PUFI AI Decision Support**.

AI tasks: - Explain why a route is eligible or ineligible using
structured facts supplied by the backend. - Summarize cost and FX
trade-offs. - Identify suspicious patterns in synthetic obligations (for
example, repeated invoice identifiers, unusual amount changes, or
inconsistent supplier details). - Explain why an instruction was held
for review. - Generate a plain-language batch summary for the business
user.

AI must not: - Invent exchange rates, provider fees, provider limits, or
settlement times. - Override provider capability checks or deterministic
policy rules. - Submit, approve, or release payments. - Treat a
simulated provider as a real provider. - Receive API secrets, full
payment credentials, or unnecessary personal data.

Use structured JSON output with evidence references to the input fields.
If AI output is malformed, unavailable, or contradictory, fall back to
deterministic results and show that AI assistance was unavailable.

## 9. PayPal integration boundary

Target integration: PayPal Payouts API in Sandbox, if the developer
account and required permissions make it available.

The backend should: - Obtain OAuth 2.0 access tokens using server-side
credentials. - Submit only supported test payout requests. - Persist
PayPal batch and item references. - Query batch/item status where
supported. - Handle duplicate prevention using stable sender batch
identifiers and request idempotency where applicable. - Verify webhook
messages before trusting event content. - Treat Sandbox as test-only.

Important: Payouts availability, recipient eligibility, supported
currencies, country rules, account permissions, and limits are
controlled by PayPal. Do not assume a USD-to-INR payout to an Indian
recipient is supported. For India-specific FX and bank settlement, use a
clearly labelled simulation unless a separate eligible provider
integration is verified.

PayPal Payouts already supports batch payouts and duplicate protections.
PUFI's differentiation must therefore be evaluated as cross-provider
orchestration, obligation-to-instruction traceability, cost/FX scenario
analysis, and reconciliation---not the invention of bulk payouts or
idempotency.

## 10. Security and reliability principles

-   Secrets only on backend in environment variables or a secrets
    manager.
-   Never expose PayPal client secret or access token to browser code.
-   Validate every request server-side.
-   Use least privilege and explicit human approval.
-   Use unique idempotency keys and database constraints.
-   Do not automatically retry ambiguous payment submissions with a new
    identifier.
-   On timeout, query provider status before deciding whether a retry is
    safe.
-   Verify webhook signatures using PayPal's documented verification
    flow.
-   Store minimal recipient data; use synthetic data in the demo.
-   Keep immutable audit events for key state transitions.
-   Separate sandbox, simulation, and production configuration.
-   No production money movement is in scope.

## 11. Prototype data model (initial)

-   `businesses`
-   `suppliers`
-   `obligations`
-   `payment_batches`
-   `payment_instructions`
-   `provider_capabilities`
-   `funding_snapshots`
-   `fx_quotes`
-   `provider_submissions`
-   `provider_events`
-   `reconciliation_records`
-   `audit_events`
-   `ai_recommendations`

Use decimal/numeric types for monetary amounts; never binary floating
point. Store currency codes explicitly. Define rounding rules per
currency.

## 12. Success criteria

A judge should be able to: 1. Load a synthetic batch of supplier
obligations. 2. See validation results and duplicate flags. 3. Compare
at least two provider routes, with one being clearly marked simulated if
necessary. 4. View an AI explanation grounded in the displayed facts. 5.
Approve a supported Sandbox action. 6. See the provider response and its
mapped PUFI status. 7. Inspect the audit trail and reconciliation
result. 8. Distinguish clearly between Sandbox provider events and
simulated external settlement.

Performance targets (100 / 1,000 / 10,000 instructions) are test
scenarios, not promised results. Record actual environment, runtime, and
measurements.

## 13. Explicit non-goals

-   Building a bank, wallet, stored-value account, or money transmitter.
-   Holding, pooling, or lending customer funds.
-   Creating new payment rails or bypassing provider limits.
-   Real cross-border INR settlement.
-   Production payroll.
-   Social-media checkout integration.
-   Real-time multi-bank connectivity.
-   Autonomous AI payment execution.
-   Production compliance certification.

## 14. Risks and open questions

  -----------------------------------------------------------------------
  Question / risk                     Required response
  ----------------------------------- -----------------------------------
  Payouts API access unavailable      Keep adapter interface and
                                      demonstrate mock provider; document
                                      blocker honestly.

  PayPal Sandbox recipient/currency   Test eligibility early; do not
  restrictions                        assume India payout support.

  AI output is unreliable             Constrain input/output;
                                      deterministic checks remain
                                      authoritative.

  FX data unavailable                 Use labelled synthetic quote
                                      scenarios.

  Time is limited                     Complete one end-to-end vertical
                                      slice before adding infrastructure.

  Novelty overstated                  Compare with PayPal's existing
                                      Payouts API and describe PUFI's
                                      incremental orchestration
                                      hypothesis.

  Sandbox status mistaken for         Show exact provider status and a
  settlement                          separate settlement-evidence field.
  -----------------------------------------------------------------------

## 15. Six-day delivery sequence

See `IMPLEMENTATION_PLAN.md`. Priority order: 1. App scaffold and
synthetic data. 2. Obligation ledger and validation. 3. Cost/FX and
provider routing. 4. AI decision support. 5. PayPal Sandbox adapter and
reconciliation. 6. Testing, screenshots, proposal, demo script.

## 16. Sources to verify during implementation

-   PayPal REST API getting started:
    https://developer.paypal.com/api/get-started/
-   OAuth authentication:
    https://developer.paypal.com/api/rest/authentication
-   Payouts integration:
    https://developer.paypal.com/docs/payouts/standard/
-   Payouts API reference:
    https://developer.paypal.com/api/payments.payouts-batch/v1/
-   Payout batch status:
    https://developer.paypal.com/api/payments.payouts-batch/v1/payouts-get/
-   Webhooks: https://developer.paypal.com/api/rest/webhooks/
-   Webhook verification:
    https://developer.paypal.com/api/rest/webhooks/
-   PayPal API specifications:
    https://github.com/paypal/paypal-rest-api-specifications

Always re-check current product eligibility, country availability, API
scopes, limits, and rules before implementation or any proposal claim.
