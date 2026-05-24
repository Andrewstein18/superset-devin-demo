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

# `explore/components/controls/` — Chart Control Widgets

## Overview

This directory contains all chart control widgets used in the Explore control
panel sidebar. Each control maps to a `type` string in the control config
(e.g., `type: 'SelectControl'`) and is rendered by the `Control` component.

## Control Directories

| Directory | Purpose |
|-----------|---------|
| `AnnotationLayerControl/` | Annotation layer configuration with formula/event/interval layers |
| `CollectionControl/` | Generic collection editor for lists of objects |
| `ColorBreakpointsControl/` | Color breakpoint configuration for heatmaps |
| `ColorSchemeControl/` | Categorical and sequential color scheme selector |
| `ColumnConfigControl/` | Per-column configuration (formatting, alignment, etc.) |
| `ConditionalFormattingControl/` | Conditional formatting rules for table cells |
| `ContourControl/` | Contour layer configuration for map visualizations |
| `ControlPopover/` | Reusable popover wrapper for control edit UIs |
| `CurrencyControl/` | Currency format configuration |
| `CustomListItem/` | Custom drag-and-drop list item component |
| `DatasourceControl/` | Datasource selector with edit/swap functionality |
| `DateFilterControl/` | Date/time range picker with multiple frame types |
| `DndColumnSelectControl/` | Drag-and-drop column/metric/filter selection |
| `FilterControl/` | Adhoc filter configuration (simple + SQL modes) |
| `FixedOrMetricControl/` | Toggle between fixed value and metric selection |
| `LayerConfigsControl/` | GeoStyler-based map layer configuration |
| `MapViewControl/` | Map viewport/extent configuration |
| `MatrixifyControl/` | Matrix layout configuration utilities |
| `MetricControl/` | Metric selection with adhoc metric builder |
| `NumberControl/` | Numeric input control |
| `OptionControls/` | Drag-and-drop option pills for columns/metrics |
| `SelectAsyncControl/` | Async-loading select dropdown |
| `TextControl/` | Simple text input control |
| `TimeRangeControl/` | Time range display and edit control |
| `TimeSeriesColumnControl/` | Column configuration for time series charts |
| `VizTypeControl/` | Visualization type gallery and switcher |
| `ZoomConfigControl/` | Zoom level configuration with slider controls |

## Standalone Control Files

| File | Purpose |
|------|---------|
| `BoundsControl.tsx` | Min/max bounds input (e.g., Y-axis bounds) |
| `CheckboxControl.tsx` | Boolean toggle checkbox |
| `ColorPickerControl.tsx` | RGBA color picker |
| `ComparisonRangeLabel.tsx` | Label showing time comparison range |
| `HiddenControl.tsx` | Hidden control (stores value without UI) |
| `JSEditorControl.tsx` | JavaScript code editor |
| `MatrixifyDimensionControl.tsx` | Dimension selector for matrix layout |
| `SelectControl.tsx` | Core dropdown select (single/multi, freeform) |
| `SliderControl.tsx` | Numeric slider |
| `SpatialControl.tsx` | Lat/Lng spatial column selection |
| `SwitchControl.tsx` | Toggle switch |
| `TextAreaControl.tsx` | Code editor with modal expand (supports SQL, markdown, etc.) |
| `TimeOffsetControl.tsx` | Time offset configuration for comparisons |
| `VerticalRadioControl.tsx` | Vertical radio button group |
| `ViewQuery.tsx` | Read-only SQL query viewer |
| `ViewQueryModal.tsx` | Modal wrapper for query viewer |
| `ViewQueryModalFooter.tsx` | Footer actions for query viewer modal |
| `ViewportControl.tsx` | Map viewport configuration |
| `XAxisSortControl.tsx` | X-axis sort order control |
| `withAsyncVerification.tsx` | HOC that adds async validation to controls |
| `index.ts` | Barrel file mapping control type strings to components |

## Tech Debt Hotspots

- **`MetricsControl.tsx`**: 22 `any` type usages, the highest in any single file
- **`MatrixifyDimensionControl.tsx`**: 9 `any` usages, `catch (error: any)` pattern
- **`TextAreaControl.tsx`**: Class component with `withTheme` HOC and `as any` export cast
- **`ZoomConfigControl.tsx`**: 4 `@ts-expect-error` for Slider `onAfterChange` type mismatch
- **`translateToSQL.ts`**: 2 `@ts-expect-error` for missing operator types (`NOT LIKE`, `TEMPORAL_RANGE`)
- Multiple controls use `@ts-expect-error - defaultProps for backward compatibility`

## Connections

- **Registered in**: `controls/index.ts` maps type strings to React components
- **Consumed by**: `Control.tsx` renders the appropriate control based on `controlState.type`
- **Config from**: `src/explore/controls.tsx` defines control instances with their props
