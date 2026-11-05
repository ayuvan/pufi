# PUFI — Local Development Guide

> Updated after Milestone 1 (Day 1). Commands verified on Windows / Python 3.12 / Node 24.

## Prerequisites

| Tool | Required version | Install |
|---|---|---|
| Python | 3.11+ | python.org |
| Node.js | 18+ (tested on 24) | nodejs.org |
| Git | any | git-scm.com |

---

## Backend (FastAPI)

```powershell
# 1. Enter backend directory
cd backend

# 2. Create virtual environment (first time only)
python -m venv .venv

# 3. Install dependencies (first time, or after requirements.txt changes)
.venv\Scripts\pip install -r requirements.txt

# 4. Copy and configure environment
Copy-Item .env.example .env
# Edit .env — fill in PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, AI_API_KEY when ready.
# DATABASE_URL defaults to SQLite — no changes needed for local dev.

# 5. Seed synthetic data (run once; re-run resets to known state)
.venv\Scripts\python seed.py

# 6. Start the development server
.venv\Scripts\uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Verify backend

```
GET http://localhost:8000/api/v1/health
→ { "status": "ok", "version": "0.1.0", ... }

GET http://localhost:8000/api/v1/obligations
→ { "items": [...], "total": 13, ... }

API docs (auto-generated):
http://localhost:8000/docs
```

> **Note:** The project path contains `&` and spaces. All backend commands use
> `.venv\Scripts\python` / `.venv\Scripts\uvicorn` directly — this avoids shell
> splitting issues. Do **not** activate the venv with `.\venv\Scripts\Activate.ps1`
> if it causes issues; using the full binary path works reliably.

---

## Frontend (React + Vite)

```powershell
# From the PUFI root directory
cd frontend

# Install dependencies (first time only — requires network)
npm install

# Start development server (proxies /api → localhost:8000)
npm run dev
# → http://localhost:5173
```

> **Note on path with `&`:** If `npm run dev` fails with a path error, run
> Vite directly:
> ```powershell
> node .\node_modules\vite\bin\vite.js
> ```

### Verify frontend

Open `http://localhost:5173` in a browser. You should see:
- Green "Backend connected" banner
- Obligation table with 13 synthetic records
- Status badges, supplier names, amounts, currencies

---

## Run both together (two terminals)

**Terminal 1 — Backend:**
```powershell
cd "d:\YS & DP\YS\Projects\PUFI\backend"
.venv\Scripts\uvicorn main:app --reload
```

**Terminal 2 — Frontend:**
```powershell
cd "d:\YS & DP\YS\Projects\PUFI\frontend"
npm run dev
```

---

## Reset demo data

```powershell
cd backend
.venv\Scripts\python seed.py
```

This clears and re-inserts all synthetic obligations. Safe to run repeatedly.

---

## Database

| Setting | Value |
|---|---|
| Dev engine | SQLite (auto-created as `backend/pufi_dev.db`) |
| Location | `backend/pufi_dev.db` (git-ignored) |
| Switch to PostgreSQL | Change `DATABASE_URL` in `.env` |

The `.db` file is git-ignored. Never commit it.

---

## Environment variables (`.env`)

| Variable | Purpose | Required for |
|---|---|---|
| `DATABASE_URL` | DB connection string | Always (defaults to SQLite) |
| `DB_ECHO` | Log SQL queries (`true`/`false`) | Dev debugging |
| `PAYPAL_ENVIRONMENT` | `sandbox` | Day 4 |
| `PAYPAL_CLIENT_ID` | PayPal app client ID | Day 4 |
| `PAYPAL_CLIENT_SECRET` | PayPal app secret (server-side only) | Day 4 |
| `AI_PROVIDER` | `gemini` | Day 3 |
| `AI_API_KEY` | Gemini API key | Day 3 |
| `AI_MODEL` | Model name (default: `gemini-2.5-flash`) | Day 3 |
| `CORS_ORIGINS` | Allowed frontend origins | Optional |

---

## Known issues and workarounds

| Issue | Workaround |
|---|---|
| `npm run build` fails (path with `&`) | Use `npm run build:fast` or `node .\node_modules\vite\bin\vite.js build` |
| `uvicorn` command not found | Use `.venv\Scripts\uvicorn` with the full relative path |
| SQLite WAL mode warning on first run | Harmless; created automatically |
| `seed.py` emoji display on Windows | ASCII fallback `[OK]` used — display is cosmetic only |

---

## Project structure (Day 1)

```
PUFI/
├── backend/
│   ├── .env.example        ← copy to .env
│   ├── requirements.txt    ← pinned Python deps
│   ├── main.py             ← FastAPI app
│   ├── seed.py             ← synthetic data loader
│   ├── models/
│   │   ├── db.py           ← engine, session, Base
│   │   └── entities.py     ← Business, Supplier, Obligation ORM
│   ├── routers/
│   │   ├── health.py       ← GET /api/v1/health
│   │   └── obligations.py  ← GET /api/v1/obligations
│   ├── schemas/
│   │   └── obligation.py   ← Pydantic response models
│   └── alembic/            ← migration framework (Day 2+)
├── frontend/
│   ├── src/
│   │   ├── api/client.ts   ← typed fetch wrapper
│   │   ├── pages/ObligationsPage.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── vite.config.ts      ← proxies /api → :8000
├── data/
│   └── synthetic_data/
│       └── obligations_seed.json
└── docs/
    ├── local_dev.md        ← this file
    ├── financial_architecture.md
    ├── api_specification.md
    ├── security_model.md
    └── proposal_requirements.md
```
