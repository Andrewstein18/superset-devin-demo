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
"""Data models for the tech debt scanner pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionType(str, Enum):
    AUTO_FIX_PR = "auto-fix-pr"
    FILE_ISSUE = "file-issue"


@dataclass
class Finding:
    """A single tech debt finding from a scanner agent."""

    file: str
    line: int
    category: str
    severity: str
    description: str
    suggested_fix: str | None = None

    def get_action(self) -> ActionType:
        """Determine action: auto-fix if there is a suggested fix, else file issue."""
        if self.suggested_fix:
            return ActionType.AUTO_FIX_PR
        return ActionType.FILE_ISSUE

    def get_labels(self) -> list[str]:
        """Generate PR/issue labels for this finding."""
        labels = ["tech-debt", "automated-cleanup"]
        if self.category == "type-safety":
            labels.append("type-safety")
        elif self.category == "security":
            labels.append("security")
        elif self.category == "dead-code":
            labels.append("dead-code")
        return labels


@dataclass
class PRRecord:
    """Record of a PR created by the pipeline."""

    pr_number: int
    pr_url: str
    title: str
    category: str
    labels: list[str]
    findings_addressed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    comments_added: int = 0
    docstrings_added: int = 0
    md_files_created: int = 0
    ci_attempts: int = 0
    ci_passed: bool = False


@dataclass
class IssueRecord:
    """Record of a GitHub Issue filed by the pipeline."""

    issue_number: int
    issue_url: str
    title: str
    category: str
    labels: list[str]
    severity: str


@dataclass
class DocResult:
    """Result from the documentation agent."""

    pr_url: str | None = None
    md_files_created: int = 0
    docstrings_added: int = 0
    comments_added: int = 0


@dataclass
class TriageResult:
    """Output of the triage stage."""

    auto_fixes: list[Finding] = field(default_factory=list)
    issues_to_file: list[Finding] = field(default_factory=list)


@dataclass
class PipelineMetrics:
    """Metrics collected across the entire pipeline run."""

    files_scanned: int = 0
    lines_scanned: int = 0
    total_findings: int = 0
    findings_by_category: dict[str, int] = field(default_factory=dict)
    findings_by_severity: dict[str, int] = field(default_factory=dict)

    auto_fix_count: int = 0
    issue_filed_count: int = 0

    total_prs_created: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    total_comments_added: int = 0
    total_docstrings_added: int = 0
    total_md_files_created: int = 0
    ci_pass_rate: float = 0.0
    avg_ci_attempts: float = 0.0

    avg_findings_per_pr: float = 0.0
    avg_lines_changed_per_pr: float = 0.0

    total_agents_spawned: int = 0

    prs: list[PRRecord] = field(default_factory=list)
    issues: list[IssueRecord] = field(default_factory=list)

    bugs_found: int = 0
    tech_debt_found: int = 0

    def compute_averages(self) -> None:
        """Compute per-PR averages from collected records."""
        if self.total_prs_created > 0:
            self.avg_findings_per_pr = self.auto_fix_count / self.total_prs_created
            self.avg_lines_changed_per_pr = (
                self.total_lines_added + self.total_lines_removed
            ) / self.total_prs_created

        ci_attempts = [pr.ci_attempts for pr in self.prs]
        ci_passes = [pr.ci_passed for pr in self.prs]
        if ci_attempts:
            self.avg_ci_attempts = sum(ci_attempts) / len(ci_attempts)
        if ci_passes:
            self.ci_pass_rate = sum(1 for p in ci_passes if p) / len(ci_passes)
