<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# Autonomous Issue Remediation Engine

A fork of [Apache Superset](https://github.com/apache/superset) wired with a GitHub Actions workflow that turns any issue labeled `devin-fix` into a pull request — automatically. A [Devin](https://devin.ai) AI agent reads the issue, clones the repo, writes the fix, and opens a PR referencing it. The entire loop (issue → PR) runs without human intervention; you just review and merge.

## How to Test (< 5 minutes)

### Option A — Collaborator access (fastest)

1. **Email [astein1801@gmail.com](mailto:astein1801@gmail.com)** with your GitHub username to be added as a collaborator.
2. Open an issue on this repo (or pick an existing one).
3. Add the **`devin-fix`** label.
4. Watch the **Actions** tab — a workflow run appears within seconds.
5. A Devin session is created; a comment on the issue links to it.
6. Within minutes, a PR referencing the issue is opened automatically.

### Option B — Fork it yourself

1. **Fork** this repo.
2. In your fork, go to **Settings → Secrets and variables → Actions** and add a secret named **`DEVIN_API_TOKEN`** with your [Devin API token](https://app.devin.ai/settings).
3. Create an issue in your fork and add the **`devin-fix`** label.
4. The workflow triggers identically — it uses `${{ github.repository }}` so no config changes are needed.

## View the Dashboard

The dashboard is static HTML — no build step, no dependencies.

```bash
cd dashboard/
python3 -m http.server 8000
# open http://localhost:8000
```

GitHub data (issues, PRs) loads without authentication for public repos.
On first load you can paste a Devin API token to see active sessions; check "Remember on this browser" to persist it.

## What to Look At

| Where | What you'll see |
|-------|-----------------|
| [**Issues**](../../issues?q=label%3Adevin-fix) | Issues labeled `devin-fix` that triggered the engine |
| [**Pull Requests**](../../pulls?q=label%3Aautomated-fix) | PRs opened by Devin with the `automated-fix` label |
| [**Actions**](../../actions/workflows/tech-debt-fixer.yml) | Workflow runs — one per labeled issue |
| `.github/workflows/tech-debt-fixer.yml` | The workflow file (trigger + permissions) |
| `scripts/tech_debt_scanner/fix_issue.py` | Python script that calls the Devin API |
| `dashboard/` | Static HTML dashboard with live GitHub/Devin metrics |

## Architecture

```
1. Issue labeled "devin-fix"
2. GitHub Actions workflow fires  (.github/workflows/tech-debt-fixer.yml)
3. Workflow calls Devin API       (scripts/tech_debt_scanner/fix_issue.py)
4. Devin agent opens a PR         (references "Fixes #N")
5. Status comment posted on issue (links to Devin session + PR)
```

## Results

| Issue | PR | Description |
|-------|----|-------------|
| [#116](../../issues/116) | [#128](../../pull/128) | Last month missing on time-series X axis |
| [#112](../../issues/112) | [#125](../../pull/125) | BigQuery errors with apostrophes in filters |
| [#111](../../issues/111) | [#126](../../pull/126) | Percentage formatting broken on small numbers |
| [#110](../../issues/110) | [#129](../../pull/129) | CSV import creates duplicate datasets |
| [#109](../../issues/109) | [#127](../../pull/127) | Histogram warning in logs |
| [#117](../../issues/117) | [#118](../../pull/118) | Chart description heatmap x-axis cutoff |

Every PR was generated end-to-end by a Devin agent with zero manual coding. Review any PR to see the diff, the linked Devin session, and the original issue.
