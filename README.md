# Multi-Tenant Organization Manager (Django)

A secure, multi-tenant backend service that lets users create organizations, invite members with roles, manage items, and view audit logs with an AI chatbot. Built with **Django** (instead of FastAPI), Django REST Framework, JWT, PostgreSQL, and Docker.

---
## Sample Video

[Uploading Screencast from 2026-03-06 19-26-36.webm…]()


## For reviewers – run with Docker (no setup)

**Requirements:** Docker and Docker Compose installed.

```bash
git clone https://github.com/FatMAnsour/Multi-Tenant-Organization-Manager.git
cd Multi-Tenant-Organization-Manager
docker compose up --build
```

Wait until the backend is ready (migrations and server start). Then:

- **API base:** http://localhost:8000  
- **Register:** `POST http://localhost:8000/auth/register`  
- **Login:** `POST http://localhost:8000/auth/login`  
- **Full manual test flow:** see [MANUAL_TESTING.md](MANUAL_TESTING.md)

No `.env` or local Python/PostgreSQL needed; defaults are used. Optional: add a `.env` (see `.env.example`) to set a custom DB password or `GROQ_API_KEY` for the chatbot.

---

## Tech Stack

- **Python 3.11+**
- **Django** + **Django REST Framework**
- **PostgreSQL**
- **JWT** (djangorestframework-simplejwt)
- **RBAC** (role-based access: Admin / Member)
- **Pytest** + **pytest-django** + **testcontainers** (Postgres)

## What This App Does

- **Access**: Sign up and log in securely (JWT).
- **Setup**: Admins create organizations and invite members with roles.
- **Search**: Admins search users in an organization via PostgreSQL full-text search.
- **Data**: Members add items to an organization; members see only their items, admins see all.
- **Oversight**: Admins see all items and audit logs.
- **Insights**: Admins ask an AI chatbot questions about today’s activity (optional streaming).
- **Deployment**: One command: `docker compose up`.

---

## How to Run

### With Docker (recommended)

No local Python or Postgres needed. From the project root:

```bash
docker compose up --build
```

- Backend: **http://localhost:8000**
- API (ex register): **http://localhost:8000/auth/register**

Migrations run automatically. Default DB credentials (postgres/postgres) are used; no `.env` required. Optional: copy `.env.example` to `.env` to override or set `GROQ_API_KEY`.

### Local development (without Docker)

1. **Python 3.11+** and **PostgreSQL** installed.
2. Create a virtualenv and install deps:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. Create a Postgres database and set env (or use defaults):

   ```bash
   export POSTGRES_DB=org_manager
   export POSTGRES_USER=postgres
   export POSTGRES_PASSWORD=postgres
   export POSTGRES_HOST=localhost
   export POSTGRES_PORT=5432
   ```

4. Migrate and run:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

### Running tests

Tests use **pytest** and, by default, **testcontainers** to run a real Postgres container:

```bash
pip install -r requirements.txt
pytest
```

To run tests against an existing Postgres (ex in CI) and skip testcontainers:

```bash
USE_TESTCONTAINERS=0 pytest
```

(Ensure `POSTGRES_*` env vars point to your test DB and that the DB exists.)

---

## API Overview

All protected endpoints require:

```http
Authorization: Bearer <access_token>
```

| Method | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| POST | `/auth/register` | Public | Register (email, password, full_name) |
| POST | `/auth/login` | Public | Login → `{ "access_token", "token_type": "bearer" }` |
| POST | `/organization` | Authenticated | Create org; creator becomes Admin; audit log |
| POST | `/organization/{id}/user` | Admin | Invite user (email, role: admin/member) |
| GET | `/organizations/{id}/users` | Admin | List org users (paginated: limit, offset) |
| GET | `/organizations/{id}/users/search?q=...` | Admin | Full-text search org users (PostgreSQL) |
| POST | `/organizations/{id}/item` | Member/Admin | Create item (item_details, org_id in body) |
| GET | `/organizations/{id}/item` | Member/Admin | List items (member=own, admin=all); paginated |
| GET | `/organizations/{id}/audit-logs` | Admin | List audit entries |
| POST | `/organizations/{id}/audit-logs/ask` | Admin | Ask AI about today’s logs (question, stream) |

---

## Database Design

- **users** – Custom user (email, full_name, password hash). No username.
- **organizations** – name, created_at.
- **memberships** – user_id, organization_id, role (admin | member). Unique (user, organization).
- **items** – organization_id, created_by_id, details (JSON), created_at.
- **audit_logs** – organization_id, user_id (nullable), action, details (JSON), created_at.

Indexes:

- `memberships(organization_id, role)`
- `items(organization_id, created_by_id)`
- `audit_logs(organization_id, created_at)`
- GIN index on `users` for full-text search: `to_tsvector('english', email || ' ' || full_name)` (migration `0002_user_search_vector`).

Relations:

