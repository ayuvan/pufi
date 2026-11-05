# PUFI --- System Architecture

## 1. Architecture goal

Build a small, auditable modular application that coordinates payment
obligations and provider instructions. Prefer a modular monolith over
microservices for the hackathon prototype.

## 2. Logical architecture

``` text
React + TypeScript
       |
       | HTTPS / JSON
       v
FastAPI application
       |
       +--> Obligation & batch service
       +--> Validation / duplicate service
       +--> Funding snapshot service
       +--> FX quote & cost model
       +--> Provider capability registry
       +--> Deterministic routing engine
       +--> AI decision-support adapter
       +--> Approval & execution coordinator
       +--> Reconciliation & audit service
                    |
                    +--> PostgreSQL
                    |
                    +--> PayPal Sandbox adapter
                    |
                    +--> Simulated provider adapter(s)
```

## 3. Component responsibilities

  -----------------------------------------------------------------------
  Component               Responsibility          Must not do
  ----------------------- ----------------------- -----------------------
  Frontend                Import obligations,     Hold secrets or decide
                          show analysis, request  provider eligibility
                          approval, display       
                          status                  

  API layer               Authentication, schema  Perform unvalidated
                          validation, request     money calculations
                          orchestration           

  Obligation service      Store business payable  Claim funds were sent
                          intent                  

  Validation service      Check data quality,     Alter source values
                          duplicate keys, policy  silently
                          limits                  

  Funding planner         Evaluate configured     Pretend synthetic data
                          funding snapshots       is a live bank balance

  FX/cost engine          Calculate transparent   Present demo rates as
                          estimates               live quotes

  Routing engine          Filter ineligible       Override provider
                          providers and score     restrictions
                          eligible routes         

  AI adapter              Explain/flag based on   Approve or execute a
                          bounded structured      payment
                          input                   

  Execution coordinator   Submit via provider     Treat request
                          adapter and track       acceptance as
                          attempts                settlement

  Provider adapter        Translate generic       Leak provider-specific
                          instruction to provider assumptions
                          API                     

  Reconciliation          Compare internal        Mark unknown outcomes
                          records with provider   as success
                          evidence                

  Audit service           Append state changes    Allow silent deletion
                          and actor/action        of financial history
                          metadata                
  -----------------------------------------------------------------------

## 4. Main workflow

``` text
IMPORT
  -> NORMALIZE
  -> VALIDATE
  -> DUPLICATE CHECK
  -> FUNDING / CAPABILITY CHECK
  -> COST & FX ANALYSIS
  -> AI EXPLANATION
  -> DETERMINISTIC POLICY CHECK
  -> HUMAN APPROVAL
  -> PROVIDER SUBMISSION
  -> PROVIDER STATUS QUERY / WEBHOOK
  -> RECONCILIATION
  -> REPORT
```

## 5. State model

Keep separate state dimensions.

### Obligation status

`DRAFT`, `VALIDATED`, `ON_HOLD`, `READY`, `CLOSED`, `CANCELLED`

### Instruction status

`CREATED`, `APPROVED`, `SUBMISSION_PENDING`, `SUBMITTED`, `UNKNOWN`,
`COMPLETED`, `FAILED`, `CANCELLED`

### Provider status

Store the raw provider status and a normalized mapping. Preserve the
original response metadata needed for support and audit, with secrets
removed.

### Settlement evidence

`NOT_APPLICABLE`, `NOT_CONFIRMED`, `PROVIDER_REPORTED_COMPLETE`,
`EXTERNAL_EVIDENCE_REQUIRED`, `RECONCILED`, `EXCEPTION`

Do not collapse these into one generic "paid" boolean.

## 6. Initial database entities

### suppliers

`id`, `display_name`, `country_code`, `recipient_reference_masked`,
`created_at`

### obligations

`id`, `business_id`, `supplier_id`, `invoice_reference`,
`amount_minor_or_decimal`, `currency`, `due_at`, `status`,
`source_hash`, `created_at`

### payment_batches

`id`, `business_id`, `batch_reference`, `status`, `created_at`,
`approved_by`, `approved_at`

### payment_instructions

`id`, `batch_id`, `obligation_id`, `provider_code`, `amount`,
`currency`, `idempotency_key`, `status`, `created_at`

### provider_capabilities

`id`, `provider_code`, `environment`, `supported_currencies`,
`recipient_types`, `minimum_amount`, `maximum_amount`, `fee_model`,
`enabled`, `last_verified_at`

### funding_snapshots

`id`, `provider_code`, `currency`, `available_amount`, `source_type`,
`observed_at`, `is_simulated`

### fx_quotes

`id`, `base_currency`, `quote_currency`, `rate`, `spread_bps`,
`fee_amount`, `source`, `quoted_at`, `expires_at`, `is_simulated`

### provider_submissions

`id`, `instruction_id`, `provider_batch_id`, `provider_item_id`,
`attempt_number`, `request_reference`, `response_status`,
`submitted_at`, `response_at`

### provider_events

`id`, `provider_code`, `provider_event_id`, `event_type`, `received_at`,
`verified`, `payload_redacted`

### reconciliation_records

`id`, `instruction_id`, `internal_status`, `provider_status`, `result`,
`difference_reason`, `checked_at`

### ai_recommendations

`id`, `batch_id`, `model_name`, `input_summary_hash`,
`recommendation_json`, `created_at`, `fallback_used`

### audit_events

`id`, `entity_type`, `entity_id`, `event_type`, `actor`,
`correlation_id`, `details_redacted`, `created_at`

Use database `NUMERIC` and Python `Decimal` for amounts. A
production-grade ledger may require double-entry accounting and formal
controls; that is outside the first prototype.

## 7. Provider adapter interface

Define a generic interface such as: - `capabilities()` -
`validate_instruction(instruction)` -
`submit_batch(batch, idempotency_reference)` -
`get_batch_status(provider_batch_id)` -
`get_item_status(provider_item_id)` -
`verify_event(request_headers, raw_body)`

PayPal adapter and simulated adapter implement the same interface. The
simulator must return an explicit `SIMULATED` environment marker.

## 8. AI interaction contract

Backend sends only a compact, sanitized decision context: - eligible
routes and reasons - estimated fees and FX assumptions - processing
constraints - anomaly flags from deterministic checks - batch-level
summary statistics

AI returns: - `summary` - `recommended_route` - `reasoning_factors` -
`warnings` - `requires_human_review` - `evidence_fields`

The backend validates that the recommended route is among the already
eligible routes. AI cannot add a route or change an amount.

## 9. API outline

See `docs/api_specification.md`. All execution endpoints require
authorization and explicit approval state.

## 10. Deployment shape

For the demo, one backend service, one frontend service, and one
database are sufficient. A local demo is acceptable if the judging
instructions permit it. A public deployment is optional and must not
expose secrets or unprotected payout actions.
