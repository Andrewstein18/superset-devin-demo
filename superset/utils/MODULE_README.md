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

# superset/utils/ — Module Documentation

This directory contains shared utility functions and classes used throughout
the Apache Superset backend. The modules are grouped below by functional area.

---

## Core Utilities

### `core.py`
The largest module (~2 150 lines). Provides foundational enums, type
definitions, and helper functions consumed across the entire codebase.

**Key contents:**
- **Enums** — `FilterOperator`, `GenericDataType`, `DatasourceType`,
  `QueryStatus`, `QuerySource`, `AnnotationType`, `RowLevelSecurityFilterType`,
  and many more.
- **TypedDicts** — `AdhocFilterClause`, `QueryObjectFilterClause`,
  `HeaderDataType`, `DatasourceDict`.
- **Filter helpers** — `merge_extra_form_data`, `simple_filter_to_adhoc`,
  `convert_legacy_filters_into_adhoc`, `split_adhoc_filters_into_base_filters`.
- **User helpers** — `get_user`, `get_username`, `get_user_id`,
  `get_user_email`, `override_user`.
- **Timeout context managers** — `SigalrmTimeout` (POSIX signal-based),
  `TimerTimeout` (thread-based, Windows-safe).
- **Email** — `send_email_smtp`, `send_mime_email`.
- **DataFrame utilities** — `normalize_dttm_col`, `extract_dataframe_dtypes`.
- **Miscellaneous** — `markdown` (render + sanitize), `sanitize_svg_content`,
  `sanitize_url`, `zlib_compress` / `zlib_decompress`, `readfile`,
  `ensure_path_exists`, `parse_ssl_cert`, `parse_boolean_string`.

**Connections:** Imported by virtually every other backend module. Depends on
`date_parser`, `hashing`, `pandas`, and `backports` within this package.

---

### `backports.py`
Provides a `StrEnum` backport for Python < 3.11. Used by `core.py` and
several other modules that define string-based enumerations.

### `__init__.py`
Empty init file (contains only the ASF license header).

---

## Caching

### `cache.py`
Decorators and helpers for caching query results and API responses.

- `generate_cache_key` — deterministic cache key from a dict payload.
- `set_and_log_cache` — write to Flask-Caching with metrics and optional
  metadata DB tracking.
- `memoized_func` — decorator with a configurable key template and cache
  backend.
- `etag_cache` — ETag-based HTTP caching decorator for API views.

### `cache_manager.py`
Manages multiple Flask-Caching instances (data cache, thumbnail cache,
filter-state cache, explore-form-data cache) and initialises them from
app config.

- `CacheManager` — main class, wired up via `init_app`.
- `SupersetCache` — subclass of `flask_caching.Cache` that uses the
  configured `HASH_ALGORITHM` instead of hard-coded MD5.
- `ConfigurableHashMethod` — defers hash-algorithm selection to runtime
  config.

### `cache_keys.py`
Helpers for listing and invalidating cache keys stored in the metadata
database (`CacheKey` model).

---

## Data Formats & Export

### `json.py`
Custom JSON encoders and serialisers for types that `stdlib json` cannot
handle (NumPy, Pandas, `datetime`, `Decimal`, `UUID`, etc.).

- `DashboardEncoder` — sorted-key encoder for dashboard export.
- `json_iso_dttm_ser` / `json_int_dttm_ser` — datetime serialisers
  (ISO-8601 and epoch-milliseconds).
- `validate_json` — schema-aware validation with `jsonpath_ng`.
- `loads` / `dumps` — thin wrappers around `simplejson`.

### `csv.py`
CSV export utilities with injection-prevention.

- `escape_value` — prevents CSV injection by escaping formulae characters.
- `df_to_escaped_csv` — safe DataFrame-to-CSV export.
- `get_chart_csv_data` / `get_chart_dataframe` — fetch chart data over HTTP
  and convert to a Pandas DataFrame.

### `excel.py`
Analogous to `csv.py` but for `.xlsx` export via `openpyxl`.

### `pdf.py`
Builds a multi-page PDF from a list of screenshot byte arrays using Pillow.

---

## Date & Time

### `date_parser.py`
Natural-language date/time parsing for the Superset time-range picker.

- `parse_human_datetime` / `parse_human_timedelta` — convert free-text like
  "3 months ago" into `datetime` / `timedelta`.
- `get_since_until` — resolves a Superset `time_range` string into a
  `(since, until)` datetime pair.
- `DateRangeMigration` — parses legacy range formats.
- Uses `parsedatetime`, `dateutil`, `pyparsing`, and `holidays`.

### `dates.py`
Tiny helpers: `datetime_to_epoch`, `EPOCH` constant, `now_as_float`.

---

## Security & Authentication

### `encrypt.py`
Encryption field adapter and secret-key migration tooling.

- `EncryptedType` — SQLAlchemy `TypeDecorator` wrapping
  `sqlalchemy_utils.EncryptedType` (with `cache_ok = True`).
- `EncryptedFieldFactory` — factory initialised from app config.
- `SecretsMigrator` — re-encrypts all encrypted columns when the
  `SECRET_KEY` is rotated.

### `machine_auth.py`
`MachineAuthProvider` — injects session cookies into Selenium WebDriver
or Playwright `BrowserContext` so headless screenshots run as a given user.

### `oauth2.py`
OAuth 2 token management (PKCE code generation, token refresh with
distributed locking, JWT-based state encoding).

