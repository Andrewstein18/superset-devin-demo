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

# `explore/controlPanels/` — Control Panel Configurations

## Overview

This directory contains control panel configuration objects that define which
controls appear for specific visualization types and how those controls
interact with the application state.

## Files

| File | Purpose |
|------|---------|
| `Separator.ts` | Control panel config for the Separator (markdown/HTML) visualization |
| `sections.tsx` | Reusable control panel section definitions shared across viz types |
| `timeGrainSqlaAnimationOverrides.ts` | Overrides for the `time_grain_sqla` control in animation contexts |
| `Separator.test.ts` | Tests for the Separator control panel config |

## Key Exports

### `sections.tsx`
Exports reusable `ControlPanelSectionConfig` objects:
- **`datasourceAndVizType`** — Datasource selector, viz type picker, and hidden controls (slice_id, cache_timeout, url_params)
- **`colorScheme`** — Color scheme selection section
- **`sqlaTimeSeries`** — Time column and time range controls
- **`annotations`** — Annotation layer configuration
- **`NVD3TimeSeries`** — Query + Advanced Analytics sections for NVD3-based time series charts (rolling window, time comparison, resample)

### `Separator.ts`
A `ControlPanelConfig` for the Separator viz type with:
- Markup type selector (markdown/html)
- Code editor (`TextAreaControl`) with dynamic language mode
- Default template with section title and separator line

### `timeGrainSqlaAnimationOverrides.ts`
Provides `mapStateToProps` that reads `time_grain_sqla` choices from the
datasource and filters out null entries. Used to override time grain options
in animation-capable visualizations.

## Connections

- **Consumed by**: `controlUtils/getSectionsToRender.ts`, chart plugin registrations
- **Depends on**: `@superset-ui/chart-controls` types, `src/explore/exploreUtils` for `formatSelectOptions`
