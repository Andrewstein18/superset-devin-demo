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
"""Triage: deduplicate, classify, and assign actions to findings."""

from __future__ import annotations

import logging

from .models import Finding, Severity, TriageResult

logger = logging.getLogger("tech_debt_scanner.triage")

SEVERITY_ORDER = {
    Severity.CRITICAL.value: 0,
    Severity.HIGH.value: 1,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 3,
}


def triage_findings(findings: list[Finding]) -> TriageResult:
    """Deduplicate, classify, and sort findings into action buckets."""
    deduped = deduplicate(findings)

    auto_fixes: list[Finding] = []
    issues_to_file: list[Finding] = []

    for finding in deduped:
        if finding.suggested_fix:
            auto_fixes.append(finding)
        else:
            issues_to_file.append(finding)

    auto_fixes.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))
    issues_to_file.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

    logger.info(
        "Triage: %d auto-fixes, %d issues to file (from %d unique findings)",
        len(auto_fixes),
        len(issues_to_file),
        len(deduped),
    )

    return TriageResult(auto_fixes=auto_fixes, issues_to_file=issues_to_file)


def deduplicate(findings: list[Finding]) -> list[Finding]:
    """Merge findings with same (file, line). Keep highest severity."""
    seen: dict[tuple[str, int], Finding] = {}

    for finding in findings:
        key = (finding.file, finding.line)
        if key in seen:
            existing = seen[key]
            existing_rank = SEVERITY_ORDER.get(existing.severity, 99)
            new_rank = SEVERITY_ORDER.get(finding.severity, 99)
            if new_rank < existing_rank:
                seen[key] = finding
        else:
            seen[key] = finding

    return list(seen.values())


def assign_labels(finding: Finding) -> list[str]:
    """Determine labels for a finding's PR or issue."""
    return finding.get_labels()
