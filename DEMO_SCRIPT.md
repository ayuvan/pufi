# PUFI — 2-Minute Demo Script

> **Total time target: ~120 seconds**  
> Words in [brackets] = on-screen action to perform while speaking.  
> Each section is timed — keep a steady pace.

---

## ⏱ 0:00 — Opening Hook (~10 seconds)

> *[Open browser to `http://localhost:5173` — Overview / Dashboard page visible]*

**"Every enterprise wastes time and money managing supplier payments across disconnected systems — wrong providers, hidden FX markups, and duplicate disbursements.  
PUFI solves that — a single intelligent coordination layer for all your payment operations."**

---

## ⏱ 0:10 — Overview Dashboard (~15 seconds)

> *[Point to the KPI metric cards at the top — total obligations, batch count, amounts]*

**"This is the PUFI dashboard. At a glance, finance teams see all outstanding supplier payment obligations, batch statuses, and total amounts — with real-time updates from the backend."**

---

## ⏱ 0:25 — Payment Obligations (~15 seconds)

> *[Click "Payment Obligations" in the left sidebar]*

**"Here are the validated supplier invoices. PUFI automatically catches duplicate invoice references and invalid amounts before they ever reach a payment provider — preventing costly errors upstream."**

---

## ⏱ 0:40 — Batch Creation & Management (~15 seconds)

> *[Click "Batches" in the sidebar — show the batch list]*

**"Validated obligations are grouped into payment batches. Each batch gets a unique reference, and the system locks it during active processing — so no two operations can collide on the same batch simultaneously."**

---

## ⏱ 0:55 — Financial Analysis & AI Advisory (~25 seconds)

> *[Click into a batch → navigate to Analysis page]*

**"This is where PUFI's core intelligence lives. The deterministic engine evaluates every eligible payment provider — comparing exact FX spreads, fixed rail fees, and estimated settlement times using precise decimal arithmetic — no floating-point rounding errors.**

**Google Gemini AI then reads that analysis and explains the trade-offs in plain English — flagging anomalies, outliers, and the optimal route. But critically — the AI is advisory only. It cannot approve or execute any payment."**

---

## ⏱ 1:20 — Human Approval & PayPal Sandbox Execution (~20 seconds)

> *[Show the Approve button / execution console]*

**"Before any money moves, an authorised human controller must review and approve the batch. Only then does PUFI submit through the PayPal Sandbox Payouts API — with stable idempotency keys preventing duplicate payouts, even if the network drops mid-request."**

---

## ⏱ 1:40 — Global Audit Trail (~15 seconds)

> *[Click "Audit Trail" in the sidebar]*

**"Every single state change — approvals, submissions, provider responses, webhook events — is recorded in a cryptographic SHA-256 hash chain. Tamper any record and verification immediately flags the broken link.  
Complete, traceable accountability — from obligation to settlement."**

---

## ⏱ 1:55 — Closing (~5 seconds)

> *[Return to Overview dashboard]*

**"PUFI — making enterprise payments organised, cost-aware, and accountable. Thank you."**

---

## 📋 Quick Reference Card

| Timestamp | Screen | Key Point |
|:---:|:---|:---|
| 0:00 | Dashboard (Overview) | Problem statement + product intro |
| 0:10 | Overview metrics | Real-time KPIs |
| 0:25 | Obligations ledger | Deduplication + validation |
| 0:40 | Batches list | Batch locking + concurrency |
| 0:55 | Financial Analysis | Deterministic routing + Gemini AI advisory |
| 1:20 | Approval & Execution | Human control + PayPal Sandbox |
| 1:40 | Audit Trail | SHA-256 hash chain + tamper detection |
| 1:55 | Dashboard | Closing statement |

---

## 🎙️ Delivery Tips

- **Speak at 140–160 words per minute** for a confident, clear cadence.
- **Click first, then speak** — let the screen change settle before narrating it.
- **Don't rush the AI section** — it's the most unique differentiator.
- Emphasise: *"AI is advisory only"* and *"human approval is mandatory"*.
- If a section runs long, skip the Audit Trail detail and go straight to closing.
