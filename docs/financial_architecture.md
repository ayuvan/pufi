# PUFI --- Financial Architecture Notes

## 1. Core distinction: obligation is not money

A payable record means the business intends or is required to pay. It
does not mean the funds are available, a provider accepted an
instruction, or a recipient received funds.

Track four distinct concepts: 1. **Obligation:** business accounting
intent. 2. **Instruction:** request to a payment provider. 3. **Provider
result:** status reported by the provider. 4. **Settlement evidence:**
evidence that the relevant financial movement completed.

## 2. Example

A business has five supplier obligations totalling USD 20,000. PUFI can
group them into a batch, validate recipient records, compare provider
options, and submit supported instructions.

If the business owes an Indian supplier in INR, the system must not
assume the PayPal Payouts API can perform the required USD-to-INR
conversion or deliver INR to that recipient. Model the FX and bank
settlement leg separately unless a provider's current documentation and
account configuration confirm support.

## 3. Cost model

For a route, calculate a transparent estimate:

`estimated_total_cost = provider_fee + fx_spread_cost + fixed_transfer_cost + other_configured_costs`

For an illustrative conversion:

`converted_amount = source_amount × quoted_rate`

Then apply the documented fee and rounding rules. Do not combine fees
into the exchange rate without disclosure. Display: - original amount
and currency - quote rate and source - quote timestamp and expiry -
spread/fee assumptions - estimated recipient amount - whether values are
live or simulated

Use `Decimal`, not floating-point arithmetic.

## 4. Route eligibility before optimization

First reject routes that fail hard constraints: - provider/environment
disabled - currency unsupported - recipient type unsupported - amount
outside configured limits - required funding snapshot insufficient -
compliance or approval gate not satisfied - quote expired or missing
where required

Only compare eligible routes. The cheapest route is not automatically
the best if it fails another constraint.

## 5. Liquidity planning

The prototype can use synthetic funding snapshots to demonstrate how a
coordinator might avoid assigning obligations beyond a configured
funding amount. Label them `SIMULATED` or `MANUALLY_CONFIGURED`.

PUFI cannot create funds, increase a provider's limits, or guarantee
access to liquidity. In a real deployment, funding data would require
authorized provider/bank integrations and contractual permissions.

## 6. Batch processing and partial outcomes

A batch can be accepted while individual items later have different
outcomes. Track item-level statuses and do not mark every obligation
paid just because a batch was acknowledged.

## 7. Idempotency and recovery

Each obligation has a stable business key. Each instruction has a stable
internal idempotency key. Each provider submission stores the
provider-specific batch/item identifiers.

On timeout: 1. Mark the submission `UNKNOWN`. 2. Query provider status
using known identifiers where possible. 3. Inspect webhook/provider
events. 4. Reconcile before deciding whether a retry is safe. 5. Reuse
the appropriate stable request reference for a safe retry.

Never create a new payment instruction simply because a response was
lost.

## 8. Double-entry accounting boundary

The prototype maintains an obligation/instruction/audit record model. It
is not a certified general ledger or full double-entry accounting
system. If the product evolves toward financial custody, balances, or
regulated payment services, that requires specialist accounting, legal,
compliance, and security design beyond this hackathon.

## 9. Metrics to demonstrate

-   obligations imported
-   invalid/duplicate instructions caught
-   eligible routes per batch
-   estimated provider and FX costs
-   time to prepare a batch
-   provider submission outcome
-   reconciliation exceptions
-   measured processing time at stated synthetic batch sizes

Do not claim fee savings unless a fair baseline and actual comparable
inputs are provided.
