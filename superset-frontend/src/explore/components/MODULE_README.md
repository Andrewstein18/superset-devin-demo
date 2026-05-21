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

# `explore/components/` — Explore UI Components

## Directory Structure

| Component | Purpose |
|-----------|---------|
| `ExploreViewContainer/` | Main container for the chart builder page |
| `DataTablesPane/` | Data preview tables (results, samples, query) |
| `DatasourcePanel/` | Left sidebar datasource column/metric browser |
| `controls/` | Individual control components (MetricControl, FilterControl, etc.) |
| `ExploreAlert.tsx` | Alert banner for explore errors |
| `ExploreContentPopover.tsx` | Popover wrapper for explore content |
| `ControlHeader.stories.tsx` | Storybook stories for control header |

## Key Components

### `ExploreViewContainer/index.tsx`
The top-level explore page container. Manages layout (chart + controls), chart rendering,
and query execution. Connected to Redux store.

### `DatasourcePanel/`
The left sidebar showing available columns and metrics from the selected datasource.
Includes drag-and-drop support (`DatasourcePanelDragOption`) and folder organization
(`transformDatasourceFolders`).

### `DataTablesPane/`
Tabbed pane below the chart showing query results, samples, and SQL.
Uses `useResultsPane`, `SamplesPane`, and `SingleQueryResultPane` components.

### `controls/`
The largest subdirectory — contains all chart control widgets:
- `MetricControl/` — Metric selection with adhoc metric support
- `FilterControl/` — Filter configuration (adhoc filters, time range)
- `VizTypeControl/` — Visualization type gallery
- `TextAreaControl.tsx` — SQL/text input with code editor
- `SelectControl.tsx` — Dropdown select with search
- `MatrixifyDimensionControl.tsx` — Matrix layout dimension control
- `ZoomConfigControl/` — Zoom configuration for charts

## Tech Debt Hotspots

- **`MetricsControl.tsx`**: 22 `any` type usages — the highest in any single component file
- **`TextAreaControl.tsx`**: Uses `eslint-disable` for `no-explicit-any`, has `defaultProps` pattern
- **`MatrixifyDimensionControl.tsx`**: 9 `any` usages
- **`ZoomConfigControl/`**: 4 `@ts-expect-error` suppressions for Slider component type mismatches
- Multiple controls use `@ts-expect-error - defaultProps for backward compatibility`
