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

# `superset-frontend/src/explore/` — Chart Builder Module

## Overview

The **Explore** module is the chart builder interface in Apache Superset. It allows
users to create, modify, and visualize charts by selecting datasources, configuring
controls (metrics, dimensions, filters), and rendering visualizations.

## Directory Structure

| Path | Purpose |
|------|---------|
| `store.ts` | Redux store initialization, `getControlsState()`, deprecated control migration |
| `types.ts` | TypeScript interfaces: `ChartState`, `ExplorePageState`, `Datasource` |
| `constants.ts` | Aggregates, operators, filter config, time filter mappings |
| `controls.tsx` | Control instance definitions reused across visualization types |
| `fixtures.tsx` | Test fixture data for explore components |
| `actions/` | Redux action creators (`exploreActions`, `hydrateExplore`, `datasourcesActions`, `saveModalActions`) |
| `reducers/` | Redux reducers (`exploreReducer`, `datasourcesReducer`, `saveModalReducer`) |
| `controlUtils/` | Control utilities: `standardizedFormData`, `getControlConfig`, `getSectionsToRender` |
| `controlPanels/` | Control panel section definitions (`Separator`, `sections`, time grain overrides) |
| `exploreUtils/` | Explore helper functions (`getChartDataUri`, `shouldUseLegacyApi`) |
| `components/` | React components (ExploreViewContainer, DataTablesPane, DatasourcePanel, controls/) |

## Key Functions

### `store.ts`
- **`getControlsState(state, formData)`** — Builds the controls state object for the active visualization type.
- **`applyDefaultFormData(formData)`** — Normalizes deprecated controls and builds default form data.
- **`handleDeprecatedControls(formData)`** — Migrates legacy `y_axis_zero` and matrixify controls to the new format.

### `actions/exploreActions.ts`
- **`setControlValue(name, value)`** — Dispatches a control value change.
- **`fetchFaveStar(sliceId)`** — Checks if a chart is favorited.
- **`fetchCompatibility(datasourceType, datasourceId, metrics, dims)`** — Fetches compatible metrics/dimensions for semantic views.

### `reducers/exploreReducer.ts`
- Handles ~20 action types including `HYDRATE_EXPLORE`, `SET_FIELD_VALUE`, `UPDATE_FORM_DATA_BY_DATASOURCE`, and `DYNAMIC_PLUGIN_CONTROLS_READY`.

## Tech Debt Summary

| Category | Count | Severity |
|----------|-------|----------|
| `: any` type annotations | 122 occurrences across source files | High |
| `eslint-disable` suppressions | 170 across the module | Medium |
| `@ts-expect-error` suppressions | 33 total (15 in non-test files) | Medium |
| Stale TODO/FIXME comments | 83 across test and source files | Low |
| `as any` type casts in `store.ts` | 4 in core state initialization | High |
| `standardizedFormData.ts` eslint suppressions | 8 `no-explicit-any` in data transform pipeline | High |
| Silent error swallowing | `fetchFaveStar` drops network errors without handling | High |
| `translateToSQL.ts` incomplete operator map | Missing `NOT LIKE` and `TEMPORAL_RANGE` operators | Medium |
| Class component pattern | `SaveModal.tsx` (842 lines), `TextAreaControl.tsx` use class components | Medium |

## Connections

- **Imports from**: `@superset-ui/core`, `@superset-ui/chart-controls`, `src/components/Chart`, `src/types/`
- **Used by**: Dashboard views, chart rendering pipeline, SQL Lab chart preview
- **Redux store**: Connected to global store via `charts`, `datasources`, and `explore` slices
