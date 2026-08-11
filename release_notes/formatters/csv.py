from __future__ import annotations

import csv
import io

from release_notes.formatters._escape import sanitize_text
from release_notes.models import RTC_FIELD_KEY, Release, TestTask, WorkItem

HEADER = [
    "Release ID", "Release Title", "Version", "Release Date",
    "Test Task ID", "Test Task Title", "Test Task State",
    "Work Item ID", "Work Item Title", "Work Item Type", "Work Item State",
    "Description", "Assigned To", "Priority", "Severity",
    "Area Path", "Iteration Path", "Tags", "RTC Item",
    "Feature ID", "Feature Title", "Feature State",
    "Epic ID", "Epic Title", "Epic State",
    "GitLab Issue ID", "GitLab Issue IID", "GitLab Issue Title", "GitLab Issue State", "GitLab Issue URL",
    "GitLab MR ID", "GitLab MR IID", "GitLab MR Title", "GitLab MR State", "GitLab MR URL", "GitLab MR Branch",
]


def _safe(value: object) -> str:
    """Prefix values a spreadsheet would evaluate as a formula.

    Excel and LibreOffice strip leading whitespace, tabs, and carriage returns
    before deciding whether a cell is a formula, so the check looks past them."""
    value = sanitize_text(value)
    stripped = value.lstrip("\t\r\n ")
    if stripped and stripped[0] in "=+-@":
        return "'" + value
    return value


def _row(release: Release, tt: TestTask, wi: WorkItem) -> list[str]:
    values: list[object] = [
        release.id, release.title, release.version, release.release_date,
        tt.id, tt.title, tt.state,
        wi.id, wi.title, wi.work_item_type.value, wi.state,
        wi.description, wi.assigned_to, wi.priority, wi.severity,
        wi.area_path, wi.iteration_path, ";".join(str(t) for t in wi.tags), wi.rtc_item,
        wi.parent_feature.id if wi.parent_feature else "",
        wi.parent_feature.title if wi.parent_feature else "",
        wi.parent_feature.state if wi.parent_feature else "",
        wi.parent_epic.id if wi.parent_epic else "",
        wi.parent_epic.title if wi.parent_epic else "",
        wi.parent_epic.state if wi.parent_epic else "",
        wi.gitlab_issue.id if wi.gitlab_issue else "",
        wi.gitlab_issue.iid if wi.gitlab_issue else "",
        wi.gitlab_issue.title if wi.gitlab_issue else "",
        wi.gitlab_issue.state if wi.gitlab_issue else "",
        wi.gitlab_issue.web_url if wi.gitlab_issue else "",
        wi.gitlab_mr.id if wi.gitlab_mr else "",
        wi.gitlab_mr.iid if wi.gitlab_mr else "",
        wi.gitlab_mr.title if wi.gitlab_mr else "",
        wi.gitlab_mr.state if wi.gitlab_mr else "",
        wi.gitlab_mr.web_url if wi.gitlab_mr else "",
        f"{wi.gitlab_mr.source_branch} -> {wi.gitlab_mr.target_branch}" if wi.gitlab_mr else "",
    ]
    return [_safe(value) for value in values]


def generate_csv(release: Release) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADER)

    for tt in release.test_tasks:
        for wi in tt.linked_work_items:
            writer.writerow(_row(release, tt, wi))

    return buf.getvalue()
