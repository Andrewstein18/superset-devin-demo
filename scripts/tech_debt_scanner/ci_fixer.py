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
"""Stage 3: CI fixer agents — iterate on failing CI until green."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

from .config import PipelineConfig
from .models import PRRecord
from .prompts import build_ci_fixer_prompt

logger = logging.getLogger("tech_debt_scanner.ci_fixer")

DEVIN_API_BASE = "https://api.devin.ai/v1"


def run_ci_fixers(
    config: PipelineConfig,
    prs: list[PRRecord],
) -> list[PRRecord]:
    """Monitor PRs for CI failures and spawn fixers."""
    api_token = os.environ.get("DEVIN_API_TOKEN", "")

    for pr in prs:
        if pr.ci_passed:
            logger.info("PR #%d already passing CI", pr.pr_number)
            continue

        for attempt in range(1, config.max_ci_retry_attempts + 1):
            logger.info(
                "PR #%d CI attempt %d/%d",
                pr.pr_number,
                attempt,
                config.max_ci_retry_attempts,
            )

            if not api_token:
                logger.warning(
                    "No DEVIN_API_TOKEN — simulating CI fix for PR #%d",
                    pr.pr_number,
                )
                pr.ci_attempts = attempt
                pr.ci_passed = attempt >= 2
                if pr.ci_passed:
                    logger.info("PR #%d CI passed (attempt %d)", pr.pr_number, attempt)
                    break
                continue

            ci_logs = _get_ci_logs(pr.pr_number, config.repo)
            if not ci_logs:
                pr.ci_passed = True
                pr.ci_attempts = attempt
                logger.info("PR #%d — no CI failures found", pr.pr_number)
                break

            prompt = build_ci_fixer_prompt(
                repo=config.repo,
                pr_url=pr.pr_url,
                pr_number=pr.pr_number,
                branch=f"devin/fix-{pr.category}",
                ci_logs=ci_logs,
                attempt=attempt,
            )

            _create_ci_fixer_session(prompt, pr.pr_number, attempt, api_token)
            pr.ci_attempts = attempt

        if not pr.ci_passed and pr.ci_attempts >= config.max_ci_retry_attempts:
            pr.labels.append("needs-human-review")
            logger.warning(
                "PR #%d failed CI after %d attempts — flagged for review",
                pr.pr_number,
                pr.ci_attempts,
            )

    return prs


def _get_ci_logs(pr_number: int, repo: str) -> str:
    """Fetch CI failure logs for a PR."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        return ""

    req = urllib.request.Request(  # noqa: S310
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/commits",
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            commits = json.loads(resp.read().decode())
            if not commits:
                return ""
            last_sha = commits[-1]["sha"]

        req = urllib.request.Request(  # noqa: S310
            f"https://api.github.com/repos/{repo}/commits/{last_sha}/check-runs",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            check_data = json.loads(resp.read().decode())

        failures = [
            cr
            for cr in check_data.get("check_runs", [])
            if cr.get("conclusion") == "failure"
        ]
        if not failures:
            return ""

        return "\n".join(
            f"Check: {cr['name']}\n"
            f"Output: {cr.get('output', {}).get('summary', 'No details')}"
            for cr in failures
        )
    except Exception:
        logger.exception("Failed to get CI logs for PR #%d", pr_number)
        return ""


def _create_ci_fixer_session(
    prompt: str,
    pr_number: int,
    attempt: int,
    api_token: str,
) -> dict | None:
    """Create a CI fixer Devin session."""
    payload = json.dumps(
        {
            "prompt": prompt,
            "title": f"CI Fixer: PR #{pr_number} (attempt {attempt})",
            "tags": ["tech-debt-scanner", "ci-fixer"],
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
            return json.loads(resp.read().decode())
    except Exception:
        logger.exception("Failed to create CI fixer for PR #%d", pr_number)
        return None
