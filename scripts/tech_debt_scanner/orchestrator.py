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
"""Simplified tech debt scanner orchestrator.

Two-stage pipeline that runs fully autonomously:
  Stage 1: Scanner agents (1 per directory) — read code, create .md docs,
           add comments, file GitHub issues, open a docs/comments PR.
  Stage 2: Fixer agents (1 per issue) — fix the issue, open a PR.

Usage:
    python -m scripts.tech_debt_scanner.orchestrator
    python -m scripts.tech_debt_scanner.orchestrator --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tech_debt_scanner")

DEVIN_API = "https://api.devin.ai/v1"
REPO = "Andrewstein18/superset-devin-demo"
REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "reports"

SCAN_DIRS: list[str] = [
    "superset/utils/",
    "superset-frontend/src/explore/",
]

SCANNER_PROMPT = """You are a tech debt scanner for the {repo} repository.

## Scope
Scan ONLY the directory: {directory}

## What to do
1. Read and understand the actual source code in this directory — do not just grep.
2. Find the top 5-10 most important issues:
   - Security: bare `except Exception:`, f-string SQL, missing auth
   - Type safety: `any` types, `# type: ignore`, `@ts-expect-error`
   - Dead code: stale TODOs marked for removal, deprecated code, unused imports
3. For each file you analyze, create a `MODULE_README.md` in the same directory
   documenting what the module does, key functions, and how it connects to others.
4. Add helpful inline comments and docstrings to undocumented functions.
5. Create a GitHub issue for EACH finding with:
   - Title: "[Tech Debt] <brief description>"
   - Labels: tech-debt, automated-cleanup
   - Body: file, line, description, suggested fix
6. Open ONE PR with all your .md files and added comments/docstrings.
   - Title: "docs: add documentation for {directory}"
   - Labels: documentation, automated-cleanup

## Output
Write a summary of what you did to /home/ubuntu/scanner_summary.json:
{{
  "issues_created": [
    {{"number": 1, "url": "...", "title": "...", "severity": "high"}}
  ],
  "pr_url": "...",
  "md_files_created": 3,
  "comments_added": 12,
  "docstrings_added": 8
}}
"""

FIXER_PROMPT = """You are a fixer agent for the {repo} repository.

## Issue to fix
{issue_url}
Title: {issue_title}

## Instructions
1. Read the issue and understand the problem
2. Read the actual source code to understand the context
3. Implement the fix
4. Run `pre-commit run --all-files` before committing
5. Open a PR that fixes this issue
   - Reference the issue in the PR body
   - Labels: tech-debt, automated-cleanup
