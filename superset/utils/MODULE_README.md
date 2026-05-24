# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# superset/utils/ — Module Documentation

## Overview

The `superset/utils/` package provides shared utility functions and classes
used across the Superset backend. It covers caching, date parsing, JSON
serialization, security helpers, screenshot/webdriver automation, encryption,
and many general-purpose helpers.

## Module Index

### Core Utilities

| Module | Purpose |
|--------|---------|
| `core.py` | Central utility module (~2 150 lines). Defines enums (`FilterOperator`, `GenericDataType`, `QueryStatus`, …), filter merging, email via SMTP, timeout context managers, DataFrame type inference, and user/session helpers. |
| `json.py` | Custom JSON encoders/decoders for dates, NumPy types, UUIDs, `Decimal`, and Pandas objects. Wraps `simplejson` and exposes `dumps`/`loads` with Superset-specific defaults. |
| `hashing.py` | Configurable hashing (`md5` or `sha256`) driven by `HASH_ALGORITHM` config. Used for cache keys and content fingerprinting. |
| `decorators.py` | Function decorators: `statsd_gauge` (metrics), `logs_context` (structured logging), `debounce`, and stats-timer helpers. |
| `backports.py` | Back-ported `StrEnum` for Python < 3.11 compatibility. |

### Caching

| Module | Purpose |
|--------|---------|
| `cache.py` | Cache key generation, `set_and_log_cache`, and `memoized_func` / `etag_cache` decorators. |
| `cache_keys.py` | Helpers to build deterministic cache keys from query context. |
| `cache_manager.py` | `CacheManager` Flask extension that initialises multiple `Cache` instances (data, thumbnail, filter-state, explore-form-data). Also provides `ConfigurableHashMethod` for FIPS-compliant hashing. |

### Date & Time

| Module | Purpose |
|--------|---------|
| `date_parser.py` | Rich natural-language date parsing (e.g. `"1 year ago"`, `"last monday"`). Implements a custom PEG grammar for time-range expressions and handles ordinal/holiday-aware logic. |
| `dates.py` | Thin helpers: `datetime_to_epoch`, `now_as_float`, and the `EPOCH` constant. |

### Data Processing

| Module | Purpose |
|--------|---------|
| `csv.py` | CSV injection escaping (`escape_value`), DataFrame-to-CSV export, and chart CSV data fetching. |
| `excel.py` | DataFrame-to-Excel export with formatting. |
| `pandas.py` | Pandas helpers: datetime format detection, data type utilities. |
| `pandas_postprocessing/` | Sub-package of DataFrame transformations applied after SQL execution: `aggregate`, `pivot`, `rolling`, `cum`, `diff`, `compare`, `rename`, `sort`, `select`, `flatten`, `boxplot`, `histogram`, `rank`, `resample`, `contribution`, `geography`, `prophet`. |

### Security & Auth

| Module | Purpose |
|--------|---------|
| `encrypt.py` | `EncryptedFieldFactory` for SQLAlchemy column encryption; `SecretsMigrator` for re-encrypting secrets after key rotation. |
| `machine_auth.py` | `MachineAuthProvider` — injects session cookies into Selenium/Playwright browsers for headless screenshot auth. |
| `oauth2.py` | OAuth 2 + PKCE token management: acquire, refresh, and store per-user per-database access tokens. |
| `rls.py` | Row-Level Security: collects RLS predicates for tables referenced in a SQL statement and injects them as WHERE clauses or subqueries. |
| `filters.py` | Builds SQLAlchemy filter clauses for dataset access control (database, datasource, schema, catalog permissions). |
| `ssh_tunnel.py` | SSH tunnel helpers for database connections. |

### Screenshot & Reporting

| Module | Purpose |
|--------|---------|
| `webdriver.py` | Selenium and Playwright WebDriver proxy classes. Handles headless browser lifecycle, screenshot capture, and error detection. |
| `screenshots.py` | `BaseScreenshot` / `ChartScreenshot` / `DashboardScreenshot` — orchestrate screenshot caching, thumbnail generation, and digest computation. |
| `screenshot_utils.py` | Low-level helpers: tiled-screenshot capture and image tile combining via Pillow. |
| `pdf.py` | HTML-to-PDF conversion helpers (used in report scheduling). |
| `slack.py` | Slack API integration: client setup, channel listing with pagination and caching, and channel search. |

### Configuration & Feature Flags

| Module | Purpose |
|--------|---------|
| `feature_flag_manager.py` | `FeatureFlagManager` — reads `FEATURE_FLAGS` and `DEFAULT_FEATURE_FLAGS` from config, with optional custom evaluation functions. |
| `logging_configurator.py` | Abstract + default logging configuration for Superset. |

### Import / Export & Migration

| Module | Purpose |
|--------|---------|
| `dashboard_import_export.py` | Legacy dashboard import/export helpers. |
| `dashboard_filter_scopes_converter.py` | Converts legacy filter-scope format to the scoped-filter format. |
| `dict_import_export.py` | Generic dict-based import/export for Superset objects. |
| `database.py` | `get_or_create_db`, `get_example_database`, `remove_database`, and a MariaDB DDL compatibility patch. |

### Networking & URLs

| Module | Purpose |
|--------|---------|
| `urls.py` | URL manipulation: `modify_url_query`, `headless_url` (translates public URL to headless-accessible URL). |
| `url_map_converters.py` | Custom Werkzeug URL converters for regex and object-type routes. |
| `network.py` | Network helpers for DNS resolution and connectivity checks. |
| `link_redirect.py` | Short-link redirect handler. |

### Miscellaneous

| Module | Purpose |
|--------|---------|
| `class_utils.py` | `load_class_from_name` — imports a class from a dotted Python path. |
| `currency.py` | Currency formatting and locale-aware display. |
| `file.py` | File-type validation helpers. |
| `mock_data.py` | Random test-data generators for each SQLAlchemy column type (used in dev/test). |
| `profiler.py` | WSGI profiler middleware (`SupersetProfiler`). |
| `public_interfaces.py` | Computes MD5 fingerprints of public API surfaces to detect breaking changes. |
| `retries.py` | Generic `retry_call` wrapper with configurable exceptions, back-off, and delay. |
| `schema.py` | Marshmallow schema helpers. |
| `version.py` | Git-based version detection for Superset builds. |
| `log.py` | `AbstractEventLogger` and `DBEventLogger` — structured event/action logging with request payload collection. |
| `jinja_template_validator.py` | Validates Jinja SQL templates before execution. |

## Key Cross-Module Relationships

```
core.py ──► hashing.py ──► json.py
   │
   ├──► date_parser.py ──► dates.py
   │
   └──► database.py
          │
cache.py ──► cache_manager.py ──► hashing.py
          │
webdriver.py ──► machine_auth.py ──► urls.py
   │
   └──► screenshot_utils.py
          │
screenshots.py ──► webdriver.py ──► cache.py
          │
log.py ──► core.py ──► json.py
```

## Known Tech Debt

- `core.py` is a ~2 150-line "god module" aggregating many unrelated concerns.
- Several broad `except Exception:` / `except BaseException:` blocks silently
  swallow errors (see csv.py, core.py, log.py, webdriver.py).
- `encrypt.py` builds SQL via f-strings (`_select_columns_from_table`,
  `_re_encrypt_row`) — safe in practice (inputs are ORM metadata) but fragile.
- `merge_extra_form_data` in core.py uses `getattr` on dict objects, causing
  the append-key merge logic to silently do nothing.
- Multiple stale TODO comments in database.py (code duplication, anti-pattern
  acknowledgements).
