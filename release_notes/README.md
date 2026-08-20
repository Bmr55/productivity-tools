# Release Notes Generator

Generates software release notes by pulling data from Azure DevOps (user stories, bugs, test tasks) and GitLab (issues, merge requests), then renders them as Markdown, HTML, and CSV.

## Quick Start

```bash
cd release_notes
python main.py 1001 --mock
```

Output goes to `exports/q3_platform_release_v420_1001/` containing `release_notes.md`, `release_notes.html`, and `release_notes.csv`.

No API keys are needed for explicit mock mode. Without `--mock`, missing or partial credentials are treated as configuration errors rather than silently producing fixture data.

## Usage

```
python main.py <release_id> [--format markdown|html|csv|all] [--stdout] [--mock]

  release_id   ADO Release ID
  --format     Output format(s), defaults to all (generates every format)
  --stdout     Print to stdout instead of exporting to file.
               Pairs with --format to select output type.
  --mock       Explicitly use the bundled mock release (ID 1001).

Examples:
  python main.py 1001 --mock                            # export all three formats
  python main.py 1001 --mock --format html              # export HTML only
  python main.py 1001 --mock --format csv --stdout      # print CSV to stdout
  python main.py 1001 --mock --format markdown --stdout # print markdown to stdout
```

## Configuration

Use all three ADO settings for live mode, or pass `--mock` for fixture data. Partial configuration is rejected.

### Option 1 — .env file (recommended)

Copy `.env.example` to `.env` in the `release_notes/` directory and fill in your credentials:

```
ADO_ORG_URL=https://dev.azure.com/your-org
ADO_PAT=your-personal-access-token
ADO_PROJECT=YourProject

GITLAB_BASE_URL=https://gitlab.example.com
GITLAB_PRIVATE_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
```

### Option 2 — Environment variables

```powershell
# PowerShell
$env:ADO_ORG_URL = "https://dev.azure.com/your-org"
$env:ADO_PAT = "your-token"
$env:ADO_PROJECT = "YourProject"
$env:GITLAB_BASE_URL = "https://gitlab.example.com"
$env:GITLAB_PRIVATE_TOKEN = "glpat-xxx"
```

Environment variables override `.env` values. The clients auto-detect credentials. With live ADO credentials, `get_release_by_id` fetches the release work item, its Test Task children (via a WIQL query on `System.Parent`), their linked User Stories and Bugs, and the parent Feature/Epic hierarchy from the Azure DevOps REST API (`api-version=7.0`). It assumes Test Tasks are children of the release work item. The GitLab REST client is currently a stub, so configured live mode reports that it is not yet implemented instead of falling back to mock data.

**Corporate VPN note**: if requests fail with `[WinError 10060]` (connection timeout), the VPN likely requires a proxy. urllib uses the Windows system proxy automatically, but PAC-based proxies are not supported — set `ADO_PROXY` (e.g. `http://proxy.corp.com:8080`) in `.env` or the environment to route ADO traffic explicitly. Timeout-class failures are retried up to 3 times before failing with this hint.

## Epic Tree Export

Exports the open Epic/Feature/User Story/Bug hierarchy (including epics nested under other epics) to JSON plus a self-contained interactive HTML page:

```bash
python release_notes/epic_tree_export.py          # live ADO (reads .env)
python release_notes/epic_tree_export.py --mock   # bundled demo data
```

Outputs `exports/epic_tree.json` and `exports/epic_tree.html` (open directly — the page also accepts drag/dropped JSON). Features:

- **Tree view** — collapsible hierarchy with expand/collapse toggle
- **Graph view** — column layout (Epics / Features / Stories & Bugs) with ADO Agile default type colors
- **Epic filter dropdown** — view a single top-level epic or all
- **Settings panel** (persisted to `localStorage`) — Visibility tab to hide level-1/2 epics, Order tab to reorder epics with arrow controls; Save/Reset/Close

## Project Structure

