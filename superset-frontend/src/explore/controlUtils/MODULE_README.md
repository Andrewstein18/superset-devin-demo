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

# `explore/controlUtils/` — Control Utility Functions

## Files

| File | Purpose |
|------|---------|
| `standardizedFormData.ts` | `StandardizedFormData` class — transforms form data between viz types |
| `getControlConfig.ts` | Retrieves control config from the chart control panel registry |
| `getControlState.ts` | Builds individual control state from config |
| `getSectionsToRender.ts` | Determines which control panel sections to render for a viz type |
| `getControlValuesCompatibleWithDatasource.ts` | Validates control values against a datasource |
| `getFormDataFromControls.ts` | Serializes controls state into form data |
| `getAllControlsState.ts` | Builds full controls state for a viz type |
| `index.ts` | Barrel file re-exporting all utilities |

## Key Class: `StandardizedFormData`

The `StandardizedFormData` class (261 lines) manages form data transformation when
users switch between visualization types. It:

1. Serializes shared metrics and columns into a standardized format
2. Memorizes form data per viz type so switching back restores previous config
3. Transforms controls between viz types via `transform(targetVizType, exploreState)`

### Tech Debt in `standardizedFormData.ts`

This file has **8 `eslint-disable` suppressions for `@typescript-eslint/no-explicit-any`**,
the highest concentration in the explore module. The `transform()` method signature
returns `any` and accepts `Record<string, any>`. These should use proper types from
`@superset-ui/chart-controls`.

## Other Functions

- **`getControlConfig(controlKey, vizType)`** — Looks up control config from registry. Contains a TODO about incorrect registry typing.
- **`getControlValuesCompatibleWithDatasource(datasource, controlState, controlConfig)`** — Filters control values to those valid for the current datasource.
- **`getSectionsToRender(vizType, datasourceType)`** — Returns control panel sections. Contains a TODO about updating `chartControlPanelRegistry` type.
