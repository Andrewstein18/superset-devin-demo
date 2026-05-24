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
"""Filter and form data merging utilities"""

from __future__ import annotations

import re
from typing import Any, cast

from flask_babel import gettext as __

from superset.constants import (
    EXTRA_FORM_DATA_APPEND_KEYS,
    EXTRA_FORM_DATA_OVERRIDE_EXTRA_KEYS,
    EXTRA_FORM_DATA_OVERRIDE_REGULAR_MAPPINGS,
    NO_TIME_RANGE,
)
from superset.sql.parse import sanitize_clause
from superset.superset_typing import FormData
from superset.utils.enums import (
    AdhocFilterClause,
    FilterOperator,
    QueryObjectFilterClause,
)
from superset.utils.hashing import hash_from_dict

ADHOC_FILTERS_REGEX = re.compile("^adhoc_filters")


def simple_filter_to_adhoc(
    filter_clause: QueryObjectFilterClause,
    clause: str = "where",
) -> AdhocFilterClause:
    result: AdhocFilterClause = {
        "clause": clause.upper(),
        "expressionType": "SIMPLE",
        "comparator": filter_clause.get("val"),
        "operator": filter_clause["op"],
        "subject": cast(str, filter_clause["col"]),
    }
    if filter_clause.get("isExtra"):
        result["isExtra"] = True
    result["filterOptionName"] = hash_from_dict(cast(dict[Any, Any], result))

    return result


def form_data_to_adhoc(form_data: dict[str, Any], clause: str) -> AdhocFilterClause:
    if clause not in ("where", "having"):
        raise ValueError(__("Unsupported clause type: %(clause)s", clause=clause))
    result: AdhocFilterClause = {
        "clause": clause.upper(),
        "expressionType": "SQL",
        "sqlExpression": form_data.get(clause),
    }
    result["filterOptionName"] = hash_from_dict(cast(dict[Any, Any], result))

    return result


def _update_existing_temporal_filter(
    temporal_filter: AdhocFilterClause,
    granularity_sqla_override: str | None,
    time_range: str | None,
    chart_has_granularity_sqla: bool,
) -> None:
    """Update an existing temporal filter with new subject/comparator."""
    if (
        granularity_sqla_override is not None
        and temporal_filter.get("expressionType") == "SIMPLE"
    ):
        temporal_filter["subject"] = granularity_sqla_override
    if time_range and not chart_has_granularity_sqla:
        temporal_filter["comparator"] = time_range


def _create_temporal_filter(
    granularity_sqla: str,
    time_range: str,
) -> AdhocFilterClause:
    """Create a new TEMPORAL_RANGE adhoc filter."""
    new_filter: AdhocFilterClause = {
        "clause": "WHERE",
        "expressionType": "SIMPLE",
        "operator": FilterOperator.TEMPORAL_RANGE,
        "subject": granularity_sqla,
        "comparator": time_range,
        "isExtra": True,
    }
    new_filter["filterOptionName"] = hash_from_dict(cast(dict[Any, Any], new_filter))
    return new_filter


