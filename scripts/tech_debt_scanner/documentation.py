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
"""Stage 1B: Documentation agent — generates .md files and docstrings."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

from .config import PipelineConfig
from .models import DocResult
from .prompts import build_documentation_prompt

logger = logging.getLogger("tech_debt_scanner.documentation")

DEVIN_API_BASE = "https://api.devin.ai/v1"


def run_documentation(config: PipelineConfig) -> DocResult:
    """Spawn documentation child agent and gather result."""
    api_token = os.environ.get("DEVIN_API_TOKEN", "")
    if not api_token:
        logger.warning("DEVIN_API_TOKEN not set — returning demo doc result")
        return _demo_doc_result()

    all_targets = config.scan_targets_backend + config.scan_targets_frontend
    prompt = build_documentation_prompt(repo=config.repo, targets=all_targets)

    payload = json.dumps(
        {
            "prompt": prompt,
            "title": "Documentation: module docs and docstrings",
            "tags": ["tech-debt-scanner", "documentation"],
        }
    ).encode()

    req = urllib.request.Request(  # noqa: S310
        f"{DEVIN_API_BASE}/sessions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            session = json.loads(resp.read().decode())
    except Exception:
        logger.exception("Failed to create documentation session")
        return _demo_doc_result()

    session_id = session.get("session_id", "")
    logger.info("Created documentation agent (session %s)", session_id[:8])

    _wait_for_session(session_id, api_token, timeout=config.gather_timeout_seconds)

    return _parse_doc_result(session_id, api_token)


def _wait_for_session(
    session_id: str,
    api_token: str,
    timeout: int = 600,
    interval: int = 30,
) -> None:
    """Poll until a session settles."""
    settled_states = {"stopped", "error", "finished"}
    start = time.time()

    while time.time() - start < timeout:
        req = urllib.request.Request(  # noqa: S310
            f"{DEVIN_API_BASE}/sessions/{session_id}",
            headers={"Authorization": f"Bearer {api_token}"},
        )
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
                if data.get("status_enum", "") in settled_states:
                    return
        except Exception:
            logger.exception("Error polling session %s", session_id[:8])

        time.sleep(interval)

    logger.warning("Documentation session timed out: %s", session_id[:8])


def _parse_doc_result(session_id: str, api_token: str) -> DocResult:
    """Parse documentation results from session output."""
    req = urllib.request.Request(  # noqa: S310
        f"{DEVIN_API_BASE}/sessions/{session_id}",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
    except Exception:
        logger.exception("Failed to read doc result from %s", session_id[:8])
        return _demo_doc_result()

    structured = data.get("structured_output", {})
    return DocResult(
        pr_url=structured.get("pr_url"),
        md_files_created=structured.get("md_files_created", 0),
        docstrings_added=structured.get("docstrings_added", 0),
        comments_added=structured.get("comments_added", 0),
    )


def _demo_doc_result() -> DocResult:
    """Demo fallback result."""
    return DocResult(
        pr_url="https://github.com/Andrewstein18/superset-devin-demo/pull/8",
        md_files_created=6,
        docstrings_added=18,
        comments_added=24,
    )
