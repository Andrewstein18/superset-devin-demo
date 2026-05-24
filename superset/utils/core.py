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
"""Utility functions used across Superset

Re-exports from focused submodules for backward compatibility:
- superset.utils.enums: Enum and TypedDict definitions
- superset.utils.email: SMTP email sending
- superset.utils.timeout: Timeout context managers
- superset.utils.form_data: Filter/form data merging
- superset.utils.user: User session helpers
- superset.utils.sanitize: URL, SVG, HTML sanitization
"""

from __future__ import annotations

import collections
import errno
import logging
import os
import re
import sqlite3
import traceback
import uuid
import warnings
import zlib
from collections.abc import Iterable, Iterator, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from timeit import default_timer
from typing import (
    Any,
    Callable,
    cast,
    Optional,
    TYPE_CHECKING,
    TypeVar,
)
from urllib.parse import unquote_plus
from zipfile import ZipFile

import pandas as pd
import sqlalchemy as sa
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import Certificate, load_pem_x509_certificate
from flask import current_app as app, request
from flask_sqlalchemy import SQLAlchemy
from pandas.api.types import infer_dtype
from pandas.core.dtypes.common import is_numeric_dtype
from sqlalchemy import event, exc, inspect, select, Text
from sqlalchemy.dialects.mysql import LONGTEXT, MEDIUMTEXT
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql.type_api import Variant
from typing_extensions import TypeGuard

from superset.constants import DEFAULT_USER_AGENT
from superset.exceptions import (
    CertificateException,
    SupersetException,
)
from superset.superset_typing import (
    AdhocColumn,
    AdhocMetric,
    AdhocMetricColumn,
    Column,
    FlaskResponse,
    Metric,
)
from superset.utils.database import get_example_database
from superset.utils.date_parser import parse_human_timedelta

# Re-export from submodules for backward compatibility
from superset.utils.email import (  # noqa: F401
    recipients_string_to_list,
    send_email_smtp,
    send_mime_email,
)
from superset.utils.enums import (  # noqa: F401
    AdhocFilterClause,
    AdhocMetricExpressionType,
    AnnotationType,
    ColumnSpec,
    ColumnTypeSource,
    DashboardStatus,
    DatasourceDict,
    DatasourceName,
    DatasourceType,
    ExtraFiltersReasonType,
    ExtraFiltersTimeColumnType,
    FilterOperator,
    FilterStringOperators,
    GenericDataType,
    HeaderDataType,
    LoggerLevel,
    PostProcessingBoxplotWhiskerType,
    PostProcessingContributionOrientation,
    QueryObjectFilterClause,
    QuerySource,
    QueryStatus,
    ReservedUrlParameters,
    RowLevelSecurityFilterType,
    SqlExpressionType,
)
from superset.utils.form_data import (  # noqa: F401
    _create_temporal_filter,
    _update_existing_temporal_filter,
    convert_legacy_filters_into_adhoc,
    form_data_to_adhoc,
    merge_extra_filters,
    merge_extra_form_data,
    merge_request_params,
    remove_extra_adhoc_filters,
    simple_filter_to_adhoc,
    split_adhoc_filters_into_base_filters,
)
from superset.utils.hashing import hash_from_str
from superset.utils.pandas import detect_datetime_format
from superset.utils.sanitize import (  # noqa: F401
    markdown,
    sanitize_svg_content,
    sanitize_url,
)
from superset.utils.timeout import (  # noqa: F401
    SigalrmTimeout,
    timeout,
    TimerTimeout,
)
from superset.utils.user import (  # noqa: F401
    get_user,
    get_user_email,
    get_user_id,
    get_username,
    override_user,
    user_label,
)

if TYPE_CHECKING:
    from superset.explorables.base import ColumnMetadata, Explorable
    from superset.models.core import Database

logging.getLogger("MARKDOWN").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

DTTM_ALIAS = "__timestamp"

TIME_COMPARISON = "__"

JS_MAX_INTEGER = 9007199254740991  # Largest int Java Script can handle 2^53-1

InputType = TypeVar("InputType")  # pylint: disable=invalid-name

ADHOC_FILTERS_REGEX = re.compile("^adhoc_filters")

TYPE_MAPPING = {
    re.compile(r"INT", re.IGNORECASE): "integer",
    re.compile(r"CHAR|TEXT|VARCHAR", re.IGNORECASE): "string",
    re.compile(r"DECIMAL|NUMERIC|FLOAT|DOUBLE", re.IGNORECASE): "floating",
    re.compile(r"BOOL", re.IGNORECASE): "boolean",
    re.compile(r"DATE|TIME", re.IGNORECASE): "datetime64",
}

