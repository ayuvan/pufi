# PUFI --- Security Model

## Scope

This is a hackathon prototype security baseline, not a security
certification or production compliance assessment.

## Assets to protect

-   PayPal Sandbox client secret and access tokens.
-   Synthetic recipient references and business records.
-   Approval state and payment instructions.
-   Provider response and webhook integrity.
-   Audit history.

## Trust boundaries

1.  Browser to backend: treat all browser input as untrusted.
2.  Backend to AI provider: send only minimized, sanitized context.
3.  Backend to PayPal: server-side OAuth and API calls only.
4.  PayPal webhook to backend: verify authenticity before processing.
5.  Simulated provider: never mix simulation records with real Sandbox
    responses without explicit labels.

## Required controls

-   Secrets in environment variables, never frontend bundles.
-   `.env` ignored by Git; `.env.example` contains placeholders only.
-   Server-side validation and authorization.
-   Explicit human approval before Sandbox submission.
-   Stable idempotency identifiers and uniqueness constraints.
-   Redacted structured logs.
-   Minimal data retention.
-   Synthetic data only in the demo.
-   HTTPS for externally reachable webhook endpoints.
-   Dependency updates and basic static checks where time permits.

## AI-specific controls

-   Do not send secrets, full payment credentials, or unnecessary
    personal data to the model.
-   AI recommendations are advisory.
-   Backend verifies every proposed route against the deterministic
    eligible-route set.
-   AI cannot change amounts, recipients, approval status, or payment
    status.
-   Record model identity, sanitized input summary hash, and output for
    reproducibility.
-   Handle malformed output and model unavailability safely.

## Incident / failure handling

If a credential is exposed, revoke/rotate it in the provider dashboard
and remove it from repository history as appropriate. Do not merely
delete the visible line and assume the credential is safe.

If a payment submission times out, do not blindly resubmit. Query
provider status and reconcile first.

If webhook verification fails, reject the event and log a redacted
security event.

## Demo safety

Use Sandbox accounts and synthetic suppliers. Never ask a judge to
provide bank credentials, real recipient financial details, or real
funds.