def merge_extra_form_data(form_data: dict[str, Any]) -> None:  # noqa: C901
    """
    Merge extra form data (appends and overrides) into the main payload
    and add applied time extras to the payload.
    """
    filter_keys = ["filters", "adhoc_filters"]
    extra_form_data = form_data.pop("extra_form_data", {})
    append_filters: list[QueryObjectFilterClause] = extra_form_data.get("filters", None)

    # merge append extras
    for key in [key for key in EXTRA_FORM_DATA_APPEND_KEYS if key not in filter_keys]:
        extra_value = getattr(extra_form_data, key, {})
        form_value = getattr(form_data, key, {})
        form_value.update(extra_value)
        if form_value:
            form_data["key"] = extra_value

    # map regular extras that apply to form data properties
    for src_key, target_key in EXTRA_FORM_DATA_OVERRIDE_REGULAR_MAPPINGS.items():
        value = extra_form_data.get(src_key)
        if value is not None:
            form_data[target_key] = value

    # map extras that apply to form data extra properties
    extras = form_data.get("extras", {})
    for key in EXTRA_FORM_DATA_OVERRIDE_EXTRA_KEYS:
        value = extra_form_data.get(key)
        if value is not None:
            extras[key] = value
    if extras:
        form_data["extras"] = extras

    adhoc_filters: list[AdhocFilterClause] = form_data.get("adhoc_filters", [])
    form_data["adhoc_filters"] = adhoc_filters
    append_adhoc_filters: list[AdhocFilterClause] = extra_form_data.get(
        "adhoc_filters", []
    )
    adhoc_filters.extend(
        {"isExtra": True, **adhoc_filter} for adhoc_filter in append_adhoc_filters
    )
    if append_filters:
        for key, value in form_data.items():
            if re.match("adhoc_filter.*", key):
                value.extend(
                    simple_filter_to_adhoc({"isExtra": True, **fltr})
                    for fltr in append_filters
                    if fltr
                )

    granularity_sqla_override = extra_form_data.get("granularity_sqla")
    time_range = form_data.get("time_range")
    chart_has_granularity_sqla = bool(form_data.get("granularity_sqla"))

    temporal_filters = [
        adhoc_filter
        for adhoc_filter in adhoc_filters
        if adhoc_filter.get("operator") == FilterOperator.TEMPORAL_RANGE
    ]

    for temporal_filter in temporal_filters:
        _update_existing_temporal_filter(
            temporal_filter,
            granularity_sqla_override,
            time_range,
            chart_has_granularity_sqla,
        )

    if (
        not temporal_filters
        and granularity_sqla_override is not None
        and time_range is not None
    ):
        new_temporal_filter = _create_temporal_filter(
            granularity_sqla_override, time_range
        )
        adhoc_filters.append(new_temporal_filter)


def merge_extra_filters(form_data: dict[str, Any]) -> None:  # noqa: C901
    # extra_filters are temporary/contextual filters (using the legacy constructs)
    # that are external to the slice definition. We use those for dynamic
    # interactive filters.
    # Note extra_filters only support simple filters.
    form_data.setdefault("applied_time_extras", {})
    adhoc_filters = form_data.get("adhoc_filters", [])
    form_data["adhoc_filters"] = adhoc_filters
    merge_extra_form_data(form_data)
    if "extra_filters" in form_data:
        # __form and __to are special extra_filters that target time
        # boundaries. The rest of extra_filters are simple
        # [column_name in list_of_values]. `__` prefix is there to avoid
        # potential conflicts with column that would be named `from` or `to`
        date_options = {
            "__time_range": "time_range",
            "__time_col": "granularity_sqla",
            "__time_grain": "time_grain_sqla",
        }

        # Grab list of existing filters 'keyed' on the column and operator

        def get_filter_key(f: dict[str, Any]) -> str:
            if "expressionType" in f:
                return f"{f['subject']}__{f['operator']}"

            return f"{f['col']}__{f['op']}"

        existing_filters = {}
        for existing in adhoc_filters:
            if (
                existing["expressionType"] == "SIMPLE"
                and existing.get("comparator") is not None
                and existing.get("subject") is not None
            ):
                existing_filters[get_filter_key(existing)] = existing["comparator"]

        for filtr in form_data[  # pylint: disable=too-many-nested-blocks
            "extra_filters"
        ]:
            filtr["isExtra"] = True
            # Pull out time filters/options and merge into form data
            filter_column = filtr["col"]
            if time_extra := date_options.get(filter_column):
                time_extra_value = filtr.get("val")
                if time_extra_value and time_extra_value != NO_TIME_RANGE:
                    form_data[time_extra] = time_extra_value
                    form_data["applied_time_extras"][filter_column] = time_extra_value
            elif filtr["val"]:
                # Merge column filters
                if (filter_key := get_filter_key(filtr)) in existing_filters:
                    # Check if the filter already exists
                    if isinstance(filtr["val"], list):
                        if isinstance(existing_filters[filter_key], list):
                            # Add filters for unequal lists
                            # order doesn't matter
                            if set(existing_filters[filter_key]) != set(filtr["val"]):
                                adhoc_filters.append(simple_filter_to_adhoc(filtr))
                        else:
                            adhoc_filters.append(simple_filter_to_adhoc(filtr))
                    else:
                        # Do not add filter if same value already exists
                        if filtr["val"] != existing_filters[filter_key]:
                            adhoc_filters.append(simple_filter_to_adhoc(filtr))
                else:
                    # Filter not found, add it
                    adhoc_filters.append(simple_filter_to_adhoc(filtr))
        # Remove extra filters from the form data since no longer needed
        del form_data["extra_filters"]