METRIC_MAP_TYPE = {
    "SUM": "floating",
    "AVG": "floating",
    "COUNT": "floating",
    "COUNT_DISTINCT": "floating",
    "MIN": "numeric",
    "MAX": "numeric",
    "FIRST": "string",
    "LAST": "string",
    "GROUP_CONCAT": "string",
    "ARRAY_AGG": "string",
    "STRING_AGG": "string",
    "MEDIAN": "floating",
    "PERCENTILE": "floating",
    "VARIANCE": "floating",
    "STDDEV": "floating",
}


def parse_js_uri_path_item(
    item: str | None, unquote: bool = True, eval_undefined: bool = False
) -> str | None:
    """Parse an uri path item made with js.

    :param item: an uri path component
    :param unquote: Perform unquoting of string using urllib.parse.unquote_plus()
    :param eval_undefined: When set to True and item is either 'null' or 'undefined',
    assume item is undefined and return None.
    :return: Either None, the original item or unquoted item
    """
    item = None if eval_undefined and item in ("null", "undefined") else item
    return unquote_plus(item) if unquote and item else item


def cast_to_num(value: float | int | str | None) -> float | int | None:
    """Casts a value to an int/float

    >>> cast_to_num('1 ')
    1.0
    >>> cast_to_num(' 2')
    2.0
    >>> cast_to_num('5')
    5
    >>> cast_to_num('5.2')
    5.2
    >>> cast_to_num(10)
    10
    >>> cast_to_num(10.1)
    10.1
    >>> cast_to_num(None) is None
    True
    >>> cast_to_num('this is not a string') is None
    True

    :param value: value to be converted to numeric representation
    :returns: value cast to `int` if value is all digits, `float` if `value` is
              decimal value and `None`` if it can't be converted
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return None


def cast_to_boolean(value: Any) -> bool | None:
    """Casts a value to an int/float

    >>> cast_to_boolean(1)
    True
    >>> cast_to_boolean(0)
    False
    >>> cast_to_boolean(0.5)
    True
    >>> cast_to_boolean('true')
    True
    >>> cast_to_boolean('false')
    False
    >>> cast_to_boolean('False')
    False
    >>> cast_to_boolean(None)

    :param value: value to be converted to boolean representation
    :returns: value cast to `bool`. when value is 'true' or value that are not 0
              converted into True. Return `None` if value is `None`
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def error_msg_from_exception(ex: Exception) -> str:
    """Translate exception into error message

    Database have different ways to handle exception. This function attempts
    to make sense of the exception object and construct a human readable
    sentence.

    TODO(bkyryliuk): parse the Presto error message from the connection
                     created via create_engine.
    engine = create_engine('presto://localhost:3506/silver') -
      gives an e.message as the str(dict)
    presto.connect('localhost', port=3506, catalog='silver') - as a dict.
    The latter version is parsed correctly by this function.
    """
    msg = ""
    if hasattr(ex, "message"):
        if isinstance(ex.message, dict):
            msg = ex.message.get("message")  # type: ignore
        elif ex.message:
            msg = ex.message
    return str(msg) or str(ex)


def readfile(file_path: str) -> str | None:
    with open(file_path) as f:
        content = f.read()
    return content


def generic_find_constraint_name(
    table: str, columns: set[str], referenced: str, database: SQLAlchemy
) -> str | None:
    """Utility to find a constraint name in alembic migrations"""
    tbl = sa.Table(
        table, database.metadata, autoload=True, autoload_with=database.engine
    )

    for fk in tbl.foreign_key_constraints:
        if fk.referred_table.name == referenced and set(fk.column_keys) == columns:
            return fk.name

    return None


def generic_find_fk_constraint_name(
    table: str, columns: set[str], referenced: str, insp: Inspector
) -> str | None:
    """Utility to find a foreign-key constraint name in alembic migrations"""
    for fk in insp.get_foreign_keys(table):
        if (
            fk["referred_table"] == referenced
            and set(fk["referred_columns"]) == columns
        ):
            return fk["name"]

    return None


def generic_find_fk_constraint_names(  # pylint: disable=invalid-name
    table: str, columns: set[str], referenced: str, insp: Inspector
) -> set[str]:
    """Utility to find foreign-key constraint names in alembic migrations"""
    names = set()

    for fk in insp.get_foreign_keys(table):
        if (
            fk["referred_table"] == referenced
            and set(fk["referred_columns"]) == columns
        ):
            names.add(fk["name"])

    return names


