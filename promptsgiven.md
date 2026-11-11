# Prompt Engineering & Build Log (`promptsgiven.md`)

This document captures the actual sequence of prompts, design decisions, and iterative refinements I used to architect, build, test, harden, style, and deploy **Modern AI-Powered Hospital Management** (a multi-tenant, permission-aware Hospital Operations AI Agent).

Rather than generating everything in a single blind shot, the project was built iteratively—starting from strict backend security & database architecture, moving through LLM provider migration, real-world debugging, 12-scenario validation, stretch-goal engineering, UI redesigns, cloud deployment, and adversarial edge-case testing.

---

## Core Idea Behind the Prompts

Hospital teams deal with sensitive inventory, INR billing, and staff permissions across independent hospitals. Giving an LLM direct SQL access is unsafe. My core idea while prompting was:

1. **Separate NLU from Authorization:** The LLM (or deterministic fallback parser) should *only* translate natural language into a fixed, schema-validated `OPERATION_REGISTRY` intent—never decide permissions and never write raw SQL.
2. **Enforce Security at Both App & DB Layers:** Every request must resolve a trusted server-side `CurrentUserContext` (`hospital_id`, `roles`, `effective_permissions`) backed by PostgreSQL Row-Level Security (`app.current_hospital_id`).
3. **Make Every Write Safe & Reversible:** No database mutation executes directly from chat. Every write generates a dry-run diff preview with an HMAC-bound confirmation token, requires exact row counts for `>50` row writes, and supports snapshot-based **Undo** and **Approval Routing**.

---

## Phase 1: System Architecture & Full-Stack Core

### 1. Initial Architecture & Security Specification
> **Why I framed it this way:** I wanted a real multi-tenant system (not a mock prototype) with strict database schemas, Alembic migrations, deterministic seed data, RBAC constraints, and security tests from day one.

```text
Act as a senior full-stack engineer, Python backend architect, AI/LLM engineer,
PostgreSQL database architect, application security engineer, and UI/UX designer.

Build a complete, production-minded, multi-tenant Hospital Operations AI Agent.
This is a real working application, not a static frontend prototype.

The application should allow hospital employees to perform authorized database
operations using natural language while ensuring strict role-based access control,
tenant isolation, business-rule enforcement, safe database writes, and
comprehensive audit logging.

Stack:
- Frontend: React + TypeScript + Tailwind CSS
- Backend: Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2
- Database: PostgreSQL / Supabase with Row Level Security (RLS)

Do not just explain the implementation. Create the actual project files, code,
database schema, API endpoints, tests, configuration, and documentation.
```

### 2. Locking the Frontend Framework Choice
> **Why:** Ensuring the UI stayed modular and strictly in React + TypeScript before scaffolding pages.

```text
Use React for the frontend workspace with role-aware views for Assistant Chat,
Inventory, Billing, Users & Access, and Audit Logs.
```

**Outcome:** Created the multi-tenant schema (`hospitals`, `users`, `roles`, `permissions`, `role_permissions`, `user_permission_overrides`, `inventory_items`, `bills`, `audit_logs`, `operation_confirmations`), RLS migration `002_rls_policies.py`, `PermissionEngine`, `ConfirmationService`, deterministic seed (`2 hospitals`, `13 users`, `1,240 inventory items`, `1,040 bills`), and React/Vite app.

---

## Phase 2: Migrating LLM Extraction to Google Gemini

### 3. Switching from OpenAI to Gemini Structured Outputs
> **Why:** I wanted to power intent extraction with Google Gemini (`google-genai` SDK) while keeping `.env.example` clean and supporting offline deterministic fallback when no API key is supplied.

```text
Write the LLM intent extraction code with the Gemini API (google-genai), not OpenAI.
Also update .env.example to use GEMINI_API_KEY and GEMINI_MODEL instead of OpenAI,
and confirm what is needed vs optional for local runs.
```

