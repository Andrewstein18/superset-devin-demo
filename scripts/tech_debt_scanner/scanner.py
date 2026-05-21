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
"""Stage 1A: Scanner agents — fan out child Devins to scan for tech debt."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field

from scripts.tech_debt_scanner.config import PipelineConfig
from scripts.tech_debt_scanner.models import Finding
from scripts.tech_debt_scanner.prompts import (
    SCANNER_OUTPUT_SCHEMA,
    build_scanner_prompt,
)

logger = logging.getLogger("tech_debt_scanner.scanner")

DEVIN_API_BASE = "https://api.devin.ai/v1"


@dataclass
class ScannerResult:
    """Results from all scanner children."""

    findings: list[Finding] = field(default_factory=list)
    agents_spawned: int = 0
    session_ids: list[str] = field(default_factory=list)


def run_scanners(config: PipelineConfig) -> ScannerResult:
    """Fan out scanner child agents and gather results."""
    api_token = os.environ.get("DEVIN_API_TOKEN", "")
    if not api_token:
        logger.warning("DEVIN_API_TOKEN not set — running in demo mode")
        return _demo_scanner_result(config)

    result = ScannerResult()

    for category in config.scanner_categories:
        prompt = build_scanner_prompt(
            category_name=category.name,
            category_description=category.description,
            patterns=category.patterns,
            repo=config.repo,
            targets_backend=config.scan_targets_backend,
            targets_frontend=config.scan_targets_frontend,
            max_findings=config.max_findings_per_category,
        )

        session = _create_session(
            prompt=prompt,
            title=f"Scanner: {category.name}",
            tags=["tech-debt-scanner", category.tag],
            api_token=api_token,
        )

        if session:
            result.session_ids.append(session["session_id"])
            result.agents_spawned += 1
            logger.info(
                "Created scanner: %s (session %s)",
                category.name,
                session["session_id"][:8],
            )

    if result.session_ids:
        logger.info("Waiting for %d scanner agents...", len(result.session_ids))
        settled = _poll_sessions(
            result.session_ids,
            api_token,
            timeout=config.gather_timeout_seconds,
        )

        for session_data, category in zip(settled, config.scanner_categories):
            findings = _extract_findings(session_data, category.tag)
            result.findings.extend(findings)

    logger.info("Total scanner findings: %d", len(result.findings))
    return result


def _create_session(
    prompt: str,
    title: str,
    tags: list[str],
    api_token: str,
) -> dict | None:
    """Create a Devin session via the API."""
    payload = json.dumps({"prompt": prompt, "title": title, "tags": tags}).encode()
    req = urllib.request.Request(
        f"{DEVIN_API_BASE}/sessions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        logger.exception("Failed to create session: %s", title)
        return None


def _poll_sessions(
    session_ids: list[str],
    api_token: str,
    timeout: int = 600,
    interval: int = 30,
) -> list[dict]:
    """Poll sessions until all settle or timeout."""
    settled_states = {"stopped", "error", "finished"}
    start = time.time()
    results: dict[str, dict] = {}

    while time.time() - start < timeout:
        all_settled = True
        for sid in session_ids:
            if sid in results:
                continue
            status = _get_session_status(sid, api_token)
            if status and status.get("status_enum", "") in settled_states:
                results[sid] = status
            else:
                all_settled = False

        if all_settled:
            break
        time.sleep(interval)

    return [results.get(sid, {}) for sid in session_ids]


def _get_session_status(session_id: str, api_token: str) -> dict | None:
    """Get session status from the API."""
    req = urllib.request.Request(
        f"{DEVIN_API_BASE}/sessions/{session_id}",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        logger.exception("Failed to get session status: %s", session_id[:8])
        return None


def _extract_findings(session_data: dict, category_tag: str) -> list[Finding]:
    """Extract findings from a session's structured output."""
    structured = session_data.get("structured_output", {})
    if not structured:
        return []

    raw_findings = structured.get("findings", [])
    return _parse_findings(raw_findings, category_tag)


def _parse_findings(raw_findings: list[dict], category: str) -> list[Finding]:
    """Parse raw JSON findings into Finding objects."""
    findings = []
    for raw in raw_findings:
        findings.append(
            Finding(
                file=raw.get("file", ""),
                line=raw.get("line", 0),
                category=raw.get("category", category),
                severity=raw.get("severity", "medium"),
                description=raw.get("description", ""),
                suggested_fix=raw.get("suggested_fix"),
            )
        )
    return findings


def _demo_scanner_result(config: PipelineConfig) -> ScannerResult:
    """Generate demo scanner results when API is unavailable."""
    findings = [
        Finding(
            file="superset/utils/core.py",
            line=245,
            category="security",
            severity="high",
            description="Bare except Exception: swallows errors silently",
            suggested_fix="Replace with specific exception type",
        ),
        Finding(
            file="superset/utils/rls.py",
            line=183,
            category="security",
            severity="critical",
            description="RLS parse failure silently returns empty list — may expose data",
            suggested_fix=None,
        ),
        Finding(
            file="superset/utils/encrypt.py",
            line=176,
            category="security",
            severity="high",
            description="f-string SQL query flagged with noqa: S608",
            suggested_fix=None,
        ),
        Finding(
            file="superset-frontend/src/explore/store.ts",
            line=161,
            category="type-safety",
            severity="medium",
            description="5 eslint-disable @typescript-eslint/no-explicit-any",
            suggested_fix="Replace any with proper TypeScript types",
        ),
        Finding(
            file="superset-frontend/src/dashboard/components/nativeFilters/selectors.ts",
            line=144,
            category="type-safety",
            severity="medium",
            description="chart: any parameter — no compile-time safety",
            suggested_fix="Define ChartState interface and use it",
        ),
        Finding(
            file="superset/tasks/scheduler.py",
            line=35,
            category="dead-code",
            severity="low",
            description="3x TODO: Deprecated: Remove support in 6.0",
            suggested_fix="Delete deprecated code paths",
        ),
        Finding(
            file="superset/views/alerts.py",
            line=42,
            category="security",
            severity="high",
            description="TODO: access control rules for this module",
            suggested_fix=None,
        ),
        Finding(
            file="superset/utils/database.py",
            line=28,
            category="dead-code",
            severity="medium",
            description="TODO: duplicate code with DatabaseDao",
            suggested_fix=None,
        ),
    ]
    return ScannerResult(
        findings=findings,
        agents_spawned=3,
        session_ids=["demo-type-safety", "demo-security", "demo-dead-code"],
    )