### `rls.py`
Row Level Security helpers — resolves RLS predicates for tables and injects
them into parsed SQL statements.

### `ssh_tunnel.py`
Utilities for masking/unmasking SSH tunnel credentials and resolving
default database ports.

---

## Screenshots & WebDriver

### `webdriver.py`
Abstractions for headless browser screenshot capture.

- `WebDriverProxy` (ABC) — base with `get_screenshot`.
- `WebDriverPlaywright` — Playwright-based implementation (preferred).
- `WebDriverSelenium` — Selenium-based fallback.
- `check_playwright_availability` / `validate_webdriver_config` — feature
  detection.

### `screenshots.py`
Higher-level screenshot orchestration with caching.

- `BaseScreenshot` / `ChartScreenshot` / `DashboardScreenshot` — cache
  screenshots in the thumbnail cache; compute cache keys from URL +
  user + window size.
- `ScreenshotCachePayload` — serialisable cache entry with status tracking.

### `screenshot_utils.py`
Tiled-screenshot helpers for Playwright: scroll a large dashboard and stitch
tiles into a single tall image.

---

## Logging & Observability

### `log.py`
Abstract event-logging framework.

- `AbstractEventLogger` — base class with `log`, `log_with_context`,
  `log_context` context manager, and a decorator wrapper.
- `DBEventLogger` — concrete implementation that persists events to the
  metadata database.
- `collect_request_payload` — extracts loggable data from Flask request.

### `logging_configurator.py`
`LoggingConfigurator` ABC and default implementations for configuring
the Python `logging` subsystem at app startup.

### `profiler.py`
`SupersetProfiler` — optional WSGI middleware that uses `pyinstrument` to
profile individual requests (enabled via `?_instrument=1`).

---

## Decorators & Helpers

### `decorators.py`
General-purpose decorators used across views and commands.

- `statsd_gauge` — emit statsd gauge on success/failure.
- `logs_context` — inject structured keys into `g.logs_context`.
- `debounce` — time-based call deduplication.
- `transaction` — SQLAlchemy commit/rollback wrapper.
- `suppress_logging` — context manager to silence loggers temporarily.

### `retries.py`
Thin wrapper around `backoff.on_exception` for retrying arbitrary callables.

### `class_utils.py`
`load_class_from_name` — dynamic class loading from a dotted module path.

---

## Hashing

### `hashing.py`
Configurable hashing (MD5 or SHA-256, controlled by `HASH_ALGORITHM`
config).

- `hash_from_str` / `hash_from_dict` — produce hex digests for cache keys,
  ETag values, and filter-option naming.

---

## Feature Flags

### `feature_flag_manager.py`
`FeatureFlagManager` — reads `DEFAULT_FEATURE_FLAGS` and `FEATURE_FLAGS`
from app config and evaluates feature gates at runtime.

---

## Integrations

### `slack.py`
Slack API helpers for alert/report delivery.

- `get_slack_client` — build a `WebClient` with rate-limit retry.
- `get_channels` / `get_channels_with_search` — paginated channel listing
  with caching.

### `link_redirect.py`
Rewrites external links in alert/report HTML emails to route through a
redirect warning page. Provides `is_safe_redirect_url` for open-redirect
prevention.

---

## Miscellaneous

### `currency.py`
Auto-detection of ISO 4217 currency codes from filtered chart data.

### `database.py`
`get_or_create_db` / `get_example_database` / `get_main_database` —
database record helpers, plus a MariaDB DDL fix.

### `dict_import_export.py`
Legacy dashboard import/export serialisation (being replaced by the
command-based import/export system).

### `dashboard_filter_scopes_converter.py`
Converts legacy filter-scope metadata into the modern format.

### `dashboard_import_export.py`
Legacy dashboard import/export (deprecated).

### `file.py`
`get_filename` — extracts a safe filename from a `Content-Disposition`
header.

### `filters.py`
Custom Jinja2 template filters registered with Flask.

### `jinja_template_validator.py`
Validates Jinja2 template syntax inside chart parameters and SQL filters
using `jinja2.sandbox.SandboxedEnvironment`.

### `mock_data.py`
Generates random data rows matching a given SQLAlchemy schema; used by
the `import-datasource` management command.

### `network.py`
`is_hostname_valid` / `is_port_open` — network connectivity checks.

### `pandas.py`
`detect_datetime_format` — samples a Pandas Series and infers its datetime
format string.

### `public_interfaces.py`
Decorator that marks a function signature as a public API and warns when
it changes.

### `schema.py`
Marshmallow field utilities for the REST API (e.g., `OneOfCaseInsensitive`).

### `url_map_converters.py`
Custom Werkzeug URL converters (`RegexConverter`, `ObjectTypeConverter`).

### `urls.py`
URL manipulation helpers: `modify_url_query`, `headless_url`.

### `version.py`
Reads and caches the installed Superset package version.

---

## Cross-Module Dependency Graph (simplified)

```
backports.py ← core.py ← (almost everything)
hashing.py ← cache.py, cache_manager.py, screenshots.py
date_parser.py ← core.py
json.py ← cache.py, csv.py, log.py, mock_data.py
webdriver.py ← screenshots.py ← screenshot_utils.py
machine_auth.py ← webdriver.py
encrypt.py ← (standalone, used by models)
decorators.py ← views, commands
```