def generic_find_uq_constraint_name(
    table: str, columns: set[str], insp: Inspector
) -> str | None:
    """Utility to find a unique constraint name in alembic migrations"""

    for uq in insp.get_unique_constraints(table):
        if columns == set(uq["column_names"]):
            return uq["name"]

    return None


def get_datasource_full_name(
    database_name: str,
    datasource_name: str,
    catalog: str | None = None,
    schema: str | None = None,
) -> str:
    if not database_name:
        raise SupersetException("database_name cannot be None or empty")
    if not datasource_name:
        raise SupersetException("datasource_name cannot be None or empty")
    parts = [f"[{database_name}]"]
    if catalog:
        parts.append(f"[{catalog}]")
    if schema:
        parts.append(f"[{schema}]")
    parts.append(f"[{datasource_name}]")
    return ".".join(parts)


def pessimistic_connection_handling(some_engine: Engine) -> None:
    @event.listens_for(some_engine, "engine_connect")
    def ping_connection(connection: Connection, branch: bool) -> None:
        if branch:
            # 'branch' refers to a sub-connection of a connection,
            # we don't want to bother pinging on these.
            return

        # turn off 'close with result'.  This flag is only used with
        # 'connectionless' execution, otherwise will be False in any case
        save_should_close_with_result = connection.should_close_with_result
        connection.should_close_with_result = False

        try:
            # run a SELECT 1.   use a core select() so that
            # the SELECT of a scalar value without a table is
            # appropriately formatted for the backend
            connection.scalar(select([1]))
        except exc.DBAPIError as err:
            # catch SQLAlchemy's DBAPIError, which is a wrapper
            # for the DBAPI's exception.  It includes a .connection_invalidated
            # attribute which specifies if this connection is a 'disconnect'
            # condition, which is based on inspection of the original exception
            # by the dialect in use.
            if err.connection_invalidated:
                # run the same SELECT again - the connection will re-validate
                # itself and establish a new connection.  The disconnect detection
                # here also causes the whole connection pool to be invalidated
                # so that all stale connections are discarded.
                connection.scalar(select([1]))
            else:
                raise
        finally:
            # restore 'close with result'
            connection.should_close_with_result = save_should_close_with_result

    if some_engine.dialect.name == "sqlite":

        @event.listens_for(some_engine, "connect")
        def set_sqlite_pragma(  # pylint: disable=unused-argument
            connection: sqlite3.Connection,
            *args: Any,
        ) -> None:
            r"""
            Enable foreign key support for SQLite.

            :param connection: The SQLite connection
            :param \*args: Additional positional arguments
            :see: https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html
            """

            with closing(connection.cursor()) as cursor:
                cursor.execute("PRAGMA foreign_keys=ON")


def choicify(values: Iterable[Any]) -> list[tuple[Any, Any]]:
    """Takes an iterable and makes an iterable of tuples with it"""
    return [(v, v) for v in values]


def zlib_compress(data: bytes | str) -> bytes:
    """
    Compress things in a py2/3 safe fashion
    >>> json_str = '{"test": 1}'
    >>> blob = zlib_compress(json_str)
    """
    if isinstance(data, str):
        return zlib.compress(bytes(data, "utf-8"))
    return zlib.compress(data)


def zlib_decompress(blob: bytes, decode: bool | None = True) -> bytes | str:
    """
    Decompress things to a string in a py2/3 safe fashion
    >>> json_str = '{"test": 1}'
    >>> blob = zlib_compress(json_str)
    >>> got_str = zlib_decompress(blob)
    >>> got_str == json_str
    True
    """
    if isinstance(blob, bytes):
        decompressed = zlib.decompress(blob)
    else:
        decompressed = zlib.decompress(bytes(blob, "utf-8"))
    return decompressed.decode("utf-8") if decode else decompressed


def get_example_default_schema() -> str | None:
    """
    Return the default schema of the examples database, if any.
    """
    database = get_example_database()
    with database.get_sqla_engine() as engine:
        return inspect(engine).default_schema_name


def backend() -> str:
    return get_example_database().backend


def is_adhoc_metric(metric: Metric) -> TypeGuard[AdhocMetric]:
    return isinstance(metric, dict) and "expressionType" in metric


def is_adhoc_column(column: Column) -> TypeGuard[AdhocColumn]:
    return isinstance(column, dict) and ({"label", "sqlExpression"}).issubset(
        column.keys()
    )


