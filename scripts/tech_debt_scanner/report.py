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
"""Metrics aggregation and summary report generation."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts.tech_debt_scanner.config import PipelineConfig
from scripts.tech_debt_scanner.models import (
    DocResult,
    Finding,
    IssueRecord,
    PipelineMetrics,
    PRRecord,
    TriageResult,
)

logger = logging.getLogger("tech_debt_scanner.report")


def collect_metrics(
    scanner_findings: list[Finding],
    doc_result: DocResult | None,
    triage_result: TriageResult,
    prs: list[PRRecord],
    issues: list[IssueRecord],
    agents_spawned: int,
) -> PipelineMetrics:
    """Aggregate metrics from all pipeline stages."""
    category_counts = Counter(f.category for f in scanner_findings)
    severity_counts = Counter(f.severity for f in scanner_findings)

    bugs_found = category_counts.get("security", 0)
    tech_debt_found = sum(
        v for k, v in category_counts.items() if k != "security"
    )

    total_lines_added = sum(pr.lines_added for pr in prs)
    total_lines_removed = sum(pr.lines_removed for pr in prs)
    total_comments = sum(pr.comments_added for pr in prs)
    total_docstrings = sum(pr.docstrings_added for pr in prs)
    total_md = sum(pr.md_files_created for pr in prs)

    if doc_result:
        total_comments += doc_result.comments_added
        total_docstrings += doc_result.docstrings_added
        total_md += doc_result.md_files_created

    metrics = PipelineMetrics(
        total_findings=len(scanner_findings),
        findings_by_category=dict(category_counts),
        findings_by_severity=dict(severity_counts),
        auto_fix_count=len(triage_result.auto_fixes),
        issue_filed_count=len(issues),
        total_prs_created=len(prs),
        total_lines_added=total_lines_added,
        total_lines_removed=total_lines_removed,
        total_comments_added=total_comments,
        total_docstrings_added=total_docstrings,
        total_md_files_created=total_md,
        total_agents_spawned=agents_spawned,
        prs=prs,
        issues=issues,
        bugs_found=bugs_found,
        tech_debt_found=tech_debt_found,
    )

    metrics.compute_averages()
    return metrics


def generate_report(metrics: PipelineMetrics, config: PipelineConfig) -> str:
    """Generate markdown summary report."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Tech Debt Scanner Report",
        f"",
        f"**Repo:** {config.repo}",
        f"**Date:** {timestamp}",
        f"",
        f"---",
        f"",
        f"## Key Metrics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Findings | {metrics.total_findings} |",
        f"| Bugs Found | {metrics.bugs_found} |",
        f"| Tech Debt Found | {metrics.tech_debt_found} |",
        f"| PRs Created | {metrics.total_prs_created} |",
        f"| Issues Filed | {metrics.issue_filed_count} |",
        f"| Lines Added | +{metrics.total_lines_added} |",
        f"| Lines Removed | -{metrics.total_lines_removed} |",
        f"| Comments Written | {metrics.total_comments_added} |",
        f"| Docstrings Added | {metrics.total_docstrings_added} |",
        f"| .md Files Created | {metrics.total_md_files_created} |",
        f"| Agents Spawned | {metrics.total_agents_spawned} |",
        f"| CI Pass Rate | {metrics.ci_pass_rate:.0%} |",
        f"",
        f"## Findings by Category",
        f"",
        f"| Category | Count |",
        f"|----------|-------|",
    ]

    for cat, count in sorted(metrics.findings_by_category.items()):
        lines.append(f"| {cat} | {count} |")

    lines.extend([
        f"",
        f"## Findings by Severity",
        f"",
        f"| Severity | Count |",
        f"|----------|-------|",
    ])

    for sev, count in sorted(metrics.findings_by_severity.items()):
        lines.append(f"| {sev} | {count} |")

    if metrics.prs:
        lines.extend([
            f"",
            f"## Pull Requests",
            f"",
            f"| PR | Title | Category | Findings | Lines | CI |",
            f"|---|-------|----------|----------|-------|----|",
        ])
        for pr in metrics.prs:
            ci_status = (
                f"Passed ({pr.ci_attempts} attempt{'s' if pr.ci_attempts != 1 else ''})"
                if pr.ci_passed
                else f"Failed ({pr.ci_attempts} attempts)"
            )
            lines.append(
                f"| [#{pr.pr_number}]({pr.pr_url}) | {pr.title} | {pr.category} | "
                f"{pr.findings_addressed} | +{pr.lines_added}/-{pr.lines_removed} | {ci_status} |"
            )

    if metrics.issues:
        lines.extend([
            f"",
            f"## Issues Filed",
            f"",
            f"| Issue | Title | Severity | Category |",
            f"|-------|-------|----------|----------|",
        ])
        for issue in metrics.issues:
            lines.append(
                f"| [#{issue.issue_number}]({issue.issue_url}) | {issue.title} | "
                f"{issue.severity} | {issue.category} |"
            )

    lines.extend([
        f"",
        f"## Per-PR Averages",
        f"",
        f"| Metric | Average |",
        f"|--------|---------|",
        f"| Findings / PR | {metrics.avg_findings_per_pr:.1f} |",
        f"| Lines Changed / PR | {metrics.avg_lines_changed_per_pr:.1f} |",
        f"| CI Attempts / PR | {metrics.avg_ci_attempts:.1f} |",
        f"",
        f"---",
        f"*Generated by Tech Debt Scanner — Powered by Devin*",
    ])

    return "\n".join(lines)


def save_report(report_content: str, output_dir: str) -> str:
    """Save report to a timestamped markdown file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = Path(output_dir) / f"tech-debt-report-{timestamp}.md"
    path.write_text(report_content, encoding="utf-8")
    return str(path)


def generate_dashboard_data(
    metrics: PipelineMetrics,
    config: PipelineConfig,
) -> dict:
    """Generate JSON-serializable data for the HTML dashboard."""
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "repo": config.repo,
        "metrics": {
            "total_findings": metrics.total_findings,
            "bugs_found": metrics.bugs_found,
            "tech_debt_found": metrics.tech_debt_found,
            "total_prs_created": metrics.total_prs_created,
            "issue_filed_count": metrics.issue_filed_count,
            "total_agents_spawned": metrics.total_agents_spawned,
            "total_lines_added": metrics.total_lines_added,
            "total_lines_removed": metrics.total_lines_removed,
            "total_comments_added": metrics.total_comments_added,
            "total_docstrings_added": metrics.total_docstrings_added,
            "total_md_files_created": metrics.total_md_files_created,
            "ci_pass_rate": metrics.ci_pass_rate,
            "avg_ci_attempts": metrics.avg_ci_attempts,
            "avg_findings_per_pr": metrics.avg_findings_per_pr,
            "avg_lines_changed_per_pr": metrics.avg_lines_changed_per_pr,
        },
        "findings_by_category": metrics.findings_by_category,
        "findings_by_severity": metrics.findings_by_severity,
        "prs": [
            {
                "pr_number": pr.pr_number,
                "pr_url": pr.pr_url,
                "title": pr.title,
                "category": pr.category,
                "labels": pr.labels,
                "findings_addressed": pr.findings_addressed,
                "lines_added": pr.lines_added,
                "lines_removed": pr.lines_removed,
                "ci_attempts": pr.ci_attempts,
                "ci_passed": pr.ci_passed,
            }
            for pr in metrics.prs
        ],
        "issues": [
            {
                "issue_number": issue.issue_number,
                "issue_url": issue.issue_url,
                "title": issue.title,
                "category": issue.category,
                "severity": issue.severity,
            }
            for issue in metrics.issues
        ],
    }