**Outcome:** Implemented `IntentExtractorService` using Gemini structured JSON outputs (`gemini-2.5-flash`) with a schema-validated deterministic local fallback so evaluators can test 100% offline.

---

## Phase 3: Database Wiring, Auth Debugging & Test Stabilization

### 4. Connecting PostgreSQL / Supabase & Configuring Local Test DB
> **Why:** Connecting Alembic and SQLAlchemy cleanly to Supabase Session Pooler vs local PostgreSQL, and configuring `TEST_DATABASE_URL` cleanly.

```text
Help me configure DATABASE_URL for Supabase PostgreSQL Session Pooler and explain
what should go in TEST_DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, and
SUPABASE_JWT_SECRET.
```

### 5. Fixing Login & Intent Extraction Unit Tests
> **Why:** While running the app locally for the first time, I hit authentication and port issues (`Invalid email or password`, port `8000` conflict, and a test failure in phase 5 intent extraction).

```text
I am getting "Invalid email or password" when trying to sign in locally, and
backend/tests/unit/test_phase5_intent_extraction.py has a failing case.
Fix the demo auth flow and the intent extraction test, and verify the backend and
frontend run cleanly together.
```

**Outcome:** Fixed local demo password/session resolution when `ALLOW_DEMO_AUTH=true`, resolved `test_phase5_intent_extraction.py`, and got the FastAPI + React local loop running smoothly.

---

## Phase 4: Validating All 12 Core Acceptance Scenarios

### 6. End-to-End Scenario Verification Prompt
> **Why:** Before adding any stretch features, I wanted to systematically verify every core security boundary—row caps, RBAC denials, IST `"last month"` date math, cross-tenant blocking, self-demotion protection, and prompt injection defense.

```text
Validate all 12 core acceptance scenarios end-to-end across roles:
1. Pharmacist: "Bulk update the entire inventory with quantity 5" -> Refuse (>500 row cap) and suggest narrowing; same query as Admin -> preview, confirm, execute, log.
2. Front desk: "Set all inventory quantities to 5" -> Refuse immediately before touching inventory.
3. Billing manager: "Give 20% discount on all bills from last month" -> Enforce 10% cap.
4. Admin: "Give 20% discount on all bills from last month" -> Resolve exact Asia/Kolkata dates, preview ₹ impact, require >50 row exact count, execute, log.
5. Admin: "Remove inventory edit access from Ravi" -> Resolve Ravi in same hospital, preview override without affecting other pharmacists, confirm, execute.
6. Admin: "Give Ravi access" -> Ask clarifying question; zero DB writes.
7. Admin self-demotion & Billing Manager self-promotion -> Refuse & audit.
8. Cross-tenant Hospital A -> Hospital B isolation & prompt-injection resistance.
```

**Outcome:** Verified all 12 scenarios in `backend/tests/scenarios/test_12_acceptance_scenarios.py` and visually tested them in the live chat UI.

---

## Phase 5: Implementing All 5 Stretch Goals

### 7. Adding Depth Features After Core Scenarios Passed
> **Why:** Once the 12 core scenarios were solid, I added the 5 optional stretch goals so the system supports real operational recovery, multi-step human approvals, bilingual hospital staff queries, quantitative security benchmarking, and fast evaluator demoing.

```text
Now that all 12 core scenarios pass, implement these 5 stretch goals cleanly:
1. Undo: "Undo my last change" restores the before-snapshot, only if no one has touched those rows since.
2. Approval routing: A billing manager asking for a 20% discount creates a pending request that an Admin can review and approve/reject in chat.
3. Telugu / Hinglish input: "Last month bills ki 20% discount ivvu" works identically to the English version.
4. Eval harness: A script running 50+ labelled queries reporting intent accuracy, false-allow rate, and false-deny rate.
5. Role switcher UI: A clean chat interface with an instant role switcher for demoing across roles and hospitals.
```

