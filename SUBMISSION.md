# PUFI — Enterprise Payment Coordination & Intelligent Routing Infrastructure

> **Hackathon Prototype | PayPal Developer Platform + AI**

## 1. Project Overview

**PUFI (Enterprise Payment Coordination & Intelligent Routing Infrastructure)** is an AI-assisted enterprise payment orchestration platform designed to simplify and coordinate large volumes of business-to-business payments.

Businesses frequently need to pay multiple suppliers, manage different currencies, compare payment providers, and maintain accurate financial records. Handling these operations across disconnected systems can create unnecessary costs, duplicate transactions, delays, and reconciliation difficulties.

PUFI addresses these challenges through a unified platform that:

- Imports and validates bulk supplier payment obligations.
- Detects duplicate and invalid payment records.
- Calculates illustrative foreign-exchange costs and transaction fees.
- Evaluates eligible payment providers using deterministic routing rules.
- Uses Google Gemini Flash for explainable financial decision support.
- Requires authorised human approval before payment submission.
- Integrates with PayPal Payouts API through its Sandbox environment.
- Maintains an audit trail of payment instructions, decisions, and provider responses.

**Project scope:** PUFI is a payment coordination and orchestration prototype. It is not a bank, digital wallet, money transmitter, settlement network, or replacement for PayPal. It does not hold customer funds or independently increase the transaction capacity of payment providers.

---

## 2. The Problem We Aim to Solve

Enterprises, particularly multinational businesses, face several operational challenges when coordinating supplier payments across multiple providers and currencies.

### 2.1 Fragmented Payment Operations

Businesses often use different banking portals and payment services to process supplier payments. Managing these independently makes it difficult to maintain a unified view of payment obligations and execution statuses.

### 2.2 Transaction Costs and Foreign Exchange

Cross-border transactions involve exchange-rate differences, conversion spreads, transaction fees, and potentially different processing times.

Without a consolidated comparison, finance teams may struggle to identify cost-effective payment routes.

### 2.3 Duplicate Payments and Accounting Errors

Manually managing large numbers of invoices can result in duplicate payment instructions, incorrect amounts, missing supplier references, and inconsistent accounting records.

### 2.4 Limited Payment Traceability

When payments are distributed across multiple providers, tracking their progress and reconciling provider responses becomes difficult.

### 2.5 Responsible AI in Financial Operations

AI can analyse information and provide recommendations, but allowing an AI model to independently authorise financial transactions introduces unacceptable reliability and accountability risks.

PUFI addresses this by separating AI recommendations from deterministic financial controls and human authorisation.

---

## 3. Proposed Solution

PUFI introduces a unified payment coordination layer between enterprise payment obligations and external payment providers.

Its primary objective is to make payment operations more organised, cost-aware, explainable, and traceable.

### Core Capabilities

**1. Bulk Payment Management**

Businesses can organise multiple supplier obligations into payment batches rather than handling each payment independently.

**2. Financial Validation**

The backend validates payment amounts, currencies, invoice references, and other required information. Duplicate records are identified before payment execution.

**3. Foreign Exchange and Fee Analysis**

PUFI models currency conversion costs, exchange-rate spreads, transaction fees, and provider-specific cost scenarios using precise decimal arithmetic.

**4. Intelligent Payment Routing**

The routing engine compares eligible providers and evaluates payment routes according to:

- Lowest estimated cost.
- Fastest estimated processing time.
- Balanced cost and processing-time considerations.

**5. AI-Assisted Decision Support**

Google Gemini Flash analyses the available payment information and explains provider comparisons, potential anomalies, and routing recommendations.

**6. Human-Controlled Execution**

Payment execution requires an authorised human approval. AI cannot approve transactions, modify financial amounts, or override provider eligibility restrictions.

**7. Payment Tracking and Reconciliation**

PUFI records payment instructions, provider responses, status changes, and relevant audit events.

---

## 4. What Has Been Implemented?

The current prototype demonstrates the following capabilities.

| Feature | Implementation status | Description |
|---|---|---|
| Bulk obligation management | Implemented | Import and organise supplier payment obligations |
| Payment validation | Implemented | Validate amounts, currencies, dates, and required fields |
| Duplicate detection | Implemented | Identify duplicate payment obligations |
| Batch management | Implemented | Group obligations into payment batches |
| Decimal-based calculations | Implemented | Avoid binary floating-point arithmetic for financial calculations |
| FX cost modelling | Implemented | Calculate illustrative currency conversion costs and spreads |
| Provider comparison | Implemented | Compare eligible simulated and Sandbox payment routes |
| Intelligent routing | Implemented | Lowest-cost, fastest, and balanced routing strategies |
| Gemini AI advisory | Implemented | Explain recommendations and identify potential anomalies |
| Human approval workflow | Implemented | Require approval before payment submission |
| PayPal Payouts integration | Sandbox integration implemented | Submit supported test payout requests when credentials and provider eligibility permit |
| Payment idempotency | Implemented | Use stable identifiers and submission guards to reduce duplicate payout risk |
| Payment status tracking | Implemented | Track provider-reported item-level payment statuses |
| Webhook receiver | Implemented in code | Receive PayPal events and perform signature verification |
| Audit trail | Implemented | Record important financial workflow events and state transitions |
| AI fallback mechanism | Implemented | Preserve deterministic analysis when the AI service is unavailable |
| Demo access control | Implemented | API-key protection for approval and submission endpoints |

