# PUFI Enterprise 2.0 — Payment Coordination Infrastructure

> **PayPal Developer Platform + Google Gemini AI Hackathon Submission**  
> *PayPal-Integrated Payment Coordination Infrastructure*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI: 0.110+](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React: 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript: 5.7](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Vite: 8.3](https://img.shields.io/badge/Vite-8.3-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![PayPal: Sandbox](https://img.shields.io/badge/PayPal-Sandbox%20Payouts%20API-003087?logo=paypal&logoColor=white)](https://developer.paypal.com)
[![Gemini: 3.8 Flash](https://img.shields.io/badge/Gemini%20AI-3.8%20Flash-8E75C2?logo=google&logoColor=white)](https://ai.google.dev)
[![Tests: 114 Passed](https://img.shields.io/badge/Tests-114%20Passed-16A779?logo=pytest&logoColor=white)](https://pytest.org)

---

## Executive Overview

**PUFI Enterprise 2.0** is an enterprise payment coordination and financial orchestration platform designed to automate and de-risk supplier disbursement lifecycles. It ingests bulk obligations across multiple currencies, performs deterministic invoice deduplication and validation, models multi-provider cost structures and FX spreads, consults Google Gemini AI for explainable decision support, enforces dual-control maker-checker governance, and dispatches authenticated batch payouts through the **PayPal Sandbox Payouts API v1**.

PUFI is **not a bank, custodian, wallet, or money transmitter**. It does not hold customer funds. It functions strictly as a coordination, decision-support, and audit-logging layer between enterprise ERP systems and payment execution rails.

* **GitHub Repository:** [https://github.com/ayuvan/pufi](https://github.com/ayuvan/pufi)
* **Frontend Design Language:** Premium Fintech UI inspired by Mercury, Stripe, Ramp, and CashPod
* **Primary Target:** PayPal Developer Platform + Google Gemini Hackathon (Judge-Ready)

---

## Key Highlights & Architectural Capabilities

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        PUFI ENTERPRISE 2.0 PLATFORM                        │
├────────────────────┬────────────────────┬──────────────────────────────────┤
│ 1. INGESTION       │ 2. AI ROUTING      │ 3. GOVERNANCE & EXECUTION        │
│ • Bulk JSON Upload │ • Deterministic    │ • Dual-Control Maker-Checker     │
│ • Invoice Dedup    │   Eligibility Rules│ • PayPal Sandbox Outbound API    │
│ • Decimal Precision│ • Gemini 3.8 Flash │ • Country Eligibility Diagnostic │
│ • Currency Checks  │ • FX Spread Models │ • SHA-256 Chained Audit Trail    │
└────────────────────┴────────────────────┴──────────────────────────────────┘
```

1. **Enterprise Frontend Redesign (PUFI 2.0)**:
   - Deep navy collapsible navigation sidebar (`#101C32`) with active ACME corporate profile.
   - Top status bar with live API health heartbeat, pulsating PayPal Sandbox status indicator, and instant Light/Dark mode switcher.
   - High-density financial tables with tabular numerals (`num-tabular`), AG Grid view toggle, and slide-over metadata drawers.
   - Bespoke zero-dependency SVG charts: Area Trend Charts, Status Donut Charts, and Comparative Route Bar Charts.

2. **Deterministic Route Analysis + Explainable AI (Google Gemini 3.8 Flash)**:
   - Evaluates provider fee schedules, settlement windows, and currency suitability across PayPal and simulated alternative rails (`LOWEST_COST`, `FASTEST`, `BALANCED`).
   - Gemini AI decision support generates structured advisory summaries with cited factors.
   - **Strict Guardrail**: AI is strictly advisory and cannot approve or execute payouts. If the model is offline or times out, the system automatically degrades to deterministic routing.

3. **Dual-Control Maker-Checker Approval Gate**:
   - Segregation of duties prevents unilateral payment execution.
   - Requires explicit sign-off on confirmed total liability and selected currency before payouts can be dispatched.

4. **PayPal Sandbox Payouts Integration**:
   - OAuth2 server-side token management (credentials never exposed to client).
   - Idempotent batch submission using deterministic `sender_batch_id` and item-level tracking.
   - Automated handling and diagnostic display for PayPal Sandbox geographic restrictions (e.g., account country payout eligibility).
   - Cryptographically verified PayPal webhook receiver (`POST /api/v1/webhooks/paypal`).

5. **Tamper-Evident Audit Trail**:
   - Immutable audit logging on all entity transitions with actor attribution and correlation IDs.
   - Phase 5 cryptographic hash chaining (`prev_hash` & `event_hash`) ensuring log immutability.

---

## 9-Module Application Map

| # | Workspace Module | Route | Key Capabilities |
|---|------------------|-------|------------------|
| 1 | **Overview Dashboard** | `#overview` | KPI metric cards, volume trends, donut status distribution, recent audit feed, quick-action navigation. |
| 2 | **Payment Obligations** | `#obligations` | Multi-field search, status & currency chips, Fintech Table vs. AG Grid toggle, slide-over invoice drawer. |
| 3 | **Import & Ingestion** | `#import` | Drag-and-drop JSON upload, JSON payload editor, pre-loaded sample datasets, Zapier webhook guide, diagnostic row-level validation. |
| 4 | **Payment Batches** | `#batches` | Batch cards, commitment sums, slide-over batch creator from `VALIDATED` obligations with live totals. |
| 5 | **Batch Detail & Execution** | `#batch/{id}` | 5-step Bryntum lifecycle stepper, multi-provider route preview, maker-checker authorization, signature PayPal Gold execution button, country eligibility diagnostic banner, itemized instructions table. |
| 6 | **Route Analysis** | `#analysis` | Active batch selector, policy objectives (`Lowest Cost`, `Fastest`, `Balanced`), TanStack Query cache, Gemini advisory card, SVG cost & speed bar chart, detailed provider breakdown. |
| 7 | **Compliance & Audit Trail**| `#audit` | Full event log, quick batch filter, actor attribution, correlation ID copy, expandable JSON payload diff viewer. |
| 8 | **Ecosystem & Sponsors** | `#ecosystem` | Direct links to 10 sponsor tools, architectural roles, Postman collection (`postman_collection.json`), and Render blueprint (`render.yaml`). |
| 9 | **Settings & Preferences**| `#settings` | Light/Dark theme switcher, layout controls, tabular numerals toggle, Sandbox disclosures, security constraints. |

---

## Repository Layout

```text
PUFI/
├── README.md                           # Master Project Documentation & Quick Start
├── API_COMPATIBILITY.md                # 12-Endpoint Backend Contract Specification
├── FRONTEND_AUDIT.md                   # Comprehensive Pre-Redesign Audit & Gap Analysis
├── FRONTEND_REDESIGN_REPORT.md         # Architecture, Design Tokens & Migration Report
├── AGENTS.md                           # AI Agent Governance & Financial Constraints
├── ARCHITECTURE.md                     # Component Boundaries & Security Model
├── IMPLEMENTATION_PLAN.md              # Milestone Delivery & Verification Matrix
├── postman_collection.json             # Automated API Testing Collection
├── render.yaml                         # Production Deployment Blueprint
├── run_backend.bat                     # Windows One-Click Backend Launcher
├── run_backend.ps1                     # PowerShell Backend Launcher
│
├── frontend/                           # React 19 + TypeScript + Vite Application
│   ├── src/
│   │   ├── api/client.ts               # Authoritative Typed API Client (with demo key header)
│   │   ├── components/
│   │   │   ├── common/                 # StatusBadge, CurrencyBadge, MetricCard, Drawer, FinancialChart
│   │   │   └── layout/                 # MainLayout, AppSidebar, Topbar, PageHeader
│   │   ├── pages/                      # 9 Complete Production Pages
│   │   ├── styles/theme.css            # Mercury/Stripe Design System Tokens & Themes
│   │   ├── App.tsx                     # Top-Level Router & PayPal Provider Shell
│   │   └── main.tsx                    # Entry Point
│   ├── package.json
│   └── vite.config.ts                  # Vite Proxy (/api/v1 -> localhost:8000)
│
└── backend/                            # Python 3.11+ FastAPI Service
    ├── main.py                         # Application Factory, CORS, Correlation Middleware
    ├── routers/                        # Obligations, Batches, Analysis, Execution, Webhooks
    ├── models/                         # SQLAlchemy Entities (Decimal precision, AuditEvent hash chain)
    ├── schemas/                        # Pydantic v2 Request/Response Envelopes
    ├── services/                       # RoutingEngine, AIAdvisor, ExecutionCoordinator, ApprovalService
    ├── tests/                          # 114 Automated Pytest Scenarios (Money, Concurrency, Adapters)
    ├── requirements.txt
    └── pufi_dev.db                     # Local SQLite Database File
```

---

## Quick Start (Judge-Ready in 2 Minutes)

### Prerequisites
* **Python 3.11+** installed
* **Node.js 18+** with `npm` installed
* **Git**

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/ayuvan/pufi.git
cd pufi
```

---

### Step 2: Start the Backend (FastAPI)
Using Windows one-click script:
```cmd
run_backend.bat
```
*Or manually via terminal:*
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Seed base synthetic obligations:
python seed.py

# Start the API server:
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
> **Backend runs at:** `http://127.0.0.1:8000`  
> **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`

---

### Step 3: Start the Frontend (Vite)
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
> **Frontend runs at:** `http://localhost:5173`

---

### Step 4: Explore the End-to-End Demo Workflow
1. Open **`http://localhost:5173`** in your browser.
2. **Overview**: View live KPI cards, commitment volume trends, and recent transaction feeds.
3. **Obligations**: Filter supplier invoices by currency (USD/EUR) or status, toggle between table views, and inspect invoice drawer metadata.
4. **Payment Batches**: Click **Create Batch** to group validated obligations into a payment batch, or select the pre-seeded batch **`DEC-2026-SUPPLIERS`**.
5. **Batch Detail**:
   - Inspect the **5-Step Bryntum Lifecycle Stepper**.
   - Review multi-provider route pricing across PayPal and simulated rails.
   - Complete the **Maker-Checker Authorization** with approver credentials.
   - Click the signature **Execute PayPal Sandbox Payout** button to witness live sandbox execution and geographic eligibility handling.
6. **Multi-Provider Route Analysis**: Switch between **Lowest Cost**, **Fastest Settlement**, and **Balanced Policy** to view real-time Gemini AI advisory notes and comparative SVG bar charts.
7. **Compliance & Audit**: Inspect immutable state transitions, correlation IDs, and cryptographic hash verification.

---

## Automated Test Suite (114 Passing Tests)

PUFI includes comprehensive test coverage for financial rounding, route eligibility, idempotency, duplicate prevention, and adapter error mapping:

```bash
cd backend
.venv\Scripts\python -m pytest tests/ -v
```

```text
====================================== test session starts ======================================
collected 114 items

tests/test_analysis.py ..................................................... [ 46%]
tests/test_approval.py ..................................................... [ 92%]
tests/test_execution.py ........                                             [100%]

====================================== 114 passed in 4.82s ======================================
```

---

## PayPal Sandbox Configuration (Optional)

The application includes working sandbox credentials and automatically falls back to clearly labelled `SIMULATED` mode if credentials are omitted.

To configure your own PayPal Sandbox account:
1. Create `backend/.env` (referencing `backend/.env.example`):
   ```env
   PAYPAL_MODE=sandbox
   PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id
   PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret
   PAYPAL_SANDBOX_RECIPIENT_EMAIL=your-sandbox-buyer@personal.paypal.com
   AI_API_KEY=your_gemini_api_key
   ```
2. **Security & Sandbox Notice**:
   - `PAYPAL_MODE` is strictly locked to `sandbox`. Production execution is barred.
   - PayPal Sandbox outbound payouts are subject to PayPal account country regulations (e.g. Indian business accounts support inward settlement only). The UI cleanly surfaces diagnostic eligibility explanations.

---

## Financial Correctness & Integrity Principles

* **Monetary Precision**: All monetary values are represented as Python `Decimal` and database `NUMERIC`. IEEE 754 floating-point arithmetic is forbidden for financial balances.
* **ISO Currency Tagging**: Every amount carries an explicit 3-letter ISO code.
* **Idempotency**: Payout requests generate stable internal idempotency keys ensuring retries never produce duplicate payments.
* **Honest Attribution**: All simulated FX rates, fees, and providers are visually flagged with badges (`SIMULATED`, `SANDBOX`).
* **AI Guardrails**: Google Gemini recommendations are advisory only and cannot override deterministic validation, approve batches, or trigger disbursements.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
