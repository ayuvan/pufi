# PUFI — Official Hackathon Submission Document

---

## 1. Project Name
**PUFI** (Enterprise Payment Coordination & Intelligent Routing Infrastructure)

---

## 2. Short Description
PUFI is an intelligent, cross-provider enterprise payment coordination web platform. It ingests bulk supplier obligations, performs mathematical validation and deduplication, deterministically evaluates fee models and FX spreads across payment rails, provides explainable AI decision-support via Google Gemini Flash, and enforces strict human-in-the-loop authorization before executing Sandbox disbursements through PayPal.

---

## 3. The Problem We Tried to Solve
Middle-market and multinational enterprises face significant financial and operational friction when managing outbound supplier disbursements:

1. **Fragmented & Opaque Multi-Rail Routing:** Businesses juggle traditional wire transfers, ACH rails, and digital provider networks (such as PayPal). Finance teams struggle to calculate real-time foreign exchange (FX) spread drag, tiered transaction fees, and expected settlement times.
2. **Duplicate Dispatches & Accounting Risk:** Disjointed spreadsheets and legacy accounting imports frequently trigger double payments or format mismatches resulting in financial leakage and tedious manual reconciliation.
3. **The AI Autonomy Dilemma in FinTech:** While LLMs are powerful at qualitative reasoning and data synthesis, allowing AI models autonomous transactional authority over financial payouts creates catastrophic hallucination and regulatory risks.
4. **Lack of Verifiable Auditability:** Audit trails across disparate banking portals are scattered, making post-disbursement verification and compliance reporting slow and error-prone.

---

## 4. The Best Solution We Have Come Up With
PUFI creates a **unified payment orchestration layer** that bridges enterprise obligations with payment execution rails while adhering to strict financial safeguards:

