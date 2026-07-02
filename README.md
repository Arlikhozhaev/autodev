# AutoDev — Self-Healing Codebase Agent

> **Paste a GitHub URL. Get static analysis, LLM refactors, and a pull request — only if 5 safety gates pass.**

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://autodev-one.vercel.app)
[![CI](https://github.com/Arlikhozhaev/autodev/actions/workflows/ci.yml/badge.svg)](https://github.com/Arlikhozhaev/autodev/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/LLM-Claude%20claude--opus--4--6-purple)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docker.com)

**[Live Dashboard](https://autodev-one.vercel.app)** · **[API Docs](https://autodev-production.up.railway.app/docs)** · **[GitHub](https://github.com/Arlikhozhaev/autodev)**

---

## The Problem → The Solution

| Challenge | AutoDev Response |
|-----------|------------------|
| Manual code review doesn't scale | **4-tool static analysis** on every clone (Radon, Ruff, Bandit, AST) |
| LLM refactors can break production | **5-layer validation pipeline** before any PR is opened |
| Analysis takes minutes, not milliseconds | **Async Celery workers** — API stays responsive under load |
| Unsafe AI output must never ship | **generate → validate → retry** loop (**3 attempts/issue**) with structured error feedback |

**In one sentence:** AutoDev automates the full improve-and-ship loop for Python repos — clone, analyze, refactor with Claude, validate, and open a GitHub PR — with safety gates that block bad output instead of hoping for the best.

---

## Impact at a Glance

| Metric | Value |
|--------|-------|
| Static analysis tools | **4** (Radon, Ruff, Bandit, AST) |
| Pre-PR safety gates | **5** (syntax, diff, signatures, lint, security, pytest) |
| LLM retry attempts per issue | **3** with validation feedback |
| Issues processed per pipeline run | **Up to 10** (highest-severity first) |
| Automated tests | **35** (pytest + API + auth + tasks) |
| CI checks on every merge | **Ruff · pytest · ESLint · production build** |
| Deployed services | **6** (API, worker, Postgres, Redis, Flower, dashboard) |
| Pipeline time limit | **10 min** per repo (configurable) |

> Validated end-to-end on a live deployment: issues detected → refactor generated → validation passed → **PR opened** on a sandbox repository.

---

## Architecture

```
POST /analyze
     │
     ▼
┌──────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────┐   ┌─────────────┐
│ Phase 1  │──▶│   Phase 2    │──▶│   Phase 3   │──▶│   Phase 4    │──▶│   Phase 5   │
│  Clone   │   │   Analyze    │   │  Refactor   │   │  Validate    │   │  Git + PR   │
│  (git)   │   │ Radon/Ruff/  │   │  (Claude)   │   │ 5 safety     │   │  branch +   │
│          │   │ Bandit/AST   │   │ 3× retry    │   │ gates        │   │  commit     │
└──────────┘   └──────────────┘   └─────────────┘   └──────────────┘   └─────────────┘
       │                │                  │                 │                  │
       └────────────────┴──────────────────┴─────────────────┴──────────────────┘
                                    Celery + Redis (async)
                                    PostgreSQL (persist)
```

**Why async matters:** Cloning, multi-tool analysis, and LLM refactors run for minutes. Celery workers handle the pipeline; FastAPI returns immediately with a `task_id` for live status polling.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI · Pydantic v2 · slowapi (rate limiting) |
| Database | PostgreSQL · SQLAlchemy 2.0 · Alembic migrations |
| Queue | Celery · Redis |
| LLM | Claude (Anthropic) — surgical refactor prompts per issue type |
| Analysis | Radon · Ruff · Bandit · Python `ast` |
| Git / PRs | GitPython · GitHub REST API |
| Frontend | Next.js 14 · TypeScript · Recharts |
| Observability | structlog (JSON) · Flower (Celery monitor) |
| Infra | Docker Compose · Railway (API/worker) · Vercel (dashboard) |
| CI | GitHub Actions |

---

## Safety-First by Design

AutoDev treats LLM output as **untrusted until proven**. No PR is opened unless every gate passes:

1. **AST syntax** — refactored code must parse
2. **Diff validator** — signature preservation, import allowlist, size bounds
3. **Ruff lint** — no E/F errors on the refactored snippet
4. **Bandit security** — no new high-severity findings
5. **pytest** — full test suite passes (when tests exist)

Failed refactors are stored with `validation_notes` for review in the dashboard diff viewer — **blocked changes, not silent failures**.

---

## Dashboard

The Next.js operations UI includes:

- **One-click analyze** — paste any public GitHub URL
- **Pipeline stepper** — clone → analyze → refactor → validate → PR
- **Issue browser** — severity, type, file path, metric values
- **Side-by-side diff viewer** — original vs. refactored code
- **Deep links** — `/repos/{id}?tab=issues|refactors|charts`
- **Task polling** — live Celery status via `GET /tasks/{id}`

API keys stay server-side via a Next.js `/api/v1` proxy — never exposed to the browser.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- [Anthropic API key](https://console.anthropic.com/)
- [GitHub token](https://github.com/settings/tokens) (`repo`, `pull_requests` scopes)

### Run locally

```bash
git clone https://github.com/Arlikhozhaev/autodev.git
cd autodev
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, GITHUB_TOKEN, API_KEY (optional)

docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Celery Monitor | http://localhost:5555 |

### Analyze a repo

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"repo_url": "https://github.com/Arlikhozhaev/autodev-sandbox", "branch": "main"}'
```

```json
{
  "repo_id": "uuid",
  "task_id": "celery-task-uuid",
  "status": "queued",
  "message": "Repository queued for analysis."
}
```

Poll progress: `GET /api/v1/tasks/{task_id}`

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/analyze` | Queue full pipeline (rate-limited: 10/min) |
| `GET` | `/api/v1/repos` | List repositories |
| `GET` | `/api/v1/repos/{id}` | Repo status |
| `GET` | `/api/v1/repos/{id}/report` | Analysis report + issues |
| `GET` | `/api/v1/repos/{id}/refactors` | Refactor suggestions + diffs |
| `POST` | `/api/v1/refactor` | Trigger single-issue refactor |
| `GET` | `/api/v1/tasks/{task_id}` | Celery task status |
| `GET` | `/api/v1/stats` | Aggregate dashboard stats |
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Postgres + Redis readiness |

**Auth:** Set `API_KEY` in `.env` — all `/api/v1/*` routes require `X-API-Key` or `Authorization: Bearer <key>`.

---

## Configuration

| Threshold | Default | Env Var |
|-----------|---------|---------|
| Max cyclomatic complexity | 10 | `MAX_CYCLOMATIC_COMPLEXITY` |
| Max function lines | 50 | `MAX_FUNCTION_LINES` |
| Max nesting depth | 3 | `MAX_NESTING_DEPTH` |
| Max parameters | 6 | `MAX_PARAMETERS` |
| Max file size change | 30% | `MAX_FILE_SIZE_CHANGE_PCT` |

---

## Engineering Quality

| Area | Implementation |
|------|----------------|
| **Testing** | 35 pytest cases — DiffValidator, AST parser, API routes, auth, task status |
| **Linting** | Ruff (backend) · ESLint (frontend) |
| **CI** | GitHub Actions on every push/PR to `main` |
| **Migrations** | Alembic with legacy-schema bootstrap for zero-downtime deploys |
| **Security** | API-key auth · rate limiting · server-side key proxy · structured error envelopes |
| **Deploy** | Railway (API + Celery worker + Postgres + Redis) · Vercel (Next.js dashboard) |

```bash
# Run tests locally
cd backend && pytest tests/ -v
cd frontend && npm run lint && npm run build
```

---

## Project Structure

```
autodev/
├── backend/
│   ├── app/
│   │   ├── api/           # Routes, schemas, auth, rate limiting
│   │   ├── models/        # SQLAlchemy ORM (repos, issues, refactors)
│   │   ├── services/      # Analysis, refactor, validation, git
│   │   ├── tasks/         # Celery pipeline worker
│   │   └── utils/         # AST parser, diff validator
│   ├── alembic/           # Database migrations
│   └── tests/             # 35 automated tests
├── frontend/
│   ├── app/               # Next.js App Router + API proxy
│   └── components/        # Dashboard, diff viewer, charts
├── docker-compose.yml     # 6-service local stack
├── .github/workflows/     # CI pipeline
└── Dockerfile
```

---

## Roadmap

- [x] CI pipeline (Ruff, pytest, ESLint, production build)
- [x] 35-test backend suite + API auth + rate limiting
- [x] Alembic migrations + Docker auto-migrate
- [x] Celery task status API + dashboard polling
- [x] Live deployment (Railway + Vercel)
- [ ] SSE / WebSocket live pipeline updates
- [ ] Demo mode (pre-seeded results, no API keys required)
- [ ] Multi-language support (TypeScript / JavaScript)
- [ ] CLI: `autodev analyze ./project`
- [ ] Cost dashboard (token usage per repo)

---

## Benchmarks

> Illustrative results from internal runs on Python repositories — not guaranteed for every codebase.

| Metric | Typical Result |
|--------|----------------|
| Avg complexity reduction (validated refactors) | ~45% |
| Validation pass rate | ~78% |
| Avg tokens per refactor | ~1,200 |
| Time to first PR | 3–5 min |

Mature codebases (e.g. Flask) may see **0 validated PRs** — that is correct behavior. Safety gates are designed to block unsafe snippet refactors, not maximize PR count.

---

## License

MIT

---

<p align="center">
  <strong>Built by <a href="https://github.com/Arlikhozhaev">Arlikhozhaev</a></strong> ·
  <a href="https://autodev-one.vercel.app">Live Demo</a> ·
  <a href="https://github.com/Arlikhozhaev/autodev/issues">Issues</a>
</p>
