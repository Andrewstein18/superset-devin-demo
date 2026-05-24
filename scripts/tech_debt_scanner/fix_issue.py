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

Triggered by the tech-debt-fixer workflow when an issue with the
'tech-debt' label is created. Spawns one Devin agent, waits for it
to finish, then closes the issue.

Usage:
    python scripts/tech_debt_scanner/fix_issue.py \
        --issue-number 28 \
        --issue-title "[Tech Debt] Missing null-check" \
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fix_issue")

DEVIN_API = "https://api.devin.ai/v1"
REPO = "Andrewstein18/superset-devin-demo"

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
   - Labels: tech-debt, automated-cleanup
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
            "tags": ["tech-debt-scanner", "fixer", "auto-triggered"],
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


def close_issue(issue_number: int, token: str) -> None:
    """Close the GitHub issue after the fixer agent is done."""
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if not gh_token:
        logger.warning("GITHUB_TOKEN not set — cannot close issue")
        return

    payload = json.dumps({"state": "closed"}).encode()
    req = urllib.request.Request(  # noqa: S310
        f"https://api.github.com/repos/{REPO}/issues/{issue_number}",
        data=payload,
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            if resp.status == 200:
                logger.info("Closed issue #%d", issue_number)
    except urllib.error.HTTPError as exc:
        logger.error("Failed to close issue #%d: %s", issue_number, exc)


def add_comment(issue_number: int, session_id: str) -> None:
    """Add a comment linking to the Devin session."""
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if not gh_token:
        return

    session_url = f"https://app.devin.ai/sessions/{session_id}"
    body = (
        f"🤖 **Devin fixer agent spawned automatically.**\n\n"
        f"Session: {session_url}\n\n"
        f"A fix PR will be created shortly."
    )
    payload = json.dumps({"body": body}).encode()
    req = urllib.request.Request(  # noqa: S310
        f"https://api.github.com/repos/{REPO}/issues/{issue_number}/comments",
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
    parser = argparse.ArgumentParser(description="Spawn a Devin fixer for an issue")
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--issue-title", type=str, required=True)
    parser.add_argument("--issue-url", type=str, required=True)
    args = parser.parse_args()

    token = os.environ.get("DEVIN_API_TOKEN", "")
    if not token:
        logger.error("DEVIN_API_TOKEN not set")
        sys.exit(1)

    logger.info("Spawning fixer for issue #%d: %s", args.issue_number, args.issue_title)

    prompt = FIXER_PROMPT.format(
        repo=REPO,
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
    add_comment(args.issue_number, session_id)

    status = wait_for_session(session_id, token)
    logger.info("Fixer finished with status: %s", status)

    if status in ("stopped", "finished"):
        close_issue(args.issue_number, token)
        logger.info("Issue #%d closed", args.issue_number)
    else:
        logger.warning(
            "Fixer did not complete successfully (status=%s) — issue left open",
            status,
        )


if __name__ == "__main__":
    main()