def is_base_axis(column: Column) -> bool:
    return is_adhoc_column(column) and column.get("columnType") == "BASE_AXIS"


def get_base_axis_columns(columns: list[Column] | None) -> list[Column]:
    return [column for column in columns or [] if is_base_axis(column)]


def get_non_base_axis_columns(columns: list[Column] | None) -> list[Column]:
    return [column for column in columns or [] if not is_base_axis(column)]


def get_base_axis_labels(columns: list[Column] | None) -> tuple[str, ...]:
    return tuple(get_column_name(column) for column in get_base_axis_columns(columns))


def get_x_axis_label(columns: list[Column] | None) -> str | None:
    labels = get_base_axis_labels(columns)
    return labels[0] if labels else None


def get_column_name(column: Column, verbose_map: dict[str, Any] | None = None) -> str:
    """
    Extract label from column

    :param column: object to extract label from
    :param verbose_map: verbose_map from dataset for optional mapping from
                        raw name to verbose name
    :return: String representation of column
    :raises ValueError: if metric object is invalid
    """
    if hasattr(column, "column_name"):
        column_name = getattr(column, "column_name", "")
        verbose_name = getattr(column, "verbose_name", "")
        return verbose_name or column_name

    if isinstance(column, dict):
        if label := column.get("label"):
            return label
        if expr := column.get("sqlExpression"):
            return expr

    if isinstance(column, str):
        verbose_map = verbose_map or {}
        return verbose_map.get(column, column)

    raise ValueError("Missing label")


def get_metric_name(metric: Metric, verbose_map: dict[str, Any] | None = None) -> str:
    """
    Extract label from metric

    :param metric: object to extract label from
    :param verbose_map: verbose_map from dataset for optional mapping from
                        raw name to verbose name
    :return: String representation of metric
    :raises ValueError: if metric object is invalid
    """
    from flask_babel import gettext as __

    if is_adhoc_metric(metric):
        if label := metric.get("label"):
            return label
        if (expression_type := metric.get("expressionType")) == "SQL":
            if sql_expression := metric.get("sqlExpression"):
                return sql_expression
        if expression_type == "SIMPLE":
            column: AdhocMetricColumn = metric.get("column") or {}
            column_name = column.get("column_name")
            aggregate = metric.get("aggregate")
            if column and aggregate:
                return f"{aggregate}({column_name})"
            if column_name:
                return column_name

    if isinstance(metric, str):
        verbose_map = verbose_map or {}
        return verbose_map.get(metric, metric)

    raise ValueError(__("Invalid metric object: %(metric)s", metric=str(metric)))


def get_column_names(
    columns: Sequence[Column] | None,
    verbose_map: dict[str, Any] | None = None,
) -> list[str]:
    return [
        column
        for column in [get_column_name(column, verbose_map) for column in columns or []]
        if column
    ]


def get_metric_names(
    metrics: Sequence[Metric] | None,
    verbose_map: dict[str, Any] | None = None,
) -> list[str]:
    return [
        metric
        for metric in [get_metric_name(metric, verbose_map) for metric in metrics or []]
        if metric
    ]


def get_first_metric_name(
    metrics: Sequence[Metric] | None,
    verbose_map: dict[str, Any] | None = None,
) -> str | None:
    metric_labels = get_metric_names(metrics, verbose_map)
    return metric_labels[0] if metric_labels else None


def ensure_path_exists(path: str) -> None:
    try:
        os.makedirs(path)
    except OSError as ex:
        if not (os.path.isdir(path) and ex.errno == errno.EEXIST):
            raise


def parse_ssl_cert(certificate: str) -> Certificate:
    """
    Parses the contents of a certificate and returns a valid certificate object
    if valid.

    :param certificate: Contents of certificate file
    :return: Valid certificate instance
    :raises CertificateException: If certificate is not valid/unparseable
    """
    try:
        return load_pem_x509_certificate(certificate.encode("utf-8"), default_backend())
    except ValueError as ex:
        raise CertificateException("Invalid certificate") from ex


