<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# `superset/tasks/` — Async Task Infrastructure

This module contains all Celery task definitions and the Global Task Framework
(GTF) that powers Superset's asynchronous operations: cache warming, thumbnail
generation, report scheduling, async query execution, and generic task
orchestration.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Celery Beat Scheduler                     │
│  (triggers periodic tasks via celery_app.py entrypoint)     │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
      ┌────────▼────────┐          ┌──────────▼──────────┐
      │   scheduler.py  │          │     cache.py        │
      │  (reports/alerts)│          │  (cache warm-up)    │
      └────────┬────────┘          └──────────┬──────────┘
               │                              │
      ┌────────▼────────────────────────────  │
      │              Celery Workers           │
      │  ┌──────────────┐ ┌───────────────┐  │
      │  │ thumbnails.py│ │async_queries.py│  │
      │  └──────────────┘ └───────────────┘  │
      └──────────────────────────────────────┘
               │
      ┌────────▼────────────────────────────────────────┐
      │           Global Task Framework (GTF)            │
      │  ┌────────────┐ ┌──────────┐ ┌───────────────┐  │
      │  │decorators.py│ │context.py│ │  manager.py   │  │
      │  └────────────┘ └──────────┘ └───────────────┘  │
      │  ┌────────────┐ ┌──────────┐ ┌───────────────┐  │
      │  │registry.py │ │ locks.py │ │ambient_context│  │
      │  └────────────┘ └──────────┘ └───────────────┘  │
      └─────────────────────────────────────────────────┘
```

## File Reference

### Core Entrypoint

| File | Purpose |
|------|---------|
| `celery_app.py` | Celery worker entrypoint. Creates the Flask app, imports task modules, and handles DB session lifecycle via `worker_process_init` and `task_postrun` signals. |

### Celery Task Definitions

| File | Purpose |
|------|---------|
| `cache.py` | Cache warm-up strategies (`DummyStrategy`, `TopNDashboardsStrategy`, `DashboardTagsStrategy`) and the `cache-warmup` / `fetch_url` Celery tasks. |
| `scheduler.py` | Alert/report scheduling (`reports.scheduler`, `reports.execute`), log/query/task pruning tasks, and the generic GTF `execute_task` executor. |
| `async_queries.py` | Async chart data loading (`load_chart_data_into_cache`, `load_explore_json_into_cache`) for non-blocking query execution. |
| `thumbnails.py` | Dashboard and chart screenshot/thumbnail generation tasks (`cache_chart_thumbnail`, `cache_dashboard_thumbnail`, `cache_dashboard_screenshot`). |
| `slack.py` | Slack channel cache warm-up task (`slack.cache_channels`). |

### Global Task Framework (GTF)

| File | Purpose |
|------|---------|
| `decorators.py` | `@task` decorator that registers functions with the GTF, handles scheduling via Celery, and manages deduplication. |
| `context.py` | `TaskContext` — the write-only context object tasks use to update progress, payload, and register abort/cleanup handlers. |
| `ambient_context.py` | `get_context()` / `use_context()` — contextvars-based ambient context so task functions access their context without parameter passing. |
| `manager.py` | `TaskManager` — handles task creation, Celery scheduling, deduplication, and Redis pub/sub abort notifications. |
| `registry.py` | `TaskRegistry` — maps task type names to executor functions. |
| `locks.py` | Distributed locking for task operations using Redis or DB-backed locks. |

### API & Data Layer

| File | Purpose |
|------|---------|
| `api.py` | `TaskRestApi` — REST endpoints for listing, getting, polling status, and cancelling tasks. |
| `schemas.py` | Marshmallow schemas for task API request/response serialization. |
| `filters.py` | `TaskFilter` — subscription-based query filter (non-admins see only subscribed tasks). |

### Types & Constants

| File | Purpose |
|------|---------|
| `types.py` | `ExecutorType` enum and `FixedExecutor` for determining which user runs scheduled tasks. |
| `constants.py` | GTF state sets: `TERMINAL_STATES`, `ACTIVE_STATES`, `ABORTABLE_STATES`, `ABORT_STATES`. |
| `exceptions.py` | `ExecutorNotFoundError`, `InvalidExecutorError`. |

### Utilities

| File | Purpose |
|------|---------|
| `utils.py` | `get_executor()` (user resolution for scheduled tasks), `fetch_csrf_token()`, dedup key generation, progress/error helpers, and property serialization. |
| `cron_util.py` | `cron_schedule_window()` — converts cron expressions to UTC schedule datetimes within a configurable window. |

## Key Data Flows

### Cache Warm-up (`cache.py`)
1. Celery beat triggers `cache_warmup` with a strategy name.
2. Strategy class queries DB for relevant charts/dashboards.
3. For each chart, `get_executor()` resolves the user to impersonate.
4. `fetch_url` tasks are dispatched with session cookies to hit the warm-up API.

### Report Execution (`scheduler.py`)
1. `scheduler()` runs periodically, finds active report schedules.
2. For each schedule matching the cron window, dispatches `execute()` with an ETA.
3. `execute()` runs `AsyncExecuteReportScheduleCommand` with the report ID.

### GTF Task Lifecycle (`decorators.py` → `scheduler.py:execute_task`)
1. `@task` decorator registers the function in `TaskRegistry`.
2. Calling `my_func.schedule(...)` creates a `Task` row and dispatches to Celery.
3. `execute_task` fetches the task, sets ambient context, and runs the function.
4. The function calls `get_context()` to update progress and check for abort.
5. On completion/failure/abort, atomic status transitions update the DB.

## Known Tech Debt

See GitHub issues labeled `tech-debt` + `automated-cleanup` for tracked items.
Key areas: null-safety in thumbnail tasks, module-level app context access in
async_queries, and inconsistent error handling patterns.