### Implementation boundaries

The following distinctions are important:

- A PayPal Sandbox submission is a test operation, not a real financial transfer.
- Simulated provider responses do not represent actual bank transactions.
- FX calculations use illustrative quotes rather than live market rates.
- A submitted payment is not automatically considered settled.
- Webhook verification implemented in code does not establish that external webhook delivery has been successfully tested.

---

## 5. Implemented Features vs. Future Scope

PUFI began with a broader ambition to simplify enterprise financial operations, including cross-border supplier payments, employee payments, and social-commerce transactions.

The current hackathon prototype focuses on payment coordination and routing rather than implementing an entire financial infrastructure.

| Original ambition / Feature | Current status | Scope or limitation |
|---|---|---|
| Bulk supplier payments | Implemented | Demonstrated through synthetic obligations and batches |
| Intelligent payment routing | Implemented | Deterministic routing across eligible providers |
| PayPal integration | Implemented | Sandbox environment only |
| AI-assisted financial analysis | Implemented | Advisory functionality, not transactional authority |
| FX cost comparison | Implemented | Simulated exchange rates and conversion costs |
| Duplicate payment prevention | Implemented | Validation, idempotency identifiers, and submission guards |
| Human approval | Implemented | Demo API-key access control and approval workflow |
| Payment reconciliation | Partially implemented | Internal records and provider-reported statuses; no independent bank reconciliation |
| Multiple payment providers | Partially implemented | PayPal Sandbox plus simulated wire and ACH providers |
| Real-time FX rates | Not implemented | Requires a live FX data provider |
| Actual USD-to-INR settlement | Not implemented | Requires supported cross-border payment and settlement infrastructure |
| Real bank connectivity | Not implemented | No direct banking network integration |
| Live bank balance verification | Not implemented | Funding snapshots are simulated |
| Production employee payroll | Not implemented | No real payroll or wage-distribution infrastructure |
| Social-media checkout integration | Not implemented | Original concept for purchasing products directly from social platforms |
| Production-grade identity management | Not implemented | Demo API-key mechanism; production OAuth2/JWT and role-based access control are future requirements |
| Production-scale infrastructure | Not implemented | SQLite is used for the current local demonstration |
| Increased PayPal transaction capacity | Outside current scope | PUFI coordinates payment operations but cannot increase a provider's actual capacity or liquidity |

**The distinction:** The implemented prototype demonstrates the coordination, analysis, routing, approval, and tracking of payment operations. Actual banking, live cross-border settlement, and production financial services remain future development goals.

---

## 6. System Architecture and Technology Stack

PUFI uses a frontend-backend architecture with separate financial services and external provider integrations.

### A. Frontend — React + TypeScript + Vite

The frontend provides the interface for business operators.

Main modules:

- **Obligations Ledger:** Displays supplier obligations, amounts, currencies, and validation results.
- **Batch Management:** Groups validated obligations into payment batches.
- **Financial Analysis Hub:** Displays provider comparisons, FX estimates, and routing recommendations.
- **Approval and Execution Console:** Provides human approval and payment submission controls.
- **Global Audit Trail:** Displays recorded system events and payment status changes.

### B. Backend — Python + FastAPI

The backend manages the financial workflow and enforces business rules.

Main services:

- Validation Engine.
- Obligation and Batch Management.
- FX and Fee Calculation Engine.
- Provider Capability Registry.
- Deterministic Routing Engine.
- Payment Execution Coordinator.
- Approval Service.
- Reconciliation and Status Tracking.
- Audit Event Management.
- PayPal Webhook Receiver.

### C. Artificial Intelligence — Google Gemini Flash

Gemini Flash provides decision-support functionality.

It is used to:

- Explain provider comparisons.
- Summarise financial analysis.
- Highlight potential anomalies.
- Provide understandable routing recommendations.

The AI operates under strict constraints. Payment eligibility, approval, financial calculations, and execution remain controlled by backend logic.

When the AI service is unavailable or produces an unusable response, PUFI can fall back to deterministic analysis.

### D. Persistence — SQLite