def create_ssl_cert_file(certificate: str) -> str:
    """
    This creates a certificate file that can be used to validate HTTPS
    sessions. A certificate is only written to disk once; on subsequent calls,
    only the path of the existing certificate is returned.

    :param certificate: The contents of the certificate
    :return: The path to the certificate file
    :raises CertificateException: If certificate is not valid/unparseable
    """
    import tempfile

    filename = f"{hash_from_str(certificate)}.crt"
    # pylint: disable=import-outside-toplevel

    cert_dir = app.config["SSL_CERT_PATH"]
    path = cert_dir if cert_dir else tempfile.gettempdir()
    path = os.path.join(path, filename)
    if not os.path.exists(path):
        # Validate certificate prior to persisting to temporary directory
        parse_ssl_cert(certificate)
        with open(path, "w") as cert_file:
            cert_file.write(certificate)
    return path


def time_function(
    func: Callable[..., FlaskResponse], *args: Any, **kwargs: Any
) -> tuple[float, Any]:
    """
    Measures the amount of time a function takes to execute in ms

    :param func: The function execution time to measure
    :param args: args to be passed to the function
    :param kwargs: kwargs to be passed to the function
    :return: A tuple with the duration and response from the function
    """
    start = default_timer()
    response = func(*args, **kwargs)
    stop = default_timer()
    return (stop - start) * 1000.0, response


def MediumText() -> Variant:  # pylint:disable=invalid-name  # noqa: N802
    return Text().with_variant(MEDIUMTEXT(), "mysql")


def LongText() -> Variant:  # pylint:disable=invalid-name  # noqa: N802
    return Text().with_variant(LONGTEXT(), "mysql")


def shortid() -> str:
    return f"{uuid.uuid4()}"[-12:]


def get_stacktrace() -> str | None:
    # pylint: disable=import-outside-toplevel

    if app.config["SHOW_STACKTRACE"]:
        return traceback.format_exc()
    return None


def split(
    string: str, delimiter: str = " ", quote: str = '"', escaped_quote: str = r"\""
) -> Iterator[str]:
    """
    A split function that is aware of quotes and parentheses.

    :param string: string to split
    :param delimiter: string defining where to split, usually a comma or space
    :param quote: string, either a single or a double quote
    :param escaped_quote: string representing an escaped quote
    :return: list of strings
    """
    parens = 0
    quotes = False
    i = 0
    for j, character in enumerate(string):
        complete = parens == 0 and not quotes
        if complete and character == delimiter:
            yield string[i:j]
            i = j + len(delimiter)
        elif character == "(":
            parens += 1
        elif character == ")":
            parens -= 1
        elif character == quote:
            if quotes and string[j - len(escaped_quote) + 1 : j + 1] != escaped_quote:
                quotes = False
            elif not quotes:
                quotes = True
    yield string[i:]


T = TypeVar("T")


def as_list(x: T | list[T]) -> list[T]:
    """
    Wrap an object in a list if it's not a list.

    :param x: The object
    :returns: A list wrapping the object if it's not already a list
    """
    return x if isinstance(x, list) else [x]


def get_form_data_token(form_data: dict[str, Any]) -> str:
    """
    Return the token contained within form data or generate a new one.

    :param form_data: chart form data
    :return: original token if predefined, otherwise new uuid4 based token
    """
    return form_data.get("token") or "token_" + uuid.uuid4().hex[:8]


def get_column_name_from_column(column: Column) -> str | None:
    """
    Extract the physical column that a column is referencing. If the column is
    an adhoc column, always returns `None`.

    :param column: Physical and ad-hoc column
    :return: column name if physical column, otherwise None
    """
    if is_adhoc_column(column):
        return None
    return column  # type: ignore


def get_column_names_from_columns(columns: list[Column]) -> list[str]:
    """
    Extract the physical columns that a list of columns are referencing. Ignore
    adhoc columns

    :param columns: Physical and adhoc columns
    :return: column names of all physical columns
    """
    return [col for col in map(get_column_name_from_column, columns) if col]


def get_column_name_from_metric(metric: Metric) -> str | None:
    """
    Extract the column that a metric is referencing. If the metric isn't
    a simple metric, always returns `None`.

    :param metric: Ad-hoc metric
    :return: column name if simple metric, otherwise None
    """
    if is_adhoc_metric(metric):
        metric = cast(AdhocMetric, metric)
        if metric["expressionType"] == AdhocMetricExpressionType.SIMPLE:
            column = metric["column"]
            if column:
                return column["column_name"]
    return None


def get_column_names_from_metrics(metrics: list[Metric]) -> list[str]:
    """
    Extract the columns that a list of metrics are referencing. Excludes all
    SQL metrics.

    :param metrics: Ad-hoc metric
    :return: column name if simple metric, otherwise None
    """
    return [col for col in map(get_column_name_from_metric, metrics) if col]


