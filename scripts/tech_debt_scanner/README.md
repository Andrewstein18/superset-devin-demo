# Tech Debt Scanner Pipeline

Automated tech debt scanner that uses Devin AI agents to scan, document, and fix code quality issues in the Apache Superset codebase.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Orchestrator                       │
│              (orchestrator.py / Docker)               │
│                                                       │
│  ┌──────────┐  ┌──────────┐                          │
│  │ Scanner  │  │ Scanner  │  Stage 1: Scan & Document│
│  │ Agent 1  │  │ Agent 2  │  (1 per directory)       │
│  │ utils/   │  │ explore/ │                          │
│  └────┬─────┘  └────┬─────┘                          │
│       │              │                                │
│       ▼              ▼                                │
│  GitHub Issues + Documentation PRs                    │
│       │              │                                │
│       ▼              ▼                                │
│  ┌──────────┐  ┌──────────┐                          │
│  │ Fixer    │  │ Fixer    │  Stage 2: Fix Issues     │
│  │ Agent 1  │  │ Agent 2  │  (1 per issue)           │
│  └──────────┘  └──────────┘                          │
│                                                       │
│  Output: Fix PRs + Metrics Report + Dashboard JSON    │
└─────────────────────────────────────────────────────┘
```

## How It Works

### Stage 1: Scanner Agents
- One Devin agent per target directory
- Each agent **reads and understands** the actual source code (not just grep)
- Finds security issues, type safety problems, dead code, and stale TODOs
- Creates `MODULE_README.md` documentation for each file analyzed
- Adds inline comments and docstrings to undocumented functions
- Files a GitHub issue for each finding
- Opens a documentation PR with all `.md` files and comments

### Stage 2: Fixer Agents
- One Devin agent per GitHub issue from Stage 1
- Reads the issue, understands the context, implements the fix
- Runs `pre-commit` before committing
- Opens a PR that references the issue

### Metrics & Reporting
After each run, the pipeline outputs:
- `reports/dashboard-data-<timestamp>.json` — structured metrics for the dashboard
- `reports/report-<timestamp>.md` — human-readable markdown summary
- Metrics tracked: agents spawned, issues filed, PRs created, .md files, comments, docstrings

## Quick Start

### Docker (recommended)

```bash
# Set your Devin API token
export DEVIN_API_TOKEN=your_token_here

# Run the full pipeline
cd scripts/tech_debt_scanner
docker compose up --build

# Or scan only (no fixer agents)
docker compose run tech-debt-scanner --dry-run
```

### Python (direct)

```bash
# Set your Devin API token
export DEVIN_API_TOKEN=your_token_here

# Run from repo root
python -m scripts.tech_debt_scanner.orchestrator

# Scan only
python -m scripts.tech_debt_scanner.orchestrator --dry-run
```

### GitHub Actions (scheduled)

The pipeline runs automatically every Sunday at 8am UTC via `.github/workflows/tech-debt-scanner.yml`. You can also trigger it manually from the Actions tab.

**Required secret:** Add `DEVIN_API_TOKEN` to your repo's GitHub Actions secrets.

## Configuration

Edit `SCAN_DIRS` in `orchestrator.py` to change which directories are scanned:

```python
SCAN_DIRS: list[str] = [
    "superset/utils/",
    "superset-frontend/src/explore/",
]
```

## Dashboard

Open `dashboard.html` in a browser to view the analytics dashboard. It shows:
- Agent status cards (which Devins at which stage)
- Metrics: issues filed, PRs created, .md files, comments, docstrings
- Pipeline logs and artifacts

## Requirements

- Python 3.10+ (no external dependencies — stdlib only)
- A valid `DEVIN_API_TOKEN`
- Docker (optional, for containerized runs)
