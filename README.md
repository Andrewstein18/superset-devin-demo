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

**Engineering orgs drown in issues they can't close.**
Dependabot files CVEs faster than teams patch them. Snyk backlogs grow
quarterly. JIRA tech-debt tickets sit untouched for months. The bottleneck
isn't detection — it's remediation.

This project is an event-driven engine that **closes issues autonomously**.
Label any GitHub issue with `devin-fix`, and a [Devin](https://devin.ai)
agent reads the issue, writes the fix, and opens a PR — ready for human
review.

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                    Issue Sources                              │
│  (Dependabot, Snyk, SonarQube, JIRA, manual triage, ...)    │
└─────────────────────────┬────────────────────────────────────┘
                          │  label: devin-fix
                          ▼
┌──────────────────────────────────────────────────────────────┐
│               GitHub Actions Workflow                         │
│         .github/workflows/tech-debt-fixer.yml                │
│                                                              │
│  Trigger: issue labeled with "devin-fix"                     │
│  Action:  run scripts/tech_debt_scanner/fix_issue.py         │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                   Devin Agent                                 │
│                                                              │
│  1. Reads the issue                                          │
│  2. Clones the repo                                          │
│  3. Understands the codebase                                 │
│  4. Implements the fix                                       │
│  5. Opens a PR with "Fixes #N" (auto-closes on merge)       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                 Human Review                                  │
│         Review PR → Approve → Merge → Issue auto-closed      │
└──────────────────────────────────────────────────────────────┘
```

## Triggers

### 1. GitHub Actions (automatic)

Any issue labeled `devin-fix` triggers the workflow automatically:

1. Create or label an issue with `devin-fix`
2. The workflow spawns a Devin agent
3. Devin reads the issue, writes the fix, opens a PR
4. Review and merge the PR — the issue auto-closes

### 2. Manual CLI

```bash
python scripts/devin_trigger.py \
  --repo Andrewstein18/superset-devin-demo \
  --title "Fix: missing null check in parser" \
  --body "The parser crashes when input is None..." \
  --label devin-fix
```

This creates the GitHub issue and immediately triggers a Devin session.

## Observability: Dashboard

Open `dashboard/index.html` in a browser to see the value dashboard.
No build step required — it talks directly to the GitHub and Devin APIs.

**Headline metrics:**
- **Estimated $ Saved** — based on engineer hourly rate and hours-per-issue
- **Engineering Hours Saved** — gross hours reclaimed
- **Issues Closed Autonomously** — merged Devin PRs
- **Avg Time-to-PR** — issue opened → PR opened

**Supporting metrics:** PR pipeline health, success rate, active Devin
sessions, weekly throughput.

All value estimates use editable assumptions (engineer cost, hours per
issue, review time) — transparent math a VP of Engineering can trust.

## Setup

### 1. Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|----------|-------------|----------|
| `DEVIN_API_TOKEN` | Devin API token ([Settings → API](https://app.devin.ai)) | Yes |
| `GITHUB_TOKEN` | GitHub PAT with `repo` + `issues` scope | Yes |
| `TARGET_REPO` | Repository in `owner/repo` format | No (defaults to config.yaml) |
| `TRIGGER_LABEL` | Label that triggers the fixer | No (defaults to `devin-fix`) |

### 2. GitHub Actions secrets

Add `DEVIN_API_TOKEN` to your repo's Actions secrets:
**Settings → Secrets and variables → Actions → New repository secret**

### 3. Configuration

Edit `config.yaml` for persistent defaults:

```yaml
target_repo: "Andrewstein18/superset-devin-demo"
trigger_label: "devin-fix"
```

Environment variables override `config.yaml` values.

### 4. Dashboard — quick start

```bash
# Open directly in a browser — no server needed
open dashboard/index.html
```

On first load, paste your Devin API token when prompted. Check
"Remember on this browser" and it will be saved for next time — no
re-entry needed.

GitHub data (issues, PRs) loads without authentication for public repos.

### 5. Dashboard — local dev convenience

For a fully automatic load (no manual token entry at all):

```bash
cp dashboard/secrets.js.example dashboard/secrets.js
# Edit dashboard/secrets.js and paste your tokens
```

`secrets.js` is gitignored and will never be committed. It supports two tokens:

- **`GITHUB_TOKEN`** — raises the GitHub API rate limit from 60 to 5,000
  requests/hour. Create one at https://github.com/settings/tokens (no
  scopes needed for public repos).
- **`DEVIN_TOKEN`** — enables the "Active Sessions" card.

## Project Structure

```
├── .github/workflows/
│   └── tech-debt-fixer.yml     # Reactive workflow: issue labeled → Devin agent
├── scripts/
│   ├── tech_debt_scanner/
│   │   └── fix_issue.py        # Spawns a Devin fixer session for an issue
│   └── devin_trigger.py        # CLI: create issue + trigger Devin
├── dashboard/
│   ├── index.html              # Value dashboard (vanilla HTML+JS)
│   └── config.js               # Dashboard configuration defaults
├── config.yaml                 # Engine configuration
├── .env.example                # Environment variable template
└── tests/unit_tests/remediation/
    └── test_fix_issue.py       # Integration test for the fixer flow
```

## Next Steps

- **Multi-repo support** — run one engine instance across multiple repositories
- **JIRA / Linear as trigger sources** — watch external issue trackers, not just GitHub labels
- **Custom remediation playbooks per label** — different fix strategies for security vs. tech-debt vs. dependency issues
- **Per-team cost dashboards** — break down savings by team or service area
- **Webhook-driven triggers** — replace polling with real-time event processing