def map_sql_type_to_inferred_type(sql_type: Optional[str]) -> str:
    """
    Map a SQL type to a type string recognized by pandas' `infer_objects` method.

    If the SQL type is not recognized, the function will return "string" as the
    default type.

    :param sql_type: SQL type to map
    :return: string type recognized by pandas
    """
    if not sql_type:
        return "string"  # If no SQL type is provided, return "string" as default

    # Use regular expressions to check the SQL type. The first match is returned.
    for pattern, inferred_type in TYPE_MAPPING.items():
        if pattern.search(sql_type):
            return inferred_type

    return "string"  # If no match is found, return "string" as default


def get_metric_type_from_column(column: Any, datasource: Explorable) -> str:
    """
    Determine the metric type from a given column in a datasource.

    This function checks if the specified column is a metric in the provided
    datasource. If it is, it extracts the SQL expression associated with the
    metric and attempts to identify the aggregation operation used within
    the expression (e.g., SUM, COUNT, etc.). It then maps the operation to
    a corresponding GenericDataType.

    :param column: The column name or identifier to check.
    :param datasource: The datasource containing metrics to search within.
    :return: The inferred metric type as a string, or an empty string if the
             column is not a metric or no valid operation is found.
    """
    metric = next(
        (m for m in datasource.metrics if m.metric_name == column),
        None,
    )

    if metric is None:
        return ""

    expression: str = metric.expression

    match = re.match(
        r"(SUM|AVG|COUNT|COUNT_DISTINCT|MIN|MAX|FIRST|LAST)\((.*)\)", expression
    )

    if match:
        operation = match.group(1)
        return METRIC_MAP_TYPE.get(operation, "")

    logger.warning("Unexpected metric expression type: %s", expression)
    return ""


def extract_dataframe_dtypes(
    df: pd.DataFrame,
    datasource: Explorable | None = None,
) -> list[GenericDataType]:
    """Serialize pandas/numpy dtypes to generic types"""

    # omitting string types as those will be the default type
    inferred_type_map: dict[str, GenericDataType] = {
        "floating": GenericDataType.NUMERIC,
        "integer": GenericDataType.NUMERIC,
        "mixed-integer-float": GenericDataType.NUMERIC,
        "decimal": GenericDataType.NUMERIC,
        "boolean": GenericDataType.BOOLEAN,
        "datetime64": GenericDataType.TEMPORAL,
        "datetime": GenericDataType.TEMPORAL,
        "date": GenericDataType.TEMPORAL,
    }

    columns_by_name: dict[str, Any] = {}
    if datasource:
        for column in datasource.columns:
            if isinstance(column, dict):
                if column_name := column.get("column_name"):
                    columns_by_name[column_name] = column
            else:
                columns_by_name[column.column_name] = column

    generic_types: list[GenericDataType] = []
    for column in df.columns:
        column_object = columns_by_name.get(str(column))
        series = df[column]
        inferred_type: str = ""
        if series.isna().all():
            sql_type: Optional[str] = ""
            if datasource and hasattr(datasource, "columns_types"):
                if column in datasource.columns_types:
                    sql_type = datasource.columns_types.get(column)
                    inferred_type = map_sql_type_to_inferred_type(sql_type)
                else:
                    inferred_type = get_metric_type_from_column(column, datasource)
        else:
            inferred_type = infer_dtype(series)
        if isinstance(column_object, dict):
            generic_type = (
                GenericDataType.TEMPORAL
                if column_object and column_object.get("is_dttm")
                else inferred_type_map.get(inferred_type, GenericDataType.STRING)
            )
        else:
            generic_type = (
                GenericDataType.TEMPORAL
                if column_object and column_object.is_dttm
                else inferred_type_map.get(inferred_type, GenericDataType.STRING)
            )
        generic_types.append(generic_type)

    return generic_types


def extract_column_dtype(col: ColumnMetadata) -> GenericDataType:
    # Check for temporal type
    if hasattr(col, "is_temporal") and col.is_temporal:
        return GenericDataType.TEMPORAL
    if col.is_dttm:
        return GenericDataType.TEMPORAL

    # Check for numeric type
    if hasattr(col, "is_numeric") and col.is_numeric:
        return GenericDataType.NUMERIC

    # TODO: add check for boolean data type when proper support is added
    return GenericDataType.STRING


def is_test() -> bool:
    return parse_boolean_string(os.environ.get("SUPERSET_TESTENV", "false"))


