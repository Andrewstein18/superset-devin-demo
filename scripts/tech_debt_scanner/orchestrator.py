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
"""Main orchestrator for the tech debt scanner pipeline.

Usage:
    python -m scripts.tech_debt_scanner.orchestrator
    python -m scripts.tech_debt_scanner.orchestrator --dry-run
    python -m scripts.tech_debt_scanner.orchestrator --skip-docs --skip-fixers
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.tech_debt_scanner.ci_fixer import run_ci_fixers
from scripts.tech_debt_scanner.config import PipelineConfig
from scripts.tech_debt_scanner.documentation import run_documentation
from scripts.tech_debt_scanner.fixer import run_fixers
from scripts.tech_debt_scanner.models import PipelineMetrics
from scripts.tech_debt_scanner.report import (
    collect_metrics,
    generate_dashboard_data,
    generate_report,
    save_report,
)
from scripts.tech_debt_scanner.scanner import run_scanners
from scripts.tech_debt_scanner.triage import triage_findings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tech_debt_scanner")

REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


def run_pipeline(
    config: PipelineConfig | None = None,
    *,
    dry_run: bool = False,
    skip_docs: bool = False,
    skip_fixers: bool = False,
) -> PipelineMetrics:
    """Execute the full tech debt scanner pipeline."""
    if config is None:
        config = PipelineConfig()

    logger.info(
        "Starting tech debt scanner pipeline for %s",
        config.repo,
    )
    logger.info(
        "Backend targets: %s",
        ", ".join(config.scan_targets_backend),
    )
    logger.info(
        "Frontend targets: %s",
        ", ".join(config.scan_targets_frontend),
    )

    total_agents = 0

    # Stage 1A: Run scanners
    logger.info("=== Stage 1A: Running scanner agents ===")
    scanner_result = run_scanners(config)
    total_agents += scanner_result.agents_spawned
    logger.info(
        "Scanners complete: %d findings from %d agents",
        len(scanner_result.findings),
        scanner_result.agents_spawned,
    )

    # Stage 1B: Run documentation (parallel in production, sequential here)
    doc_result = None
    if not skip_docs:
        logger.info("=== Stage 1B: Running documentation agent ===")
        doc_result = run_documentation(config)
        total_agents += 1
        logger.info(
            "Documentation complete: %d .md files, %d docstrings, %d comments",
            doc_result.md_files_created,
            doc_result.docstrings_added,
            doc_result.comments_added,
        )

    # Triage findings
    logger.info("=== Triage: Deduplicating and classifying findings ===")
    triage_result = triage_findings(scanner_result.findings)
    logger.info(
        "Triage complete: %d auto-fixes, %d issues to file",
        len(triage_result.auto_fixes),
        len(triage_result.issues_to_file),
    )

    if dry_run:
        logger.info("Dry run — skipping fixers, CI, and issue creation")
        metrics = collect_metrics(
            scanner_findings=scanner_result.findings,
            doc_result=doc_result,
            triage_result=triage_result,
            prs=[],
            issues=[],
            agents_spawned=total_agents,
        )
        _save_outputs(metrics, config)
        return metrics

    # Stage 2: Run fixers
    fixer_result = None
    if not skip_fixers:
        logger.info("=== Stage 2: Running fixer agents ===")
        fixer_result = run_fixers(
            config,
            triage_result.auto_fixes,
            triage_result.issues_to_file,
        )
        total_agents += fixer_result.agents_spawned
        logger.info(
            "Fixers complete: %d PRs, %d issues filed",
            len(fixer_result.prs),
            len(fixer_result.issues),
        )

        # Stage 3: CI fixers
        logger.info("=== Stage 3: Running CI fixer agents ===")
        updated_prs = run_ci_fixers(config, fixer_result.prs)
        fixer_result.prs = updated_prs
        passed = sum(1 for pr in updated_prs if pr.ci_passed)
        logger.info(
            "CI fixers complete: %d/%d PRs passing",
            passed,
            len(updated_prs),
        )

    # Collect metrics and generate report
    metrics = collect_metrics(
        scanner_findings=scanner_result.findings,
        doc_result=doc_result,
        triage_result=triage_result,
        prs=fixer_result.prs if fixer_result else [],
        issues=fixer_result.issues if fixer_result else [],
        agents_spawned=total_agents,
    )
    _save_outputs(metrics, config)
    return metrics


def _save_outputs(metrics: PipelineMetrics, config: PipelineConfig) -> None:
    """Save report and dashboard data."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report_md = generate_report(metrics, config)
    report_path = save_report(report_md, str(REPORT_DIR))
    logger.info("Report saved: %s", report_path)

    dashboard_data = generate_dashboard_data(metrics, config)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    data_path = REPORT_DIR / f"dashboard-data-{timestamp}.json"
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(dashboard_data, fh, indent=2, default=str)
    logger.info("Dashboard data saved: %s", data_path)

    metrics.compute_averages()
    logger.info("=== Pipeline Complete ===")
    logger.info("Total findings: %d", metrics.total_findings)
    logger.info("Total PRs created: %d", metrics.total_prs_created)
    logger.info("Total issues filed: %d", metrics.issue_filed_count)
    logger.info("Total agents spawned: %d", metrics.total_agents_spawned)
    logger.info(
        "Bugs found: %d | Tech debt found: %d",
        metrics.bugs_found,
        metrics.tech_debt_found,
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run the tech debt scanner pipeline",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan only — no PRs or issues",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip Stage 1B documentation agent",
    )
    parser.add_argument(
        "--skip-fixers",
        action="store_true",
        help="Skip Stage 2+3 (fixers and CI)",
    )
    parser.add_argument(
        "--targets",
        type=str,
        default="",
        help="Comma-separated directories to scan (overrides defaults)",
    )
    args = parser.parse_args()

    config = PipelineConfig()
    if args.targets:
        targets = [t.strip() for t in args.targets.split(",") if t.strip()]
        backend = [t for t in targets if t.startswith("superset/")]
        frontend = [t for t in targets if t.startswith("superset-frontend/")]
        if backend:
            config.scan_targets_backend = backend
        if frontend:
            config.scan_targets_frontend = frontend

    try:
        metrics = run_pipeline(
            config,
            dry_run=args.dry_run,
            skip_docs=args.skip_docs,
            skip_fixers=args.skip_fixers,
        )
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)

    print(
        json.dumps(
            {
                "total_findings": metrics.total_findings,
                "total_prs": metrics.total_prs_created,
                "total_issues": metrics.issue_filed_count,
                "agents_spawned": metrics.total_agents_spawned,
                "bugs_found": metrics.bugs_found,
                "tech_debt_found": metrics.tech_debt_found,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
