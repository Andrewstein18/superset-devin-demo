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

# superset/utils/pandas_postprocessing/ — Module Documentation

## Overview

This sub-package contains DataFrame transformation functions that are
applied *after* SQL execution and *before* chart rendering. Each module
exposes one or two public functions that accept a `pandas.DataFrame` and
return a transformed `DataFrame`.

These transformations are referenced in the `QueryContext.post_processing`
pipeline and are dispatched by name from the frontend chart configuration.

## Module Index

| Module | Function(s) | Description |
|--------|-------------|-------------|
| `aggregate.py` | `aggregate()` | Group-by aggregation with configurable aggregates. |
| `boxplot.py` | `boxplot()` | Computes boxplot statistics (quartiles, whiskers, outliers). |
| `compare.py` | `compare()` | Computes absolute/percentage differences between columns. |
| `contribution.py` | `contribution()` | Cell contribution to row or column totals. |
| `cum.py` | `cum()` | Cumulative operations (sum, mean, min, max). |
| `diff.py` | `diff()` | Period-over-period difference. |
| `flatten.py` | `flatten()` | Flattens MultiIndex columns into single-level strings. |
| `geography.py` | `geohash_decode()`, `geohash_encode()`, `geodetic_parse()` | Geospatial column parsing and encoding. |
| `histogram.py` | `histogram()` | Bins numeric data into histogram buckets. |
| `pivot.py` | `pivot()` | Pivot table with aggregation and optional subtotals. |
| `prophet.py` | `prophet()` | Time-series forecasting via Facebook Prophet. |
| `rank.py` | `rank()` | Window ranking (dense, min, first, etc.). |
| `rename.py` | `rename()` | Column renaming with optional regex support. |
| `resample.py` | `resample()` | Time-series resampling (up/down) with fill methods. |
| `rolling.py` | `rolling()` | Rolling-window aggregations (mean, sum, std, …). |
| `select.py` | `select()` | Column selection and reordering. |
| `sort.py` | `sort()` | Row sorting by one or more columns. |
| `utils.py` | Validation helpers | `validate_column_args`, `escape_separator`, column-name utilities shared across the sub-package. |

## Data Flow

```
SQL Result (DataFrame)
  │
  ▼
post_processing pipeline
  │
  ├─► aggregate / pivot / sort / …
  │
  ▼
Serialized to JSON → frontend chart
```

## Key Conventions

- Every public function takes `df: DataFrame` as its first argument and
  returns a `DataFrame`.
- Column validation is performed via `@validate_column_args` decorator from
  `utils.py` (raises `InvalidPostProcessingError` on missing columns).
- The `__init__.py` re-exports all public functions so callers import from
  `superset.utils.pandas_postprocessing` directly.
