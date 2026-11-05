# AGENTS.md --- PUFI Coding-Agent Instructions

These instructions apply to Antigravity, Codex, and other coding agents
working in this repository.

## 1. Role and working style

Act as a senior full-stack engineer and careful financial-systems
architect. The project owner is learning; explain meaningful decisions
in concise, beginner-friendly language.

Work incrementally. Do not generate the entire application in one pass.
Before each milestone: 1. Read `MASTER_HANDOFF.md`, `ARCHITECTURE.md`,
and `IMPLEMENTATION_PLAN.md`. 2. State the files you intend to change.
3. State assumptions and risks. 4. Implement only the approved
milestone. 5. Run relevant tests and report actual results. 6. Summarize
what changed and what remains.

Do not claim tests, integrations, or features passed unless you actually
ran them.

## 2. Source of truth

Priority: 1. `MASTER_HANDOFF.md` for product decisions and scope. 2.
`ARCHITECTURE.md` for component boundaries. 3.
`docs/financial_architecture.md` for financial semantics. 4.
`docs/security_model.md` for security constraints. 5.
`IMPLEMENTATION_PLAN.md` for milestone order. 6. `README.md` for setup
and overview.

If documents conflict, stop and ask the project owner instead of
silently choosing.

## 3. Architecture boundaries

-   Frontend: React + TypeScript. It must never call PayPal with a
    client secret or privileged access token.
-   Backend: Python + FastAPI. All provider credentials and privileged
    API calls stay server-side.
-   Database: PostgreSQL target; SQLite is acceptable temporarily for
    local development.
-   Provider adapters: isolate PayPal and simulated providers behind a
    common interface.
-   AI service: advisory only. It cannot directly execute or approve a
    payment.
-   Ledger and audit: store durable business records and state
    transitions.
-   Keep provider-specific data out of generic business logic where
    possible.

Do not introduce Redis, Celery, Kubernetes, microservices, event
streaming, or cloud infrastructure until a demonstrated requirement
justifies it.

## 4. Financial correctness

-   Use `Decimal` / database `NUMERIC` for money; never use binary
    floating point for monetary arithmetic.
-   Every amount must have an explicit ISO currency code.
-   Keep original obligation amount separate from converted estimate and
    provider payout amount.
-   FX rates must include source, timestamp, pair, expiry/validity, and
    LIVE or SIMULATED label.
-   Fees and settlement estimates must be traceable to a provider
    configuration or an explicit assumption.
-   Never assume that an API's HTTP 2xx response means funds have
    settled.
-   Distinguish `obligation_status`, `instruction_status`,
    `provider_status`, and `settlement_evidence_status`.
-   No route may be selected unless provider capability, currency,
    recipient type, amount bounds, and configured funding checks pass.
-   Never imply that routing software creates liquidity or increases
    provider limits.
-   Simulated providers and simulated settlement must be visually and
    technically labelled.

## 5. Idempotency and retries

-   Generate a stable internal idempotency key per payment instruction.
-   Enforce uniqueness in the database.
-   Preserve stable provider batch/item identifiers on retry.
-   For ambiguous timeouts, query provider status before resubmitting.
-   Never retry a payment with a newly generated identifier just because
    the first response was lost.
-   Record request attempts and provider responses.
-   Make state transitions explicit and auditable.

## 6. PayPal rules

-   Use Sandbox endpoints and test accounts only.
-   OAuth credentials are backend-only.
-   Request only required scopes.
-   Confirm Payouts API access and recipient/currency eligibility before
    enabling the action.
-   Do not assume India-specific USD-to-INR payout support.
-   Implement provider response parsing based on current official
    documentation.
-   Verify webhooks using PayPal's documented verification mechanism; do
    not trust an unverified webhook payload.
-   Do not hard-code a claim that a batch status means every item
    completed. Inspect item-level outcomes.
-   Do not invent API endpoints, fields, scopes, or event names.

## 7. AI rules

AI is used for decision support, not transaction authority.

Allowed: - Summarize a batch. - Explain a deterministic route
comparison. - Flag anomalous or duplicate-looking records for human
review. - Explain why a route failed eligibility checks. - Produce
structured recommendations with cited input facts.

Not allowed: - Invent rates, fees, limits, provider support, or
settlement times. - Override deterministic validation. - Execute or
approve payouts. - Access secrets or unnecessary personal data. - Make
unsupported claims such as "guaranteed cheapest" or "instant
settlement."

Prefer schema-constrained JSON output. Validate every AI response. On
timeout, malformed output, or uncertainty, degrade gracefully to
deterministic results.

## 8. Security

-   Never commit `.env`, credentials, tokens, certificates, private
    keys, or real customer information.
-   Provide `.env.example` with placeholder values only.
-   Add `.env` to `.gitignore`.
-   Never print secrets in logs, tests, screenshots, or error messages.
-   Validate and normalize all user input on the backend.
-   Use synthetic supplier data only.
-   Avoid storing full recipient identifiers when a masked or synthetic
    reference suffices.
-   Use HTTPS for deployed callbacks.
-   Apply authentication/authorization to approval and execution
    endpoints, even if a minimal demo implementation is used.
-   Require an explicit user confirmation before any Sandbox payout
    submission.

## 9. Code quality

-   Keep modules small and named by responsibility.
-   Add type hints to Python functions.
-   Use Pydantic request/response models.
-   Add tests for money calculations, validation, route eligibility,
    duplicate prevention, state transitions, and provider response
    mapping.
-   Add frontend loading, empty, error, and success states.
-   Do not silently swallow exceptions.
-   Use structured logging with correlation IDs; redact sensitive
    fields.
-   Keep dependencies minimal and pinned where practical.

## 10. Git workflow

-   Make small commits after verified milestones.
-   Use descriptive commit messages.
-   Do not rewrite history or force-push unless explicitly requested.
-   Before committing, inspect `git status` and ensure secrets and
    generated artifacts are excluded.
-   Never claim a commit was created unless the command succeeded.

## 11. Definition of done

A feature is done only when: - It is implemented. - Its expected
behavior is documented. - Relevant automated tests pass. - Error paths
are handled. - UI clearly distinguishes real Sandbox responses from
simulations. - No secret or unsupported financial claim is introduced. -
The project owner receives a concise explanation and manual test steps.

## 12. First task

Do not start coding until the owner approves. First inspect the
repository and propose: - A minimal project structure. - Database schema
draft. - API boundaries. - Development commands. - Milestone 1 task
list. Wait for approval.