SQLite is used for local development and the hackathon demonstration.

The database stores business information, supplier obligations, batches, FX quotes, payment instructions, provider submissions, and audit events.

PostgreSQL is a future deployment option for a more demanding production environment.

### Technology Summary

| Component | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| Backend | Python 3.12, FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| AI | Google Gemini Flash |
| Payment integration | PayPal REST API / Payouts API Sandbox |
| API communication | REST |
| Authentication for demo | API-key mechanism |
| Financial arithmetic | Python Decimal |

---

## 7. How PUFI Works — User Journey

```text
       SUPPLIER INVOICES
              |
              v
      VALIDATION ENGINE
              |
              v
     DUPLICATE DETECTION
              |
              v
      PAYMENT BATCHES
              |
              v
     FINANCIAL ANALYSIS
       /            \
      v              v
  FX + FEES       GEMINI AI
      \              /
       \            /
        v          v
      PROVIDER ROUTING
              |
              v
       HUMAN APPROVAL
              |
              v
      PAYMENT EXECUTION
              |
        +-----+------+
        |            |
        v            v
   PAYPAL SANDBOX  SIMULATED
                   PROVIDERS
        |            |
        +-----+------+
              |
              v
       STATUS TRACKING
              |
              v
       AUDIT & RECONCILIATION
```

### Step 1 — Import and Validate

The business operator imports supplier payment obligations.

PUFI validates the records and identifies invalid or duplicate entries.

### Step 2 — Create Payment Batches

Validated obligations are grouped into batches with unique identifiers.

### Step 3 — Analyse Financial Information

The financial engine calculates illustrative conversion costs, transaction fees, and provider eligibility.

### Step 4 — Generate AI Recommendations

Gemini Flash explains the available routes and identifies potential anomalies.

### Step 5 — Obtain Human Approval

The authorised operator reviews the financial information, confirms the batch total, and approves the proposed execution.

### Step 6 — Submit Payment Instructions

PUFI submits supported test payout requests through PayPal Sandbox when the required credentials and eligibility conditions are satisfied.

Other payment providers remain simulated.

### Step 7 — Track and Reconcile

PUFI records provider responses, updates payment statuses, and maintains an audit history.

A payment is considered completed only according to the relevant provider-reported status, not merely because an API request was submitted.

---

## 8. Financial Correctness and Security

Financial reliability is a central design consideration.

The prototype incorporates the following safeguards:

1. **Decimal Arithmetic:** Financial calculations use Python Decimal rather than binary floating-point arithmetic.
2. **Currency Identification:** Every financial amount has an explicit currency code.
3. **Deterministic Eligibility:** Provider eligibility is checked independently of AI recommendations.
4. **Idempotency:** Stable identifiers and submission guards help prevent duplicate payout requests.
5. **Human Approval:** AI cannot independently approve or execute payments.
6. **Webhook Verification:** The webhook implementation uses PayPal's signature-verification API.
7. **Audit Events:** Important workflow transitions are recorded.
8. **Sandbox Isolation:** The prototype uses the PayPal Sandbox environment, not production payment endpoints.

### Current Security Limitations

The current implementation is a hackathon prototype.

- Demo authentication uses an API key rather than enterprise-grade identity management.
- SQLite is intended for local demonstration, not high-concurrency production workloads.
- Local development does not establish production HTTPS security.
- External webhook delivery has not yet been independently verified.
- Production security audits, operational monitoring, and disaster recovery are outside the current implementation.

---

## 9. Testing and Verification

The project includes automated backend tests covering financial calculations, validation, routing, payment execution controls, and other backend behaviour.

The project submission reports **114 passing backend tests**. This figure should be confirmed against the current repository test run before final judging, as the README contains an earlier figure of 107 tests.

### Recommended verification commands

```powershell
cd backend

# Activate the virtual environment
.venv\Scripts\activate

# Run backend tests
python -m pytest tests/ -v
```

### Demonstration Scenarios

| Scenario | Expected behaviour |
|---|---|
| Valid supplier obligations | Successful validation |
| Duplicate invoice | Duplicate flagged |
| Invalid amount | Record rejected |
| Unsupported currency | Validation or provider eligibility failure |
| Multiple currencies | Illustrative FX calculations |
| Different routing strategies | Appropriate eligible route recommended |
| Gemini unavailable | Deterministic fallback |
| Unauthorised approval | Request rejected |
| Duplicate submission | Additional payout prevented by safeguards |
| Provider rejection | Failure recorded |
| Partial batch success | Individual item statuses maintained |
| Invalid webhook signature | Event rejected |

All test data used in the demonstration is synthetic.

---

## 10. Demo and Setup Instructions

**Repository:** https://github.com/ayuvan/pufi

### Prerequisites

