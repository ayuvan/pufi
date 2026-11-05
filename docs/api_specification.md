# PUFI --- Initial API Specification

This is a proposed interface contract. Implement only endpoints needed
for the approved milestone.

## General conventions

-   JSON over HTTPS.
-   Version prefix: `/api/v1`.
-   Monetary values are decimal strings plus ISO currency codes.
-   Use server-side authorization for approvals and execution.
-   Return a correlation ID for support and audit.
-   Never return secrets or raw sensitive provider payloads.

## Proposed endpoints

  -----------------------------------------------------------------------------------------
  Method                  Path                                      Purpose
  ----------------------- ----------------------------------------- -----------------------
  GET                     `/api/v1/health`                          Service health

  GET                     `/api/v1/obligations`                     List obligations

  POST                    `/api/v1/obligations/import`              Import synthetic/CSV
                                                                    obligations

  POST                    `/api/v1/batches`                         Create batch from
                                                                    selected obligations

  GET                     `/api/v1/batches/{batch_id}`              Batch detail and
                                                                    validation

  POST                    `/api/v1/batches/{batch_id}/validate`     Run deterministic
                                                                    validation

  POST                    `/api/v1/batches/{batch_id}/analyze`      Calculate cost/FX and
                                                                    AI explanation

  POST                    `/api/v1/batches/{batch_id}/approve`      Record human approval

  POST                    `/api/v1/batches/{batch_id}/submit`       Submit approved
                                                                    supported Sandbox
                                                                    instructions

  GET                     `/api/v1/instructions/{instruction_id}`   Instruction status

  POST                    `/api/v1/reconciliation/run`              Reconcile selected
                                                                    instructions

  GET                     `/api/v1/audit`                           View audit events
  -----------------------------------------------------------------------------------------

## Example obligation

``` json
{
  "supplier_reference": "SUP-001",
  "invoice_reference": "INV-2026-001",
  "amount": "1250.00",
  "currency": "USD",
  "due_at": "2026-11-10"
}
```

## Example analysis response

``` json
{
  "batch_id": "BATCH-DEMO-001",
  "eligible_routes": [
    {
      "provider_code": "SIM_PROVIDER_A",
      "environment": "SIMULATED",
      "estimated_cost": "12.50",
      "currency": "USD"
    }
  ],
  "excluded_routes": [
    {
      "provider_code": "PAYPAL_SANDBOX",
      "reason_code": "RECIPIENT_CURRENCY_NOT_CONFIRMED"
    }
  ],
  "ai_assistance": {
    "summary": "The simulated route is eligible under the configured demo assumptions.",
    "recommended_route": "SIM_PROVIDER_A",
    "requires_human_review": true
  }
}
```

This example is illustrative, not a live PayPal capability statement.

## Error response

``` json
{
  "error": {
    "code": "BATCH_NOT_APPROVED",
    "message": "The batch must be approved before submission."
  },
  "correlation_id": "corr-demo-001"
}
```

## Execution safeguards

-   `/submit` must reject unapproved batches.
-   The backend re-runs critical eligibility checks at submission time.
-   The frontend cannot set a batch to approved by changing local state.
-   Submission requires a stable idempotency key.
-   A timeout results in an `UNKNOWN` state pending provider lookup.
-   Webhook endpoints verify the provider signature before applying an
    event.
