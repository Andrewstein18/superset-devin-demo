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
"""Create a GitHub issue and trigger a Devin session to work on it.

Usage:
    python scripts/devin_trigger.py \
        --repo Andrewstein18/superset-devin-demo \
        --title "Fix: broken import in utils module" \
        --body "The utils module has a broken import that causes ..." \
        --label bug \
        --label automated

Environment variables:
    GITHUB_TOKEN   - GitHub personal access token (repo scope)
    DEVIN_API_TOKEN - Devin API token for session creation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

GITHUB_API_BASE = "https://api.github.com"
DEVIN_API_BASE = "https://api.devin.ai/v1"


def github_api_request(
    endpoint: str,
    *,
    method: str = "GET",
    token: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the GitHub API."""
    url = f"{GITHUB_API_BASE}{endpoint}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def create_github_issue(
    repo: str,
    title: str,
    body: str,
    labels: list[str],
    token: str,
) -> dict[str, Any]:
    """Create a GitHub issue and return the API response."""
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    return github_api_request(
        f"/repos/{urllib.parse.quote(repo, safe='/')}/issues",
        method="POST",
        token=token,
        data=payload,
    )


def create_devin_session(
    prompt: str,
    api_token: str,
) -> dict[str, Any]:
    """Create a Devin session via the API and return the session info."""
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        f"{DEVIN_API_BASE}/sessions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def build_devin_prompt(
    repo: str,
    issue_url: str,
    issue_title: str,
    issue_body: str,
) -> str:
    """Build a prompt for the Devin session based on the GitHub issue."""
    return (
        f"You are working on the repository {repo}.\n\n"
        f"A GitHub issue has been created that needs your attention:\n\n"
        f"**Issue:** {issue_url}\n"
        f"**Title:** {issue_title}\n\n"
        f"**Description:**\n{issue_body}\n\n"
        f"Your task:\n"
        f"1. Read the issue to understand what needs to be done\n"
        f"2. Search the codebase for relevant files and context\n"
        f"3. Implement the fix or feature described in the issue\n"
        f"4. Run tests and lint checks to verify your changes\n"
        f"5. Create a PR that references the issue "
        f"(Fixes #{issue_url.split('/')[-1]})\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a GitHub issue and trigger a Devin session to work on it"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository in owner/repo format",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Issue title",
    )
    parser.add_argument(
        "--body",
        required=True,
        help="Issue body/description",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Issue label (can be repeated)",
    )
    parser.add_argument(
        "--skip-devin",
        action="store_true",
        help="Only create the issue, do not trigger a Devin session",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making API calls",
    )
    args = parser.parse_args()

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print(
            "Error: GITHUB_TOKEN environment variable is not set",
            file=sys.stderr,
        )
        sys.exit(1)

    devin_token = os.environ.get("DEVIN_API_TOKEN")
    if not args.skip_devin and not devin_token:
        print(
            "Error: DEVIN_API_TOKEN environment variable is not set "
            "(use --skip-devin to only create the issue)",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "action": "dry_run",
                    "repo": args.repo,
                    "issue_title": args.title,
                    "issue_body": args.body,
                    "labels": args.label,
                    "skip_devin": args.skip_devin,
                },
                indent=2,
            )
        )
        return

    # Step 1: Create the GitHub issue
    try:
        issue = create_github_issue(
            repo=args.repo,
            title=args.title,
            body=args.body,
            labels=args.label,
            token=github_token,
        )
    except Exception as exc:
        print(f"Error creating GitHub issue: {exc}", file=sys.stderr)
        sys.exit(1)

    issue_url: str = issue.get("html_url", "")
    issue_number: int = issue.get("number", 0)
    print(f"Created issue #{issue_number}: {issue_url}")

    if args.skip_devin:
        print(json.dumps({"issue_url": issue_url, "issue_number": issue_number}))
        return

    # Step 2: Trigger a Devin session
    assert devin_token is not None
    prompt = build_devin_prompt(
        repo=args.repo,
        issue_url=issue_url,
        issue_title=args.title,
        issue_body=args.body,
    )

    try:
        session = create_devin_session(prompt=prompt, api_token=devin_token)
    except Exception as exc:
        print(f"Error creating Devin session: {exc}", file=sys.stderr)
        print(
            json.dumps(
                {
                    "issue_url": issue_url,
                    "issue_number": issue_number,
                    "devin_session": None,
                    "error": str(exc),
                }
            )
        )
        sys.exit(1)

    session_url = session.get("url", session.get("session_url", "unknown"))
    session_id = session.get("session_id", "unknown")

    print(
        json.dumps(
            {
                "issue_url": issue_url,
                "issue_number": issue_number,
                "devin_session_url": session_url,
                "devin_session_id": session_id,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