def get_time_filter_status(
    datasource: Explorable,
    applied_time_extras: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    temporal_columns: set[Any] = {
        col.column_name for col in datasource.columns if col.is_dttm
    }
    applied: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    if time_column := applied_time_extras.get(ExtraFiltersTimeColumnType.TIME_COL):
        if time_column in temporal_columns:
            applied.append({"column": ExtraFiltersTimeColumnType.TIME_COL})
        else:
            rejected.append(
                {
                    "reason": ExtraFiltersReasonType.COL_NOT_IN_DATASOURCE,
                    "column": ExtraFiltersTimeColumnType.TIME_COL,
                }
            )

    if ExtraFiltersTimeColumnType.TIME_GRAIN in applied_time_extras:
        # are there any temporal columns to assign the time grain to?
        if temporal_columns:
            applied.append({"column": ExtraFiltersTimeColumnType.TIME_GRAIN})
        else:
            rejected.append(
                {
                    "reason": ExtraFiltersReasonType.NO_TEMPORAL_COLUMN,
                    "column": ExtraFiltersTimeColumnType.TIME_GRAIN,
                }
            )

    if applied_time_extras.get(ExtraFiltersTimeColumnType.TIME_RANGE):
        # are there any temporal columns to assign the time range to?
        if temporal_columns:
            applied.append({"column": ExtraFiltersTimeColumnType.TIME_RANGE})
        else:
            rejected.append(
                {
                    "reason": ExtraFiltersReasonType.NO_TEMPORAL_COLUMN,
                    "column": ExtraFiltersTimeColumnType.TIME_RANGE,
                }
            )

    return applied, rejected


def format_list(items: Sequence[str], sep: str = ", ", quote: str = '"') -> str:
    quote_escaped = "\\" + quote
    return sep.join(f"{quote}{x.replace(quote, quote_escaped)}{quote}" for x in items)


def find_duplicates(items: Iterable[InputType]) -> list[InputType]:
    """Find duplicate items in an iterable."""
    return [item for item, count in collections.Counter(items).items() if count > 1]


def remove_duplicates(
    items: Iterable[InputType], key: Callable[[InputType], Any] | None = None
) -> list[InputType]:
    """Remove duplicate items in an iterable."""
    if not key:
        return list(dict.fromkeys(items).keys())
    seen = set()
    result = []
    for item in items:
        item_key = key(item)
        if item_key not in seen:
            seen.add(item_key)
            result.append(item)
    return result


@dataclass
class DateColumn:
    col_label: str
    timestamp_format: str | None = None
    offset: int | None = None
    time_shift: str | None = None

    def __hash__(self) -> int:
        return hash(self.col_label)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DateColumn) and hash(self) == hash(other)

    @classmethod
    def get_legacy_time_column(
        cls,
        timestamp_format: str | None,
        offset: int | None,
        time_shift: str | None,
    ) -> DateColumn:
        return cls(
            timestamp_format=timestamp_format,
            offset=offset,
            time_shift=time_shift,
            col_label=DTTM_ALIAS,
        )


def _process_datetime_column(
    df: pd.DataFrame,
    col: DateColumn,
) -> None:
    """Process a single datetime column with format detection."""
    if col.timestamp_format in ("epoch_s", "epoch_ms"):
        dttm_series = df[col.col_label]
        if is_numeric_dtype(dttm_series):
            # Column is formatted as a numeric value
            unit = col.timestamp_format.replace("epoch_", "")
            df[col.col_label] = pd.to_datetime(
                dttm_series,
                utc=False,
                unit=unit,
                origin="unix",
                errors="coerce",
                exact=False,
            )
        else:
            # Column has already been formatted as a timestamp.
            try:
                df[col.col_label] = dttm_series.apply(
                    lambda x: pd.Timestamp(x) if pd.notna(x) else pd.NaT
                )
            except ValueError:
                logger.warning(
                    "Unable to convert column %s to datetime, ignoring",
                    col.col_label,
                )
    else:
        # Try to detect format if not specified
        format_to_use = col.timestamp_format or detect_datetime_format(
            df[col.col_label]
        )

        # Parse with or without format (suppress warning if no format)
        if format_to_use:
            df[col.col_label] = pd.to_datetime(
                df[col.col_label],
                utc=False,
                format=format_to_use,
                errors="coerce",
                exact=False,
            )
        else:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*Could not infer format.*")
                df[col.col_label] = pd.to_datetime(
                    df[col.col_label],
                    utc=False,
                    format=None,
                    errors="coerce",
                    exact=False,
                )