- **Mathematical Correctness First:** All financial values and exchange rates are handled with arbitrary-precision `Decimal` representations (never IEEE 754 binary floating-point) with explicit ISO currency pairs.
- **Deterministic-First Eligibility Engine:** Hard business logic (recipient types, transaction bounds, provider eligibility rules, currency support) is evaluated deterministically. AI cannot override mathematical or regulatory constraints.
- **Explainable AI Decision-Support:** Gemini Flash synthesizes the batch characteristics, explains fee vs. speed tradeoffs in plain language, and highlights anomalies for human review.
- **Mandatory Human-in-the-Loop Gate:** Payments can never be executed autonomously. An authorized human approver must confirm the snapshot total and select the provider route.
- **Live PayPal Sandbox Integration:** Complete integration with PayPal OAuth 2.0 and the PayPal Payouts API featuring stable idempotency keys and item-level settlement tracking.
- **Transparent Failure Handling:** Rather than disguising provider errors, PUFI transparently logs and displays real provider eligibility responses (e.g., PayPal's India sender country restrictions) and updates the durable audit ledger.

---

## 5. How the Solution Was Created (App / Web / AI Architecture)

The system is architected into three tightly integrated tiers:

### A. Frontend Web Application (React + TypeScript + Vite)
- **Tech Stack:** React 18, TypeScript, TanStack React Query, modern CSS.
- **Key Modules:**
  - **Obligations Ledger:** Interactive table showing invoices, validation flags, and Decimal amounts.
  - **Batch Creator:** Multi-select grouping of pre-validated obligations into disbursement batches.
  - **Financial Analysis Hub:** Visual breakdown of costs across providers with explicit `SIMULATED` vs `SANDBOX` labeling.
  - **Approval & Execution Console:** Dual-control approval modal and PayPal Sandbox execution trigger with real-time status polling.
  - **Global Audit Trail:** Chronological timeline of all system transitions and verified webhooks.

### B. Backend API & Core Financial Engines (FastAPI + Python 3.12)
- **Validation Engine:** Multi-rule validation verifying invoice syntax, positive amounts, future/current due dates, and SHA-256 payload deduplication.
- **FX & Fee Engine:** Models currency-specific rounding (e.g., zero-decimal JPY vs 2-decimal USD), basis-point fee calculation, and FX spread degradation.
- **Provider Capability Registry:** Registry modeling provider parameters (e.g., PayPal Sandbox USD email payouts, Simulated Wire, Simulated ACH).
- **Execution Coordinator:** Generates deterministic `sender_batch_id` and item-level idempotency keys (`PUFI-{batch_id}-{obligation_id}`) persisted prior to network calls.
- **PayPal Webhook Receiver:** Validates incoming event signatures via PayPal's `verify-webhook-signature` REST endpoint with SHA-256 event deduplication.

### C. Artificial Intelligence Service (Google Gemini Flash)
- **SDK:** Official `@google/genai` Python SDK.
- **Model:** `gemini-flash-latest` (fast, structured JSON schema response).
- **Graceful Fallback:** If the AI service times out or credentials are absent, the system degrades seamlessly to deterministic financial rankings with zero user interruption.

---

## 6. How the System Works (User Journey)

```
[ Supplier Invoices ] ──► [ Validation & Deduplication ] ──► [ Payment Batch Creation ]
                                                                       │
                                                                       ▼
[ Real Provider Call ] ◄── [ Human Approval Gate ] ◄── [ Deterministic FX + Gemini AI ]
         │                                                             │
         ▼                                                             ▼
[ PayPal Sandbox / Mock ] ───────────────────────────────► [ Durable Audit Ledger ]
```

1. **Ingest & Validate:** The finance operator imports raw obligations. The backend validates format rules and verifies no duplicate invoice references exist.
2. **Form a Batch:** Validated obligations are batched together under a unique batch reference (e.g., `DEMO-BATCH-DAY4`).
3. **Analyze & Advise:** The financial intelligence engine evaluates eligible providers. Gemini Flash inspects the sanitized context and outputs plain-language explanations of costs and trade-offs.
4. **Human Review & Approval:** The operator reviews the AI advisory, confirms the exact batch total, and formally records approval.
5. **Execute Payout:** The operator triggers execution. PUFI dispatches the request to PayPal's Sandbox API using OAuth 2.0 client credentials and safe idempotency keys.
6. **Audit & Trace:** Every transition—from validation to provider HTTP responses—is permanently recorded in the audit trail.

---

## 7. Demo Link & Setup Instructions

* **Public GitHub Repository:** [https://github.com/ayuvan/pufi](https://github.com/ayuvan/pufi)
* **Open Source License:** [MIT License](https://github.com/ayuvan/pufi/blob/main/LICENSE) visible in repository root.

### How Judges Can Run the Project Locally:

#### Prerequisites:
- Python 3.11+
- Node.js 18+ & npm / pnpm
- Git

#### 1. Clone the repository:
```bash
git clone https://github.com/ayuvan/pufi.git
cd pufi
```

#### 2. Backend Setup:
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Seed the database with ready-to-use demo data:
python demo_seed.py

# Start the backend server:
uvicorn main:app --reload
```
*(Backend runs at `http://localhost:8000` with interactive Swagger docs at `http://localhost:8000/docs`)*

#### 3. Frontend Setup:
```bash
# Open a new terminal:
cd frontend
npm install
npm run dev
```
*(Frontend runs at `http://localhost:5173`)*

#### 4. Run the Automated Test Suite (114 Tests):
```bash
cd backend
pytest -v
# Output: 114 passed in < 5 seconds
```

---

## 8. Demo Video Outline (Under 3 Minutes)

* **0:00 – 0:30 (Problem & Overview):** Introduce PUFI as an enterprise payment coordination engine solving multi-rail opaque fees and duplicate payouts.
* **0:30 – 1:00 (Obligations & Batch Creation):** Show the Obligations tab, demonstrate Decimal precision, and create a disbursement batch.
* **1:00 – 1:45 (Analysis & Gemini AI Decision-Support):** Open the Financial Analysis page. Show deterministic fee calculation across PayPal vs. Simulated rails, followed by the Gemini Flash plain-English recommendation.
* **1:45 – 2:20 (Human Approval & PayPal Sandbox Execution):** Perform human approval. Trigger the live PayPal Sandbox API call; show the genuine OAuth token exchange and transparent provider feedback.
* **2:20 – 2:50 (Audit Trail & Verification):** Switch to the Audit Trail tab to show immutable transition records with correlation IDs.
* **2:50 – 3:00 (Conclusion):** Emphasize financial correctness, zero hallucinations in payment authority, and open-source compliance.
