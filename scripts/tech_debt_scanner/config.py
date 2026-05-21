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
"""Configuration for the tech debt scanner pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

REPO = "Andrewstein18/superset-devin-demo"

SCAN_TARGETS_BACKEND: list[str] = [
    "superset/utils/",
    "superset/views/",
    "superset/tasks/",
]

SCAN_TARGETS_FRONTEND: list[str] = [
    "superset-frontend/src/explore/",
    "superset-frontend/src/dashboard/",
]


@dataclass
class ScanCategory:
    """A scanner child agent category."""

    name: str
    tag: str
    labels: list[str]
    description: str
    patterns: list[str]


SCANNER_CATEGORIES: list[ScanCategory] = [
    ScanCategory(
        name="Type Safety",
        tag="scanner-type-safety",
        labels=["tech-debt", "type-safety"],
        description="TypeScript `any` types and Python type suppressions",
        patterns=[
            ": any",
            "# type: ignore",
            "@ts-expect-error",
            "@ts-ignore",
            "eslint-disable.*no-explicit-any",
        ],
    ),
    ScanCategory(
        name="Security",
        tag="scanner-security",
        labels=["tech-debt", "security"],
        description="Bare exception handling, f-string SQL, missing auth checks",
        patterns=[
            "except Exception:",
            "except:",
            '# noqa: S608',
            "TODO.*access control",
        ],
    ),
    ScanCategory(
        name="Dead Code & Stale TODOs",
        tag="scanner-dead-code",
        labels=["tech-debt", "dead-code"],
        description="Deprecated code, POC leftovers, stale TODOs, unused code",
        patterns=[
            "TODO",
            "FIXME",
            "HACK",
            "Deprecated.*Remove",
        ],
    ),
]


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration."""

    repo: str = REPO
    scan_targets_backend: list[str] = field(
        default_factory=lambda: list(SCAN_TARGETS_BACKEND)
    )
    scan_targets_frontend: list[str] = field(
        default_factory=lambda: list(SCAN_TARGETS_FRONTEND)
    )
    scanner_categories: list[ScanCategory] = field(
        default_factory=lambda: list(SCANNER_CATEGORIES)
    )
    max_findings_per_category: int = 30
    max_fix_agents: int = 5
    max_ci_retry_attempts: int = 3
    gather_timeout_seconds: int = 600
