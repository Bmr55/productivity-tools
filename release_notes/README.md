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

Environment variables override `.env` values. The clients auto-detect credentials. The ADO REST implementation is currently a stub, so configured live mode reports that it is not yet implemented instead of falling back to mock data.

## Project Structure

```
release_notes/
  main.py               # CLI entry point
  config.py             # Credential loading (.env + env vars)
  generator.py          # Orchestrator — fetches ADO release, selects formatter
  ado_client.py         # Azure DevOps API client (mocked when no credentials)
  gitlab_client.py      # GitLab API client (mocked when no credentials)
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
  Epic ──→ Feature ──→ WorkItem (User Story / Bug)

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
| RTC Item | Custom ADO field — Rational Team Concert reference |
| Feature | Parent ADO Feature (ParentWorkItem with id, title, type, state, url) |
| Epic | Grandparent ADO Epic (ParentWorkItem with id, title, type, state, url) |
| Custom Fields | Arbitrary `name: value` fields from ADO |

## Custom ADO Fields

Custom fields (e.g. `RTC Item`) are stored in the `custom_fields` dict on each `WorkItem` model, with a convenience property `rtc_item` for direct access. All formatters render custom fields automatically.

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
