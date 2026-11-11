# Permission-Aware Hospital Operations AI Agent

A production-minded, multi-tenant Hospital Operations AI Agent built with **FastAPI**, **React + TypeScript + Tailwind CSS**, **SQLAlchemy 2.x + Alembic**, **Supabase PostgreSQL + Row Level Security (RLS)**, and **Google Gemini API (`google-genai`) Structured JSON Outputs**.

Hospital staff can perform authorized read and write operations using natural language while the backend strictly enforces authentication, hospital-level tenant isolation, role-based access control (RBAC) with per-user overrides, dry-run previews, >50-row exact confirmation gates, `Decimal` financial precision, and append-only audit logging.

---

## Quick Start (Docker Compose)

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
   *(Optionally set `GEMINI_API_KEY` in `.env`. Without a Gemini API key, the backend uses a deterministic schema-validated local parser for offline/demo usage.)*

2. Start PostgreSQL, Backend (auto-migrates + seeds), and Frontend:
   ```bash
   docker compose up --build
   ```

3. Open the application:
   - **Frontend UI:** http://localhost:5173
   - **Backend API Docs (Swagger):** http://localhost:8000/docs

---

## Local Development Setup

### Backend (Python 3.12+)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run Alembic migrations (against DATABASE_URL in .env)
alembic upgrade head

# One-command deterministic seed (2 hospitals, 13 users, 5 roles, 620 inventory items & 520 bills per hospital)
python -m seed.seed_data

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

### Frontend (React + Vite + TypeScript)
```bash
cd frontend
npm install
npm run dev
```

---

## Demo Credentials (Local Demo Mode)

When `ALLOW_DEMO_AUTH=true` (local dev/evaluation), sign in with any seeded email using password `HospitalDemo!2026` (never use demo mode in production; configure Supabase Auth credentials in `.env` instead):

| Hospital | Role | Name | Email |
|---|---|---|---|
| Metro General Hospital | Admin | Dr. Ananya Sharma | `admin.a@metrogeneral.org` |
| Metro General Hospital | Billing Manager | Vikram Nair | `billing.a@metrogeneral.org` |
| Metro General Hospital | Pharmacist | Priya Patel | `pharmacist.a@metrogeneral.org` |
| Metro General Hospital | Pharmacist | Ravi Kumar | `ravi.a@metrogeneral.org` |
| Metro General Hospital | Front Desk | Neha Verma | `frontdesk.a@metrogeneral.org` |
| Metro General Hospital | Doctor | Dr. Kabir Rao | `doctor.a@metrogeneral.org` |
| City Care Medical Center | Admin | Dr. Meera Iyer | `admin.b@citycare.org` |
| City Care Medical Center | Pharmacist | Ravi Menon | `ravi.b@citycare.org` |

---

## Running Tests & 110-Case Evaluation

### Automated Pytest Suite (Unit, Integration, Security, & All 12 Acceptance Scenarios)
```bash
cd backend
.venv/bin/pytest
```
To run against a live PostgreSQL instance (including RLS policy verification):
```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hospital_ai_test .venv/bin/pytest
```

### 110-Case Natural-Language & Security Evaluation
```bash
cd backend
.venv/bin/python ../evaluation/evaluate.py
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/session` | Authenticate via Supabase Auth or demo auth and resolve profile |
| `GET` | `/api/auth/me` | Return current trusted server-side `CurrentUserContext` |
| `GET` | `/api/permissions/me` | Return current user's effective permissions and constraints |
| `POST` | `/api/agent/chat` | Parse natural language -> read result, clarification, denial, or write preview |
| `POST` | `/api/operations/preview` | Generate dry-run preview + bound confirmation token |
| `POST` | `/api/operations/confirm` | Confirm and atomically execute previewed write (>50 rows requires exact count) |
| `POST` | `/api/operations/cancel` | Cancel pending preview and audit cancellation |
| `GET` | `/api/inventory` | Read hospital-scoped inventory (`inventory.read`) |
| `GET` | `/api/bills` | Read hospital-scoped or own-only bills (`bills.read`) |
| `GET` | `/api/users` | Read hospital users & effective permissions (`users.read`) |
| `GET` | `/api/audit-logs` | Read immutable hospital audit history (Admin only) |

---

## Extending to New Business Cases

1. Add or reuse an approved operation key in `backend/app/registry/operation_registry.py`.
2. Add a strict Pydantic v2 parameter schema (`extra="forbid"`) in `backend/app/schemas/operations.py`.
3. Implement preview + atomic execution logic in `backend/app/services/operations/`.
4. Map required permission & constraints in `backend/app/services/permissions/engine.py` and seed data.
5. Add paraphrases to `prompts/examples/few_shot_examples.json` and `evaluation/dataset/cases.json`.
6. Add positive, negative, and cross-tenant tests, then run `evaluation/evaluate.py` and `pytest`.

---

## Documentation

- [System Architecture & Assumptions](docs/architecture.md)
- [Security & Tenant Isolation](docs/security.md)
- [One-Page Design Note (Risks & Mitigations)](docs/design_note.md)
- [5–7 Minute Demo Script](docs/demo_script.md)