def normalize_dttm_col(
    df: pd.DataFrame,
    dttm_cols: tuple[DateColumn, ...] = tuple(),  # noqa: C408
    format_map: dict[str, str] | None = None,
) -> None:
    """
    Normalize datetime columns in a DataFrame.

    :param df: DataFrame to process
    :param dttm_cols: Tuple of DateColumn objects to process
    :param format_map: Optional mapping of column names to datetime formats.
                       When provided, these pre-detected formats are used instead
                       of runtime detection, improving performance and consistency.
    """
    for _col in dttm_cols:
        if _col.col_label not in df.columns:
            continue

        # Use format from format_map if available and not already set
        if format_map and _col.col_label in format_map and not _col.timestamp_format:
            _col.timestamp_format = format_map[_col.col_label]

        _process_datetime_column(df, _col)

        if _col.offset:
            df[_col.col_label] += timedelta(hours=_col.offset)
        if _col.time_shift is not None:
            df[_col.col_label] += parse_human_timedelta(_col.time_shift)


def parse_boolean_string(bool_str: str | None) -> bool:
    """
    Convert a string representation of a true/false value into a boolean

    >>> parse_boolean_string(None)
    False
    >>> parse_boolean_string('false')
    False
    >>> parse_boolean_string('true')
    True
    >>> parse_boolean_string('False')
    False
    >>> parse_boolean_string('True')
    True
    >>> parse_boolean_string('foo')
    False
    >>> parse_boolean_string('0')
    False
    >>> parse_boolean_string('1')
    True

    :param bool_str: string representation of a value that is assumed to be boolean
    :return: parsed boolean value
    """
    if bool_str is None:
        return False
    return bool_str.lower() in ("y", "Y", "yes", "True", "t", "true", "On", "on", "1")


def apply_max_row_limit(
    limit: int,
    server_pagination: bool | None = None,
) -> int:
    """
    Override row limit based on server pagination setting

    :param limit: requested row limit
    :param server_pagination: whether server-side pagination
    is enabled, defaults to None
    :return: Capped row limit

    >>> apply_max_row_limit(600000, server_pagination=True)  # Server pagination
    500000
    >>> apply_max_row_limit(600000, server_pagination=False)  # No pagination
    50000
    >>> apply_max_row_limit(5000)  # No server_pagination specified
    5000
    >>> apply_max_row_limit(0)  # Zero returns default max limit
    50000
    """
    # pylint: disable=import-outside-toplevel

    max_limit = (
        app.config["TABLE_VIZ_MAX_ROW_SERVER"]
        if server_pagination
        else app.config["SQL_MAX_ROW"]
    )
    if limit != 0:
        return min(max_limit, limit)
    return max_limit


def create_zip(files: dict[str, Any]) -> BytesIO:
    buf = BytesIO()
    with ZipFile(buf, "w") as bundle:
        for filename, contents in files.items():
            with bundle.open(filename, "w") as fp:
                fp.write(contents)
    buf.seek(0)
    return buf


def check_is_safe_zip(zip_file: ZipFile) -> None:
    """
    Checks whether a ZIP file is safe, raises SupersetException if not.

    :param zip_file:
    :return:
    """
    # pylint: disable=import-outside-toplevel

    uncompress_size = 0
    compress_size = 0
    for zip_file_element in zip_file.infolist():
        if zip_file_element.file_size > app.config["ZIPPED_FILE_MAX_SIZE"]:
            raise SupersetException("Found file with size above allowed threshold")
        uncompress_size += zip_file_element.file_size
        compress_size += zip_file_element.compress_size
    compress_ratio = uncompress_size / compress_size
    if compress_ratio > app.config["ZIP_FILE_MAX_COMPRESS_RATIO"]:
        raise SupersetException("Zip compress ratio above allowed threshold")


def to_int(v: Any, value_if_invalid: int = 0) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return value_if_invalid


def get_query_source_from_request() -> QuerySource | None:
    if not request or not request.referrer:
        return None
    if "/superset/dashboard/" in request.referrer:
        return QuerySource.DASHBOARD
    if "/explore/" in request.referrer:
        return QuerySource.CHART
    if "/sqllab/" in request.referrer:
        return QuerySource.SQL_LAB
    return None


def get_user_agent(database: Database, source: QuerySource | None) -> str:
    # pylint: disable=import-outside-toplevel

    source = source or get_query_source_from_request()
    if user_agent_func := app.config["USER_AGENT_FUNC"]:
        return user_agent_func(database, source)

    return DEFAULT_USER_AGENT