- Python 3.11 or later.
- Node.js 18 or later.
- Git.
- pnpm.
- PayPal Sandbox developer credentials (optional).
- Gemini API credentials (optional, for AI advisory).

### 1. Clone the repository

```bash
git clone https://github.com/ayuvan/pufi.git
cd pufi
```

### 2. Configure the backend

```powershell
cd backend

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

Configure the required environment variables using the supplied `.env.example` template.

PayPal credentials must be Sandbox credentials only.

### 3. Seed synthetic data

```powershell
python seed.py
python demo_seed.py
```

Use the batch ID printed by the demo seed script.

### 4. Start the backend

```powershell
uvicorn main:app --reload
```

Backend:

`http://localhost:8000`

API documentation:

`http://localhost:8000/docs`

### 5. Start the frontend

Open a second terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

Frontend:

`http://localhost:5173`

### 6. Demonstrate PUFI

1. Open the dashboard.
2. Navigate to the supplier obligations.
3. Open or create a payment batch.
4. Run financial analysis.
5. Review provider eligibility and routing recommendations.
6. Examine Gemini's advisory.
7. Complete human approval.
8. Submit through PayPal Sandbox if configured, or demonstrate the clearly labelled simulated mode.
9. Refresh payment statuses.
10. Inspect the Global Audit Trail.

---

## 11. Hackathon Integration and Value Proposition

### PayPal Integration

PUFI uses the PayPal Payouts API in Sandbox to demonstrate an external payment-provider integration.

The integration includes:

- OAuth 2.0 authentication.
- Sandbox payout submission.
- Stable batch and item identifiers.
- Item-level status tracking.
- Webhook signature-verification implementation.

PayPal Payouts support and availability depend on account configuration, supported currencies, countries, recipient eligibility, and product restrictions.

The prototype does not claim successful settlement in unsupported scenarios.

### AI Integration

Google Gemini Flash provides advisory-only intelligence.

It makes financial information easier to understand by explaining provider comparisons, identifying anomalies, and describing trade-offs.

Deterministic backend controls remain authoritative.

### Business Value

PUFI demonstrates how enterprises could improve their payment operations through:

- Centralised supplier payment management.
- Reduced manual payment-processing effort.
- Better visibility into estimated transaction expenses.
- More structured provider selection.
- Improved duplicate-payment controls.
- Human-accountable payment execution.
- Centralised payment records and auditability.

The prototype demonstrates these capabilities using synthetic data, simulated financial scenarios, and PayPal Sandbox.

It does not claim measured production cost savings or real-world settlement improvements.

---

## 12. Future Development

The current implementation establishes a foundation for further development.

Potential future improvements include:

1. **Live FX Integration:** Connect supported exchange-rate data sources to obtain current currency quotes.
2. **Banking Connectivity:** Integrate eligible banking and payment-provider APIs.
3. **Cross-Border Settlement:** Explore supported USD-to-INR payment and settlement pathways.
4. **Advanced Reconciliation:** Match provider records against external financial statements.
5. **Scalable Persistence:** Introduce PostgreSQL and appropriate asynchronous processing.
6. **Enterprise Identity Management:** Implement OAuth2/JWT, role-based access control, and stronger approval policies.
7. **Payroll Coordination:** Explore structured employee payment workflows through supported providers.
8. **Social-Commerce Payments:** Explore integration with social-commerce platforms and PayPal checkout capabilities.

These are proposed extensions, not features delivered by the current hackathon prototype.

---

## 13. Conclusion

PUFI demonstrates an approach to simplifying enterprise payment operations through payment orchestration, deterministic financial analysis, AI-assisted decision support, human authorisation, and external payment-provider integration.

Rather than attempting to replace existing banks or payment providers, PUFI focuses on coordinating their capabilities through a unified operational layer.

Its central design principle is simple:

**Make enterprise payments more organised, cost-aware, explainable, and accountable — while keeping financial authority under deterministic controls and human supervision.**

PUFI is a working hackathon proof of concept that establishes the foundation for exploring more advanced enterprise payment coordination systems.

---

## 14. Official Technical References

- [PayPal Developer Platform](https://developer.paypal.com/)
- [PayPal REST API Getting Started](https://developer.paypal.com/api/rest/)
- [PayPal REST API Authentication](https://developer.paypal.com/api/rest/authentication/)
- [PayPal Payouts API](https://developer.paypal.com/docs/payouts/standard/)
- [PayPal Payouts API Reference](https://developer.paypal.com/docs/api/payments.payouts-batch/v1/)
- [PayPal Webhooks](https://developer.paypal.com/api/rest/webhooks/)
- [Google Gemini API Documentation](https://ai.google.dev/gemini-api/docs)

**Project Repository:** https://github.com/ayuvan/pufi