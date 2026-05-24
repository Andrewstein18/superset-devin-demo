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

# `explore/actions/` — Redux Action Creators

## Files

| File | Purpose |
|------|---------|
| `exploreActions.ts` | Core explore actions: control values, form data, chart title, favorites, compatibility |
| `hydrateExplore.ts` | Initial explore state hydration from server response |
| `datasourcesActions.ts` | Datasource fetching and updating |
| `saveModalActions.ts` | Chart save/overwrite modal actions |

## Key Action Creators

### `exploreActions.ts`
- **`setControlValue(name, value, validationErrors?)`** — Sets a single control value. Note: `value` is typed as `any` (tech debt).
- **`setExploreControls(formData)`** — Bulk-updates explore controls from form data.
- **`fetchFaveStar(sliceId)`** — Thunk that checks favorite status via REST API.
- **`saveFaveStar(sliceId, isStarred)`** — Thunk that toggles favorite status.
- **`fetchCompatibility(datasourceType, datasourceId, metrics, dims)`** — Thunk that fetches compatible metrics/dimensions for semantic views. Includes request sequencing to handle race conditions.

### `hydrateExplore.ts`
- **`hydrateExplore(data)`** — Dispatches `HYDRATE_EXPLORE` to initialize the full explore state from server-side data.

## Tech Debt

- `setControlValue` uses `value: any` — should use a union type or generic
- `validationErrors` typed as `any[]` — should use a proper error type
- No action type constants exported as a union type for exhaustive switch checks