**Outcome:** Added `operations.undo` (with snapshot/row-staleness checks), `approvals.read` / `approvals.resolve` + migration `004_approval_requests`, Telugu/Hinglish intent extraction, a 130-case evaluation suite in `evaluation/evaluate.py`, and a 1-click **Demo Role Switcher**.

---

## Phase 6: UI/UX Evolution (Swiss Design -> Bento Grid UI)

### 8. First UI Pass: Swiss Typographic Style
> **Why:** Replacing default boilerplate cards with disciplined typography, clear hierarchy, and tabular INR/quantity alignment.

```text
Apply the whole website with a clean Swiss Design UI so every permission, audit status,
and dry-run financial table is crisp and readable.
```

### 9. Second UI Pass: Bento Grid UI & Hero Landing Page
> **Why:** Making the first impression immediately clear for evaluators and operators with a strong hero headline and modular Bento Grid layout across both the landing page and operations workspace.

```text
Put a strong "Modern AI-Powered Hospital Management" big heading on the landing page,
apply a Bento Grid UI across the entire project (landing page, dashboard KPIs, copilot
chat console, role switcher, permissions matrix, and ledger tables), and push to GitHub.
```

**Outcome:** Redesigned `LoginPage.tsx`, `DashboardLayout.tsx`, `DashboardPage.tsx`, `ChatPanel.tsx`, `OperationPreviewCard.tsx`, and all ledger views into a unified Bento Grid design system (`Plus Jakarta Sans` + `IBM Plex Mono`).

---

## Phase 7: Cloud Deployment & Edge-Case Hardening

### 10. Free Cloud Deployment (GitHub + Render + Vercel + Supabase)
> **Why:** Making the app live and testable in a browser without requiring an evaluator to install dependencies first.

```text
Help me push the project cleanly to GitHub (excluding secrets) and deploy it freely:
Supabase PostgreSQL + FastAPI backend on Render (Blueprint / render.yaml) + React Vite
frontend on Vercel, with CORS properly connected between Vercel and Render.
```

### 11. Catching & Fixing a Live Adversarial Edge Case as Admin
> **Why:** While testing the live deployed Admin UI, I tried `"delete my role as admin"` and noticed two real bugs: it returned `Unsupported` instead of `Denied` (`cannot_self_demote`), and long constraint JSON wrapped tightly next to the `Allow` badge.

```text
Validate this case as Admin login: when I type "delete my role as admin", it says
Unsupported instead of enforcing the self-demotion guard and returning Denied.
Also clean up the constraint JSON text overlap in the Effective Role Permissions card.
```

**Outcome:** Updated `IntentExtractorService`, `prompts/system_prompt.txt`, `prompts/examples/few_shot_examples.json`, and `test_scenario_08` so `"delete my role as admin"` routes to `users.manage_access`, triggers `cannot_self_demote`, logs the denied attempt, and returns **`Denied`**—and wrapped long constraint badges cleanly in `DashboardPage.tsx`.

---

## Phase 8: Evaluator Documentation & Reproducibility

### 12. Validating Setup, `.env.example`, `README.md`, and `promptsgiven.md`
> **Why:** Ensuring any evaluator cloning the repository understands every environment variable, can run Docker or local setup in minutes, and can trace the exact prompts used to build the application.

```text
Validate the codebase, tests, and evaluation script, then rewrite README.md and
.env.example clearly so an evaluator understands every variable and how to run the
project locally. Finally, document the connected prompts used to build the project
in promptsgiven.md.
```

---

## Final Verified Checks After All Prompts

- **Pytest Suite (`backend/.venv/bin/pytest -q`):** `41 passed` (unit, integration, security/RLS boundaries, 12 acceptance scenarios, and stretch goals)
- **Evaluation Harness (`evaluation/evaluate.py`):** `130/130 (100.0%)` Intent, Parameter, Clarification, and Authorization accuracy (`0/41` False-Allow, `0/89` False-Deny)
- **Frontend Production Build (`cd frontend && npm run build`):** `tsc && vite build` passed cleanly
