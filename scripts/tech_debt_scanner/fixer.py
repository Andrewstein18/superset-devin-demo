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
"""Stage 2: Fixer agents — create issues and spawn fixers."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field

from scripts.tech_debt_scanner.config import PipelineConfig
from scripts.tech_debt_scanner.models import Finding, IssueRecord, PRRecord
from scripts.tech_debt_scanner.prompts import build_fixer_prompt

logger = logging.getLogger("tech_debt_scanner.fixer")

DEVIN_API_BASE = "https://api.devin.ai/v1"
GITHUB_API_BASE = "https://api.github.com"


@dataclass
class FixerResult:
    """Results from fixer agents."""

    prs: list[PRRecord] = field(default_factory=list)
    issues: list[IssueRecord] = field(default_factory=list)
    agents_spawned: int = 0


def run_fixers(
    config: PipelineConfig,
    auto_fixes: list[Finding],
    issues_to_file: list[Finding],
) -> FixerResult:
    """Create issues and spawn fixer agents."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    api_token = os.environ.get("DEVIN_API_TOKEN", "")

    result = FixerResult()

    # File GitHub issues for complex findings
    if issues_to_file:
        result.issues = _create_issues(config, issues_to_file, github_token)
        logger.info("Filed %d GitHub issues", len(result.issues))

    # Batch auto-fixes by category and spawn fixer agents
    if not auto_fixes:
        return result

    batches = _batch_findings_by_category(auto_fixes)

    for category, findings in batches.items():
        if not api_token:
            logger.warning("No DEVIN_API_TOKEN — skipping fixer for %s", category)
            result.prs.append(
                _demo_pr_record(category, len(findings)),
            )
            result.agents_spawned += 1
            continue

        findings_json = json.dumps(
            [
                {
                    "file": f.file,
                    "line": f.line,
                    "description": f.description,
                    "suggested_fix": f.suggested_fix,
                }
                for f in findings
            ],
            indent=2,
        )

        labels = findings[0].get_labels()
        prompt = build_fixer_prompt(
            repo=config.repo,
            issue_url="",
            issue_title=f"Fix {category} tech debt",
            issue_body=f"Auto-fix {len(findings)} {category} findings",
            findings_json=findings_json,
            labels=labels,
        )

        session = _create_session(prompt, f"Fixer: {category}", api_token)
        if session:
            result.agents_spawned += 1
            logger.info(
                "Created fixer for %s (session %s)",
                category,
                session["session_id"][:8],
            )

    return result


def _create_issues(
    config: PipelineConfig,
    findings: list[Finding],
    github_token: str,
) -> list[IssueRecord]:
    """Create GitHub Issues for findings that need investigation."""
    records: list[IssueRecord] = []

    if not github_token:
        logger.warning("No GITHUB_TOKEN — generating demo issue records")
        for i, finding in enumerate(findings):
            records.append(
                IssueRecord(
                    issue_number=10 + i,
                    issue_url=f"https://github.com/{config.repo}/issues/{10 + i}",
                    title=finding.description[:80],
                    category=finding.category,
                    labels=finding.get_labels(),
                    severity=finding.severity,
                )
            )
        return records

    for finding in findings:
        labels = finding.get_labels()
        body = (
            f"## Tech Debt Finding\n\n"
            f"**File:** `{finding.file}`\n"
            f"**Line:** {finding.line}\n"
            f"**Category:** {finding.category}\n"
            f"**Severity:** {finding.severity}\n\n"
            f"### Description\n{finding.description}\n\n"
            f"*Filed by Tech Debt Scanner*"
        )

        payload = json.dumps(
            {
                "title": f"[Tech Debt] {finding.description[:80]}",
                "body": body,
                "labels": labels,
            }
        ).encode()

        req = urllib.request.Request(
            f"{GITHUB_API_BASE}/repos/{config.repo}/issues",
            data=payload,
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                records.append(
                    IssueRecord(
                        issue_number=data["number"],
                        issue_url=data["html_url"],
                        title=data["title"],
                        category=finding.category,
                        labels=labels,
                        severity=finding.severity,
                    )
                )
        except Exception:
            logger.exception("Failed to create issue for %s", finding.file)

    return records


def _batch_findings_by_category(
    findings: list[Finding],
) -> dict[str, list[Finding]]:
    """Group findings by category for batched PRs."""
    batches: dict[str, list[Finding]] = {}
    for finding in findings:
        batches.setdefault(finding.category, []).append(finding)
    return batches


def _create_session(prompt: str, title: str, api_token: str) -> dict | None:
    """Create a Devin fixer session."""
    payload = json.dumps(
        {
            "prompt": prompt,
            "title": title,
            "tags": ["tech-debt-scanner", "fixer"],
        }
    ).encode()

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
        logger.exception("Failed to create fixer session: %s", title)
        return None


def _demo_pr_record(category: str, findings_count: int) -> PRRecord:
    """Generate a demo PR record when API is unavailable."""
    pr_titles = {
        "type-safety": "fix: replace any types with proper TypeScript types",
        "security": "fix: replace bare exceptions with specific types",
        "dead-code": "refactor: remove deprecated code and stale TODOs",
    }
    return PRRecord(
        pr_number=5,
        pr_url=f"https://github.com/Andrewstein18/superset-devin-demo/pull/5",
        title=pr_titles.get(category, f"fix: {category} tech debt cleanup"),
        category=category,
        labels=["tech-debt", "automated-cleanup", category],
        findings_addressed=findings_count,
        lines_added=23,
        lines_removed=15,
        ci_attempts=1,
        ci_passed=True,
    )
