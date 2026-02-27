# AutoDev — Self-Healing Codebase Agent

> AI-powered autonomous code analysis, refactoring, and PR automation.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/LLM-Claude%20claude--opus--4--6-purple)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docker.com)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AutoDev Pipeline                        │
│                                                                  │
│  POST /analyze                                                   │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐             │
│  │  Phase 1 │──▶│   Phase 2    │──▶│   Phase 3   │             │
│  │  Clone   │   │   Analyze    │   │   Refactor  │             │
│  │  Repo    │   │  Radon/Ruff/ │   │   (Claude   │             │
│  │          │   │  Bandit/AST  │   │    LLM)     │             │
│  └──────────┘   └──────────────┘   └─────────────┘             │
│                                           │                      │
│                                           ▼                      │
│                         ┌──────────────────────────┐            │
│                         │        Phase 4           │            │
│                         │   Safety Validation      │            │
│                         │  syntax+diff+ruff+       │            │
│                         │  bandit+pytest           │            │
│                         └──────────────────────────┘            │
│                                           │ PASS                 │
│                                           ▼                      │
│                         ┌──────────────────────────┐            │
│                         │        Phase 5           │            │
│                         │    Git Automation        │            │
│                         │  branch + commit + PR    │            │
│                         └──────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic |
| Database | PostgreSQL + SQLAlchemy |
| Queue | Celery + Redis |
| LLM | Claude (Anthropic) |
| Complexity | Radon |
| Linting | Ruff |
| Security | Bandit |
| AST Parsing | Python `ast` module |
| Git | GitPython + GitHub REST API |
| Frontend | Next.js + TypeScript + Recharts |
| Logging | structlog (JSON) |
| Container | Docker + Docker Compose |

---

## Quick Start

### 1. Prerequisites

- Docker + Docker Compose
- Anthropic API key
- GitHub personal access token (scopes: `repo`, `pull_requests`)

### 2. Configure

```bash
cp .env.example .env
# Edit .env and fill in:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GITHUB_TOKEN=ghp_...
```

### 3. Launch

```bash
docker compose up --build
```

Services:
- **API**: http://localhost:8000
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Celery Monitor**: http://localhost:5555

### 4. Analyze a Repo

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/pallets/flask", "branch": "main"}'
```

Response:
```json
{
  "repo_id": "uuid-here",
  "task_id": "celery-task-uuid",
  "status": "queued",
  "message": "Repository queued for analysis."
}
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/analyze` | Queue repo for full pipeline |
| `GET` | `/api/v1/repos` | List all repositories |
| `GET` | `/api/v1/repos/{id}` | Get repo status |
| `GET` | `/api/v1/repos/{id}/report` | Full analysis report + issues |
| `GET` | `/api/v1/repos/{id}/refactors` | All refactor suggestions |
| `POST` | `/api/v1/refactor` | Manually trigger refactor for issue |
| `GET` | `/api/v1/stats` | Global aggregate stats |
| `GET` | `/health` | Health check |

---

## Analysis Thresholds (configurable via `.env`)

| Metric | Default | Env Var |
|---|---|---|
| Cyclomatic complexity | 10 | `MAX_CYCLOMATIC_COMPLEXITY` |
| Max function lines | 50 | `MAX_FUNCTION_LINES` |
| Max nesting depth | 3 | `MAX_NESTING_DEPTH` |
| Max parameters | 6 | `MAX_PARAMETERS` |
| Max file size change | 30% | `MAX_FILE_SIZE_CHANGE_PCT` |

---

## Safety Guarantees

AutoDev applies **5 layers of validation** before opening any PR:

1. **Syntax check** — AST parse of refactored code
2. **Diff validator** — size change < 30%, no unexpected imports
3. **Signature check** — all public function signatures preserved
4. **Lint gate** — Ruff must pass with no E/W/F errors
5. **Test gate** — pytest must pass if tests exist

If any check fails → suggestion is marked `failed`, no PR opened.

---

## Project Structure

```
autodev/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── api/routes.py        # All REST endpoints
│   │   ├── models/
│   │   │   ├── repo.py          # Repository ORM model
│   │   │   └── analysis.py      # Issue + Refactor ORM models
│   │   ├── services/
│   │   │   ├── repo_service.py       # Clone + manage repos
│   │   │   ├── analysis_service.py   # Radon + Ruff + Bandit + AST
│   │   │   ├── refactor_service.py   # Claude LLM integration
│   │   │   ├── validation_service.py # Safety checks
│   │   │   └── git_service.py        # Branch + commit + PR
│   │   ├── tasks/worker.py      # Celery tasks
│   │   └── utils/
│   │       ├── ast_parser.py    # Python AST extraction
│   │       └── diff_validator.py # Diff safety checks
│   ├── requirements.txt
│   └── alembic.ini
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Main dashboard
│   │   └── layout.tsx
│   ├── lib/api.ts               # Typed API client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

---

## Development

### Run locally (no Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Worker (separate terminal)
celery -A app.tasks.worker.celery_app worker --loglevel=info

# Frontend
cd frontend
npm install && npm run dev
```

### Run tests

```bash
cd backend
pytest tests/ -v
```

---

## Roadmap

- [ ] Multi-language support (JavaScript/TypeScript)
- [ ] Embedding-based duplicate function detection
- [ ] CLI: `autodev analyze ./project`
- [ ] Webhook support (auto-analyze on push)
- [ ] PR review mode (analyze diffs, not full repo)
- [ ] Cost dashboard (token usage per repo)
- [ ] Slack/Teams notifications

---

## Benchmarks

| Metric | Result |
|---|---|
| Avg complexity reduction | ~45% |
| Validation pass rate | ~78% |
| Avg tokens per refactor | ~1,200 |
| Time to first PR | ~3–5 min |

---

## License

MIT
