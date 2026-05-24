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

# `explore/reducers/` — Redux Reducers

## Files

| File | Purpose |
|------|---------|
| `exploreReducer.ts` | Main explore state reducer (~684 lines, handles ~20 action types) |
| `datasourcesReducer.ts` | Datasource state management |
| `saveModalReducer.ts` | Save modal state (slice name, save action type) |

## `exploreReducer.ts` — Key Actions Handled

- **`HYDRATE_EXPLORE`** — Full state initialization from server response
- **`SET_FIELD_VALUE`** — Updates individual control values and rebuilds form data
- **`UPDATE_FORM_DATA_BY_DATASOURCE`** — Handles datasource changes (revalidates controls)
- **`DYNAMIC_PLUGIN_CONTROLS_READY`** — Integrates controls from dynamically loaded chart plugins
- **`SET_STASH_FORM_DATA`** — Hides/shows form data fields
- **`SET_COMPATIBILITY`** — Updates compatible metrics/dimensions for semantic views

## State Shape

The `ExploreState` interface includes:
- `controls: ControlStateMapping` — All active control states
- `form_data: QueryFormData` — The serialized form data for the query
- `datasource?: Dataset` — The active datasource
- `slice?: Slice` — The saved chart metadata
- Various UI flags (`isDatasourceMetaLoading`, `isStarred`, `triggerRender`, etc.)

## Tech Debt

- Reducer is 684 lines — could benefit from splitting with `combineReducers` or Redux Toolkit slices
- Uses `JsonObject` and `JsonValue` from `@superset-ui/core` as escape hatches
- Some action handlers use broad type assertions