- User ↔ Organization: many-to-many via **Membership** with a **Role**.
- Item belongs to one Organization and one User (creator).
- AuditLog belongs to one Organization and optionally one User (actor).

---

## Architecture Decisions and Tradeoffs

1. **Django instead of FastAPI**  
   Request handling is synchronous. For this assignment’s scale, Django’s simplicity and ecosystem (ORM, admin, auth, migrations) were preferred. Async could be added later with ASGI and async views if needed.

2. **Django REST Framework**  
   Used for serializers, permissions, and pagination so the API matches the spec (JSON, status codes, auth) without reimplementing everything by hand.

3. **JWT via djangorestframework-simplejwt**  
   Access tokens include `sub` (user id) as required. No refresh flow in the spec; it can be added if needed.

4. **RBAC**  
   Implemented as custom permission classes (`IsOrgAdmin`, `IsOrgMember`) that resolve membership from the URL `organization id` and the authenticated user. No global “super admin” beyond Django’s `is_staff`; org-scoped roles only.

5. **Full-text search**  
   PostgreSQL `to_tsvector` / `tsquery` via Django’s `SearchVector` and `SearchQuery` on `email` and `full_name`, restricted to users in the organization. A GIN index on the user table (migration) keeps search fast.

6. **Audit logging**  
   One `AuditLog` model; actions (ex organization_created, user_invited, item_created, items_listed) are written in the view layer. No async queue; good enough for the assignment.

7. **Chatbot (LLM)**  
   Optional. If `GROQ_API_KEY` is set, the “ask” endpoint uses Groq to answer questions about today’s audit logs; otherwise it returns a short placeholder. Streaming returns NDJSON chunks.

8. **Tests**  
   Pytest + pytest-django; testcontainers spawns Postgres so tests run against a real DB. Tests cover auth, RBAC (admin vs member), and organization isolation (member sees only own items; admin sees all; no cross-org access).

9. **Docker**  
   Single `docker compose up`: Postgres + Django app. No external dependencies; migrations run on startup. Suitable for local and demo; production would add env-based secrets and possibly a reverse proxy.

---

## Spec compliance (assignment requirements, using Django)

| Requirement | Implementation |
|-------------|----------------|
| **1) Domain model** | `User`, `Organization`, `Membership`, `Role` (Admin/Member), `Item`, `AuditLog` in `core/models.py`. User can belong to multiple orgs; each Membership has a role. |
| **2) Auth** | `POST /auth/register`: email, password, full_name → hash password (Django), create user. `POST /auth/login`: validate credentials → JWT with `sub` (user_id), response `{ "access_token", "token_type": "bearer" }`. |
| **3) RBAC** | JWT validated (DRF + SimpleJWT); user_id from token; custom permissions `IsOrgAdmin` / `IsOrgMember`. All protected endpoints require `Authorization: Bearer <token>`. |
| **4) Organization API** | `POST /organization`: body `org_name` → create org, Admin membership for creator, AuditLog; response `{ "org_id" }`. `POST /organization/{id}/user`: body email, role → Admin only, create membership, log. `GET /organizations/{id}/users?limit=20&offset=0`: Admin only, paginated. |
| **5) Full-text search** | `GET /organizations/{id}/users/search?q=keyword`: Admin only; PostgreSQL `SearchVector`/`SearchQuery` (tsvector/tsquery); GIN index in migration `0002_user_search_vector`. |
| **6) Items** | `POST /organizations/{id}/item`: body `item_details`, `org_id` → Member/Admin, create item + AuditLog; response `{ "item_id" }`. `GET /organizations/{id}/item?limit=20&offset=0`: member = own items, admin = all; AuditLog entry on list. |
| **7) Audit logs** | `GET /organizations/{id}/audit-logs`: Admin only; returns org audit entries. |
| **8) Chatbot** | `POST /organizations/{id}/audit-logs/ask`: body `question`, `stream`; Admin only; today’s logs → Groq (GROQ_API_KEY); stream if `stream=true`. |
| **9) Docker** | `docker-compose.yml`: backend + PostgreSQL; `docker compose up`; no external deps. |
| **10) Testing** | pytest, pytest-django, testcontainers (Postgres). Tests: Authentication, RBAC enforcement, Organization isolation. |

**Stack substitution (Django instead of FastAPI):** Python 3.11+, Django + DRF (instead of FastAPI), Django ORM (instead of SQLAlchemy 2.0 async), PostgreSQL, JWT, RBAC, Pytest. Async: assignment was written for FastAPI async; this implementation is synchronous Django (documented tradeoff).

---

## Design Tradeoffs

- **Sync vs async**: Django is sync by default. For high concurrency you’d consider async views and an async DB driver; for this scope sync is simpler.
- **Pagination**: List endpoints use limit/offset; cursor-based pagination could be added for very large lists.
- **Invite flow**: “Invite” here means “add existing user to org by email”. A full invite flow would add email invitations and signup links.
- **LLM**: Groq (`GROQ_API_KEY` in .env; default model `llama-3.1-8b-instant`).

---
