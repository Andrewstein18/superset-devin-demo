#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from flask import current_app as app
from sqlalchemy.sql import compiler

from superset.constants import EXAMPLES_DB_UUID

if TYPE_CHECKING:
    from superset.connectors.sqla.models import Database

logging.getLogger("MARKDOWN").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def get_or_create_db(
    database_name: str, sqlalchemy_uri: str, always_create: bool | None = True
) -> Database:
    # pylint: disable=import-outside-toplevel
    from superset import db
    from superset.daos.database import DatabaseDAO
    from superset.models import core as models

    database = DatabaseDAO.get_database_by_name(database_name)

    # databases with a fixed UUID
    uuids = {
        "examples": EXAMPLES_DB_UUID,
    }

    if not database and always_create:
        logger.info("Creating database reference for %s", database_name)
        database = models.Database(
            database_name=database_name, uuid=uuids.get(database_name)
        )
        db.session.add(database)
        database.set_sqlalchemy_uri(sqlalchemy_uri)

    _sync_database_uri(database, sqlalchemy_uri)

    db.session.flush()

    if database is None:
        raise ValueError(
            f"Database '{database_name}' not found and creation was skipped"
        )

    return database


def _sync_database_uri(database: Database | None, sqlalchemy_uri: str) -> None:
    """Update the database URI if it differs from the expected value."""
    if database and database.sqlalchemy_uri_decrypted != sqlalchemy_uri:
        database.set_sqlalchemy_uri(sqlalchemy_uri)


def get_example_database() -> Database:
    # pylint: disable=import-outside-toplevel

    return get_or_create_db("examples", app.config["SQLALCHEMY_EXAMPLES_URI"])


def get_main_database() -> Database:
    # pylint: disable=import-outside-toplevel

    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    return get_or_create_db("main", db_uri)


def apply_mariadb_ddl_fix() -> None:
    """
    Fix MariaDB "NO CYCLE" syntax issue - MariaDB uses "NOCYCLE" (no space).

    This fix will be included in SQLAlchemy v2.1.0.
    See: https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_1_0b1/lib/sqlalchemy/dialects/mysql/_mariadb_shim.py
    """
    original_visit_create_sequence = compiler.DDLCompiler.visit_create_sequence

    def patched_visit_create_sequence(self: Any, create: Any, **kw: Any) -> str:
        text = original_visit_create_sequence(self, create, **kw)
        dialect_name = getattr(self.dialect, "name", "") or ""
        if "mariadb" in dialect_name.lower():
            return text.replace("NO CYCLE", "NOCYCLE")
        return text

    compiler.DDLCompiler.visit_create_sequence = patched_visit_create_sequence
