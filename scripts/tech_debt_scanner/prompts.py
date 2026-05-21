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
"""Prompt templates for child Devin agents."""

from __future__ import annotations


def build_scanner_prompt(
    category_name: str,
    category_description: str,
    patterns: list[str],
    repo: str,
    targets_backend: list[str],
    targets_frontend: list[str],
    max_findings: int,
) -> str:
    """Build the prompt for a scanner child agent."""
    targets = ", ".join(targets_backend + targets_frontend)
    pattern_list = "\n".join(f"  - `{p}`" for p in patterns)

    return f"""You are a tech debt scanner agent for the {repo} repository.

## Your Task
Scan the following directories for **{category_name}** issues:
{targets}

## What to Look For
{category_description}

Search patterns:
{pattern_list}

## Instructions
1. Use grep/ripgrep to find occurrences of the patterns above in the target directories
2. For each finding, analyze the surrounding code context to understand severity
3. Where possible, suggest a concrete fix
4. You CAN spawn sub-agents if you want to parallelize scanning across directories
5. Limit your output to the top {max_findings} most important findings

## Output Format
Write your findings as JSON to a file called `/home/ubuntu/scanner_output.json`:

```json
{{
  "findings": [
    {{
      "file": "superset/utils/core.py",
      "line": 42,
      "category": "{category_name.lower().replace(" ", "-")}",
      "severity": "high",
      "description": "Brief description of the issue",
      "suggested_fix": "How to fix it (or null if complex)"
    }}
  ]
}}
```

Severity levels: critical, high, medium, low
- critical: Security vulnerabilities, data exposure risks
- high: Bugs likely to cause runtime errors, silent failures
- medium: Type safety issues, lint suppressions, code quality
- low: Style issues, TODOs, minor cleanup

Do NOT create any PRs or issues. Only scan and output findings.
"""


def build_documentation_prompt(
    repo: str,
    targets: list[str],
) -> str:
    """Build the prompt for the documentation child agent."""
    target_list = ", ".join(targets)

    return f"""You are a documentation agent for the {repo} repository.

## Your Task
Generate documentation for the following directories:
{target_list}

## Instructions
1. For each module/directory, create a `.md` README file that documents:
   - What the module does (purpose)
   - Key classes and functions (with signatures)
   - How it connects to other modules
   - Any important caveats or patterns

2. Add docstrings to undocumented public functions and classes

3. Improve existing inline comments where they are unclear

4. You CAN spawn sub-agents to parallelize documentation across modules

5. Open a single PR with all documentation changes
   - Title: "docs: add module documentation and docstrings"
   - Labels: documentation, automated-cleanup

## Guidelines
- Write documentation that is useful for AI agents (Claude, Devin, GPT)
- Use structured markdown with clear headings
- Include code examples where helpful
- Keep docstrings concise but informative (Google style)
- Follow Apache license header format for new files
"""


def build_fixer_prompt(
    repo: str,
    issue_url: str,
    issue_title: str,
    issue_body: str,
    findings_json: str,
    labels: list[str],
) -> str:
    """Build the prompt for a fixer child agent."""
    label_str = ", ".join(labels)

    return f"""You are a fixer agent for the {repo} repository.

## Issue
Title: {issue_title}
URL: {issue_url}

## Description
{issue_body}

## Findings to Fix
{findings_json}

## Instructions
1. Read the findings and understand the context
2. Implement fixes for each finding
3. You CAN spawn sub-agents if the fix spans many files or modules
4. Run `pre-commit run --all-files` before committing
5. Open a PR with:
   - A descriptive title summarizing the fixes
   - Labels: {label_str}
   - Reference the issue in the PR body

## Guidelines
- Follow existing code conventions
- Add type hints to any new Python code
- NO `any` types in TypeScript
- Run pre-commit hooks before pushing
"""


def build_ci_fixer_prompt(
    repo: str,
    pr_url: str,
    pr_number: int,
    branch: str,
    ci_logs: str,
    attempt: int,
) -> str:
    """Build the prompt for a CI fixer child agent."""
    return f"""You are a CI fixer agent for the {repo} repository.

## PR
PR #{pr_number}: {pr_url}
Branch: {branch}
Attempt: {attempt}

## CI Failure Logs
{ci_logs}

## Instructions
1. Analyze the CI failure logs above
2. Identify the root cause of each failure
3. Fix the issues (lint errors, type errors, test failures)
4. Push fixes to the branch `{branch}`
5. Do NOT create a new PR — push to the existing branch

## Guidelines
- Run `pre-commit run --all-files` before pushing
- If tests fail, fix the tests or the code — do not skip tests
- If lint/type errors, fix the code — do not add suppressions
"""


SCANNER_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "category": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                    },
                    "description": {"type": "string"},
                    "suggested_fix": {
                        "type": ["string", "null"],
                    },
                },
                "required": [
                    "file",
                    "line",
                    "category",
                    "severity",
                    "description",
                ],
            },
        },
    },
    "required": ["findings"],
}