"""


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_session(
    prompt: str,
    title: str,
    token: str,
    tags: list[str] | None = None,
) -> str | None:
    """Create a Devin session. Returns session_id or None."""
    payload = json.dumps(
        {
            "prompt": prompt,
            "title": title,
            "idempotent": True,
            **({"tags": tags} if tags else {}),
        }
    ).encode()
    req = urllib.request.Request(  # noqa: S310
        f"{DEVIN_API}/sessions",
        data=payload,
        headers=_api_headers(token),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
            return data.get("session_id")
    except urllib.error.HTTPError as exc:
        logger.error("Failed to create session %s: %s", title, exc)
        return None


def wait_for_session(
    session_id: str,
    token: str,
    timeout: int = 1800,
    poll_interval: int = 30,
) -> dict[str, Any]:
    """Poll a session until it finishes. Returns session data."""
    done_states = {"stopped", "error", "finished"}
    start = time.time()

    while time.time() - start < timeout:
        req = urllib.request.Request(  # noqa: S310
            f"{DEVIN_API}/sessions/{session_id}",
            headers=_api_headers(token),
        )
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
                status = data.get("status_enum", "")
                if status in done_states:
                    logger.info(
                        "Session %s finished: %s",
                        session_id[:8],
                        status,
                    )
                    return data
        except urllib.error.HTTPError:
            logger.warning("Error polling %s", session_id[:8])

        time.sleep(poll_interval)

    logger.warning("Session %s timed out", session_id[:8])
    return {}


def run_pipeline(dry_run: bool = False) -> None:
    """Run the full pipeline."""
    token = os.environ.get("DEVIN_API_TOKEN", "")
    if not token:
        logger.error("DEVIN_API_TOKEN not set — cannot run pipeline")
        sys.exit(1)

    agents_spawned = 0
    scanner_results: list[dict[str, Any]] = []
    fixer_prs: list[dict[str, Any]] = []

    # --- Stage 1: Scanner agents (one per directory) ---
    logger.info("=== Stage 1: Spawning scanner agents ===")
    scanner_sessions: list[tuple[str, str]] = []

    for directory in SCAN_DIRS:
        prompt = SCANNER_PROMPT.format(repo=REPO, directory=directory)
        title = f"Scanner: {directory}"
        sid = create_session(
            prompt,
            title,
            token,
            tags=["tech-debt-scanner", "scanner"],
        )
        if sid:
            scanner_sessions.append((sid, directory))
            agents_spawned += 1
            logger.info("Created scanner for %s (%s)", directory, sid[:8])
        else:
            logger.error("Failed to create scanner for %s", directory)

    if not scanner_sessions:
        logger.error("No scanner sessions created — aborting")
        sys.exit(1)

    # Wait for all scanners
    logger.info("Waiting for %d scanner agents...", len(scanner_sessions))
    all_issues: list[dict[str, Any]] = []

    for sid, directory in scanner_sessions:
        result = wait_for_session(sid, token)
        structured = result.get("structured_output", {})
        issues = structured.get("issues_created", [])
        scanner_results.append(
            {
                "directory": directory,
                "session_id": sid,
                "issues_created": len(issues),
                "md_files_created": structured.get("md_files_created", 0),
                "comments_added": structured.get("comments_added", 0),
                "docstrings_added": structured.get("docstrings_added", 0),
                "pr_url": structured.get("pr_url", ""),
            }
        )
        all_issues.extend(issues)
        logger.info(
            "Scanner %s done: %d issues created",
            directory,
            len(issues),
        )

    logger.info("Total issues from scanners: %d", len(all_issues))

    if dry_run:
        logger.info("Dry run — skipping fixer agents")
        _save_results(agents_spawned, all_issues, scanner_results, fixer_prs)
        return

    # --- Stage 2: Fixer agents (one per issue) ---
    if not all_issues:
        logger.info("No issues to fix — done")
        _save_results(agents_spawned, all_issues, scanner_results, fixer_prs)
        return

    logger.info("=== Stage 2: Spawning fixer agents ===")
    for issue in all_issues:
        prompt = FIXER_PROMPT.format(
            repo=REPO,
            issue_url=issue.get("url", ""),
            issue_title=issue.get("title", ""),
        )
        title = f"Fixer: {issue.get('title', 'unknown')[:60]}"
        sid = create_session(
            prompt,
            title,
            token,
            tags=["tech-debt-scanner", "fixer"],
        )
        if sid:
            agents_spawned += 1
            logger.info("Created fixer for issue #%s", issue.get("number"))
            fixer_result = wait_for_session(sid, token)
            fixer_prs.append(
                {
                    "issue_number": issue.get("number"),
                    "issue_title": issue.get("title", ""),
                    "session_id": sid,
                    "status": fixer_result.get("status_enum", "unknown"),
                }
            )
        else:
            logger.error(
                "Failed to create fixer for issue #%s",
                issue.get("number"),
            )

    logger.info("=== Pipeline Complete ===")
    _save_results(agents_spawned, all_issues, scanner_results, fixer_prs)


def _save_results(
    agents_spawned: int,
    issues: list[dict[str, Any]],
    scanner_results: list[dict[str, Any]],
    fixer_prs: list[dict[str, Any]],
) -> None:
    """Save metrics report and dashboard JSON."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_md = sum(s.get("md_files_created", 0) for s in scanner_results)
    total_comments = sum(s.get("comments_added", 0) for s in scanner_results)
    total_docstrings = sum(s.get("docstrings_added", 0) for s in scanner_results)

    metrics = {
        "timestamp": timestamp,
        "repo": REPO,
        "agents_spawned": agents_spawned,
        "total_issues_filed": len(issues),
        "total_prs_created": len(fixer_prs),
        "md_files_created": total_md,
        "comments_added": total_comments,
        "docstrings_added": total_docstrings,
        "scanners": scanner_results,
        "issues": issues,
        "fixer_prs": fixer_prs,
    }

    # Save dashboard JSON
    ts_file = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    data_path = REPORT_DIR / f"dashboard-data-{ts_file}.json"
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    logger.info("Dashboard data saved: %s", data_path)

    # Save markdown report
    report_lines = [
        "# Tech Debt Scanner Report",
        "",
        f"**Repo:** {REPO}",
        f"**Date:** {timestamp}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Agents Spawned | {agents_spawned} |",
        f"| Issues Filed | {len(issues)} |",
        f"| Fix PRs Created | {len(fixer_prs)} |",
        f"| .md Files Created | {total_md} |",
        f"| Comments Added | {total_comments} |",
        f"| Docstrings Added | {total_docstrings} |",
        "",
        "## Scanner Results",
        "",
    ]
    for scanner in scanner_results:
        report_lines.append(f"### {scanner['directory']}")
        report_lines.append(f"- Issues: {scanner['issues_created']}")
        report_lines.append(f"- .md files: {scanner['md_files_created']}")
        report_lines.append(f"- Comments: {scanner['comments_added']}")
        report_lines.append(f"- Docstrings: {scanner['docstrings_added']}")
        if scanner.get("pr_url"):
            report_lines.append(f"- Docs PR: {scanner['pr_url']}")
        report_lines.append("")

    if issues:
        report_lines.append("## Issues Filed")
        report_lines.append("")
        for issue in issues:
            report_lines.append(
                f"- [{issue.get('title', 'Untitled')}]({issue.get('url', '')})"
            )
        report_lines.append("")

    report_path = REPORT_DIR / f"report-{ts_file}.md"
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report_lines))
    logger.info("Report saved: %s", report_path)

    # Print summary
    logger.info(
        "Agents: %d | Issues: %d | PRs: %d | .md: %d",
        agents_spawned,
        len(issues),
        len(fixer_prs),
        total_md,
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run the tech debt scanner pipeline",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan only — no fixer agents",
    )
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
