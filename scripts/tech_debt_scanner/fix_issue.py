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
"""Spawn a Devin fixer agent for a single GitHub issue.

Triggered by the tech-debt-fixer workflow when an issue receives the
trigger label. Spawns one Devin agent and waits for it to finish.
Issue closure happens when the PR merges via GitHub's native
``Fixes #N`` mechanism.

Usage:
    python scripts/tech_debt_scanner/fix_issue.py \
        --issue-number 28 \
        --issue-title "Missing null-check in parser" \
        --issue-url "https://github.com/..."
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fix_issue")

DEVIN_API = "https://api.devin.ai/v1"
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.yaml"


def load_config() -> dict[str, Any]:
    """Load configuration from config.yaml, with env-var overrides."""
    defaults: dict[str, Any] = {
        "target_repo": "Andrewstein18/superset-devin-demo",
        "trigger_label": "devin-fix",
    }
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            file_cfg = yaml.safe_load(fh) or {}
            defaults.update(file_cfg)

    defaults["target_repo"] = os.environ.get("TARGET_REPO", defaults["target_repo"])
    defaults["trigger_label"] = os.environ.get(
        "TRIGGER_LABEL", defaults["trigger_label"]
    )
    return defaults


FIXER_PROMPT = """You are a fixer agent for the {repo} repository.

## Issue to fix
{issue_url}
Title: {issue_title}

## Instructions
1. Clone the repo: git clone https://github.com/{repo}.git
2. Read the issue and understand the problem fully
3. Read the source code to understand context — trace call chains
4. Implement the fix on a new branch
5. Open a PR that fixes this issue
   - Reference the issue: "Fixes #{issue_number}"
   - Apply label: automated-fix
   - PR body MUST end with this exact line: <!-- devin-authored: true -->
6. Keep the fix focused and minimal
"""


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_session(prompt: str, title: str, token: str) -> str | None:
    """Create a Devin session. Returns session_id or None."""
    payload = json.dumps(
        {
            "prompt": prompt,
            "title": title,
            "idempotent": True,
            "tags": ["remediation-engine", "fixer", "auto-triggered"],
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
        logger.error("Failed to create session: %s", exc)
        return None


def wait_for_session(session_id: str, token: str, timeout: int = 1800) -> str:
    """Poll session until done. Returns final status."""
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
                    return status
        except urllib.error.HTTPError:
            pass
        time.sleep(30)
    return "timeout"


def add_comment(issue_number: int, session_id: str, repo: str) -> None:
    """Add a comment linking to the Devin session."""
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if not gh_token:
        return

    session_url = f"https://app.devin.ai/sessions/{session_id}"
    body = (
        f"**Devin fixer agent spawned automatically.**\n\n"
        f"Session: {session_url}\n\n"
        f"A fix PR will be created shortly."
    )
    payload = json.dumps({"body": body}).encode()
    req = urllib.request.Request(  # noqa: S310
        f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
        data=payload,
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req)  # noqa: S310
        logger.info("Added comment to issue #%d", issue_number)
    except urllib.error.HTTPError as exc:
        logger.error("Failed to comment on issue #%d: %s", issue_number, exc)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Spawn a Devin fixer agent for a GitHub issue"
    )
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--issue-title", type=str, required=True)
    parser.add_argument("--issue-url", type=str, required=True)
    args = parser.parse_args()

    token = os.environ.get("DEVIN_API_TOKEN", "")
    if not token:
        logger.error("DEVIN_API_TOKEN not set")
        sys.exit(1)

    cfg = load_config()
    repo = cfg["target_repo"]

    logger.info("Spawning fixer for issue #%d: %s", args.issue_number, args.issue_title)

    prompt = FIXER_PROMPT.format(
        repo=repo,
        issue_url=args.issue_url,
        issue_title=args.issue_title,
        issue_number=args.issue_number,
    )
    title = f"Fixer: {args.issue_title[:60]}"

    session_id = create_session(prompt, title, token)
    if not session_id:
        logger.error("Failed to create fixer session")
        sys.exit(1)

    logger.info("Fixer session created: %s", session_id)
    add_comment(args.issue_number, session_id, repo)

    status = wait_for_session(session_id, token)
    logger.info("Fixer finished with status: %s", status)

    if status in ("stopped", "finished"):
        logger.info("Fixer completed — issue closes when PR merges")
    else:
        logger.warning("Fixer did not complete (status=%s)", status)


if __name__ == "__main__":
    main()
