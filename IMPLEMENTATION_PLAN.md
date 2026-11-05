# PUFI --- Six-Day Implementation Plan

**Rule:** A working end-to-end vertical slice is more valuable than many
unfinished modules. Adjust the calendar to the actual submission
deadline.

## Priority legend

-   P0: required for a credible demo
-   P1: useful if time remains
-   P2: explicitly defer

## Day 1 --- Repository and first vertical slice (P0)

-   [ ] Initialize Git and inspect project tree.
-   [ ] Scaffold React + TypeScript.
-   [ ] Scaffold FastAPI backend.
-   [ ] Add health endpoint and frontend API connection.
-   [ ] Define initial data models.
-   [ ] Create synthetic supplier and obligation records.
-   [ ] Document local run commands.

**Acceptance:** frontend loads, backend health check succeeds, synthetic
obligations appear.

## Day 2 --- Obligation ledger and validation (P0)

-   [ ] Create obligation CRUD/import path.
-   [ ] Validate amount, currency, invoice reference, recipient
    reference.
-   [ ] Add duplicate detection using a stable business key.
-   [ ] Add batch summary and validation result UI.
-   [ ] Add unit tests for money parsing and duplicate detection.

**Acceptance:** invalid and duplicate records are visibly rejected or
held; no payout is submitted.

## Day 3 --- Cost, FX, routing, and AI (P0)

-   [ ] Define provider capability registry.
-   [ ] Add at least one simulated provider route.
-   [ ] Implement deterministic eligibility filtering.
-   [ ] Implement transparent fee/FX scenario calculations.
-   [ ] Add AI explanation and anomaly-summary feature.
-   [ ] Validate AI output against backend-eligible route IDs.
-   [ ] Add fallback behavior when AI is unavailable.

**Acceptance:** a batch can be compared across eligible routes and AI
explains the facts without changing the decision constraints.

## Day 4 --- PayPal Sandbox (P0, subject to access)

-   [ ] Create PayPal Developer Sandbox app and test accounts.
-   [ ] Store credentials in backend environment variables.
-   [ ] Implement OAuth token retrieval server-side.
-   [ ] Confirm Payouts API access and scope.
-   [ ] Submit a small test batch only after explicit user approval.
-   [ ] Persist provider batch/item identifiers and responses.
-   [ ] Query payout status and map provider status accurately.

**Fallback:** if Payouts API permission or recipient eligibility blocks
the test, demonstrate the adapter contract with a simulator and clearly
document the integration blocker. Do not fake a PayPal response.

## Day 5 --- Reconciliation, reliability, and testing (P0)

-   [ ] Add state-transition audit events.
-   [ ] Add stable idempotency identifiers and database uniqueness.
-   [ ] Handle timeout/unknown state without blind resubmission.
-   [ ] Add webhook verification if a reachable HTTPS endpoint is
    available.
-   [ ] Add reconciliation screen.
-   [ ] Test provider denial, timeout, duplicate, partial batch result,
    and malformed AI response.
-   [ ] Run synthetic load tests at 100, 1,000, and 10,000 records if
    time permits.

**Acceptance:** failures remain visible; ambiguous submissions do not
become success; test measurements are recorded honestly.

## Day 6 --- Judge-ready packaging (P0)

-   [ ] Capture screenshots of the real working app.
-   [ ] Prepare architecture diagram.
-   [ ] Prepare a concise demo dataset.
-   [ ] Write proposal using official judging format when supplied.
-   [ ] Prepare 3--5 minute demo script.
-   [ ] Add setup instructions and known limitations.
-   [ ] Run clean-start test from documented instructions.
-   [ ] Check Git status for secrets.

## P1 backlog

-   [ ] CSV upload and downloadable reconciliation report.
-   [ ] Better batch filters and search.
-   [ ] AI-generated natural-language exception explanations.
-   [ ] Provider fee configuration editor.
-   [ ] Audit log export.
-   [ ] AG Grid or another sponsor tool only if it improves the actual
    UI.

## P2 / out of scope

-   Real bank connectivity.
-   Production INR settlement.
-   Production payroll.
-   Mobile app.
-   Social commerce checkout.
-   Autonomous payments.
-   Multi-tenant enterprise identity and compliance program.
-   Microservices and complex infrastructure.

## Daily review checklist

1.  What works end-to-end today?
2.  What tests were run and what failed?
3.  Which assumptions remain unverified?
4.  What is the next smallest valuable milestone?
5.  Is the prototype still aligned with the hackathon brief?