```
release_notes/
  main.py               # CLI entry point
  config.py             # Credential loading (.env + env vars)
  generator.py          # Orchestrator — fetches ADO release, selects formatter
  ado_client.py         # Azure DevOps API client (mocked when no credentials)
  gitlab_client.py      # GitLab API client (mocked when no credentials)
  epic_tree_export.py   # Epic/Feature/Story/Bug tree export to JSON + HTML
  epic_tree.html        # Template for the interactive epic tree page
  models.py             # Data models (Release, TestTask, WorkItem, GitLabIssue, GitLabMergeRequest)
  mock_data.py          # Sample release with 3 test tasks and 6 linked work items
  .env.example          # Template for API credentials
  formatters/
    markdown.py         # Markdown output
    html.py             # Self-contained HTML output with inline CSS
    csv.py              # CSV output (one row per work item, flattened)
```

## Data Hierarchy

```
ADO Hierarchy (parent links)
  Epic ──→ Epic (optional nesting) ──→ Feature ──→ WorkItem (User Story / Bug)

Release Structure (test validation)
  Release ──→ TestTask ──→ WorkItem (same as above)
                               ├── GitLabIssue
                               └── GitLabMergeRequest
```

## Work Item Fields

| Field | Description |
|---|---|
| ID | ADO work item ID |
| Title | Work item title |
| Type | User Story or Bug |
| State | Current work item state |
| Description | Work item description (acceptance criteria) |
| Assigned to | Owner |
| Priority | Numeric priority |
| Severity | Bug severity (bugs only) |
| Area Path | Product area classification |
| Iteration Path | Sprint/iteration |
| Tags | ADO tags |
| RTC Item | Rational Team Concert reference — maps to `Custom.RTCWI` in the connected ADO project |
| Feature | Parent ADO Feature (ParentWorkItem with id, title, type, state, url) |
| Epic | Grandparent ADO Epic (ParentWorkItem with id, title, type, state, url) |
| Custom Fields | Arbitrary `name: value` fields from ADO |

## Custom ADO Fields

Custom fields (`Custom.*` in ADO) are stored in the `custom_fields` dict on each `WorkItem` model, and all formatters render them automatically. The connected ADO project defines these custom fields:

| ADO Field | Surfaced As |
|---|---|
| `Custom.RTCWI` | `RTC Item` (canonical alias) and `RTCWI` |
| `Custom.ConfigurationRelease` | `ConfigurationRelease` |
| `Custom.FixedRelease` | `FixedRelease` |
| `Custom.PullIn` | `PullIn` |

The `rtc_item` convenience property on `WorkItem` returns the value of the first custom field containing "RTC" (`Custom.RTCWI`), falling back to an empty string when absent.

## Parent Feature & Epic Linking

Each work item can reference its parent Feature and grandparent Epic via the ADO work item hierarchy:

```
Epic (ParentWorkItem)
  └── Feature (ParentWorkItem)
        └── WorkItem (User Story / Bug)
```

Set via the `parent_feature` and `parent_epic` fields on `WorkItem`. Both are optional `ParentWorkItem` objects with `id`, `title`, `work_item_type`, `state`, and `url` properties.

In **Markdown**, they render as plain text links:
```
- **Feature**: [Feature 200] Dashboard V2 Widget Suite (Done)
- **Epic**: [Epic 100] Platform UX Modernization (In Progress)
```

In **HTML**, they render as clickable ADO links with state badges. In **CSV**, they appear as `Feature ID`, `Feature Title`, `Feature State`, `Epic ID`, `Epic Title`, and `Epic State` columns.

## CSV Export

CSV output flattens the full hierarchy into rows — one row per work item. Columns include all release, test task, work item, parent feature/epic, and GitLab issue/MR fields:

| Column Group | Fields |
|---|---|
| Release | Release ID, Release Title, Version, Release Date |
| Test Task | Test Task ID, Test Task Title, Test Task State |
| Work Item | ID, Title, Type, State, Description, Assigned To, Priority, Severity, Area Path, Iteration Path, Tags, RTC Item |
| Parent Links | Feature ID, Feature Title, Feature State, Epic ID, Epic Title, Epic State |
| GitLab Issue | Issue ID, Issue IID, Issue Title, Issue State, Issue URL |
| GitLab MR | MR ID, MR IID, MR Title, MR State, MR URL, MR Branch |

```bash
python main.py 1001 --mock --format csv           # exports csv only
python main.py 1001 --mock --format csv --stdout  # csv to stdout
python main.py 1001 --mock --format all           # all three formats (default)
```