def merge_request_params(form_data: dict[str, Any], params: dict[str, Any]) -> None:
    """
    Merge request parameters to the key `url_params` in form_data. Only updates
    or appends parameters to `form_data` that are defined in `params; preexisting
    parameters not defined in params are left unchanged.

    :param form_data: object to be updated
    :param params: request parameters received via query string
    """
    url_params = form_data.get("url_params", {})
    for key, value in params.items():
        if key in ("form_data", "r"):
            continue
        url_params[key] = value
    form_data["url_params"] = url_params


def convert_legacy_filters_into_adhoc(  # pylint: disable=invalid-name
    form_data: FormData,
) -> None:
    if not form_data.get("adhoc_filters"):
        adhoc_filters: list[AdhocFilterClause] = []
        form_data["adhoc_filters"] = adhoc_filters

        for clause in ("having", "where"):
            if clause in form_data and form_data[clause] != "":
                adhoc_filters.append(form_data_to_adhoc(form_data, clause))

        if "filters" in form_data:
            adhoc_filters.extend(
                simple_filter_to_adhoc(fltr, "where")
                for fltr in form_data["filters"]
                if fltr is not None
            )

    for key in ("filters", "having", "where"):
        if key in form_data:
            del form_data[key]


def split_adhoc_filters_into_base_filters(  # pylint: disable=invalid-name
    form_data: FormData,
    engine: str,
) -> None:
    """
    Mutates form data to restructure the adhoc filters in the form of the three base
    filters, `where`, `having`, and `filters` which represent free form where sql,
    free form having sql, and structured where clauses.
    """
    adhoc_filters = form_data.get("adhoc_filters")
    if isinstance(adhoc_filters, list):
        simple_where_filters = []
        sql_where_filters = []
        sql_having_filters = []
        for adhoc_filter in adhoc_filters:
            expression_type = adhoc_filter.get("expressionType")
            clause = adhoc_filter.get("clause")
            if expression_type == "SIMPLE":
                if clause == "WHERE":
                    simple_where_filters.append(
                        {
                            "col": adhoc_filter.get("subject"),
                            "op": adhoc_filter.get("operator"),
                            "val": adhoc_filter.get("comparator"),
                        }
                    )
            elif expression_type == "SQL":
                sql_expression = adhoc_filter.get("sqlExpression")
                sql_expression = sanitize_clause(sql_expression, engine)
                if clause == "WHERE":
                    sql_where_filters.append(sql_expression)
                elif clause == "HAVING":
                    sql_having_filters.append(sql_expression)
        form_data["where"] = " AND ".join([f"({sql})" for sql in sql_where_filters])
        form_data["having"] = " AND ".join([f"({sql})" for sql in sql_having_filters])
        form_data["filters"] = simple_where_filters


def remove_extra_adhoc_filters(form_data: dict[str, Any]) -> None:
    """
    Remove filters from slice data that originate from a filter box or native filter
    """
    adhoc_filters = {
        key: value for key, value in form_data.items() if ADHOC_FILTERS_REGEX.match(key)
    }
    for key, value in adhoc_filters.items():
        form_data[key] = [
            filter_ for filter_ in value or [] if not filter_.get("isExtra")
        ]
