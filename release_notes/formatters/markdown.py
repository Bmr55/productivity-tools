from __future__ import annotations

from release_notes.formatters._escape import escape_markdown, markdown_field, markdown_url
from release_notes.models import RTC_FIELD_KEY, WORK_ITEM_ICONS, Release, TestTask, WorkItem


def _format_work_item(wi: WorkItem) -> str:
    icon = WORK_ITEM_ICONS.get(wi.work_item_type, "\U0001f41b")
    lines = [
        f"### {icon} [{wi.work_item_type.value}] {markdown_field(wi.title)}",
        "",
        f"- **ID**: {markdown_field(wi.id)}",
        f"- **State**: {markdown_field(wi.state)}",
        f"- **Assigned to**: {markdown_field(wi.assigned_to)}",
        f"- **Priority**: {markdown_field(wi.priority)}",
    ]
    if wi.severity:
        lines.append(f"- **Severity**: {markdown_field(wi.severity)}")
    if wi.area_path:
        lines.append(f"- **Area**: {markdown_field(wi.area_path)}")
    if wi.iteration_path:
        lines.append(f"- **Iteration**: {markdown_field(wi.iteration_path)}")
    if wi.tags:
        lines.append(f"- **Tags**: {', '.join(markdown_field(t) for t in wi.tags)}")
    if wi.rtc_item:
        lines.append(f"- **RTC Item**: {markdown_field(wi.rtc_item)}")
    if wi.parent_feature:
        lines.append(f"- **Feature**: [{wi.parent_feature.work_item_type.value} {markdown_field(wi.parent_feature.id)}] {markdown_field(wi.parent_feature.title)} ({markdown_field(wi.parent_feature.state)})")
    if wi.parent_epic:
        lines.append(f"- **Epic**: [{wi.parent_epic.work_item_type.value} {markdown_field(wi.parent_epic.id)}] {markdown_field(wi.parent_epic.title)} ({markdown_field(wi.parent_epic.state)})")
    for name, value in wi.custom_fields.items():
        if name == RTC_FIELD_KEY:
            continue
        lines.append(f"- **{markdown_field(name)}**: {markdown_field(value)}")
    if wi.description:
        lines.append("")
        lines.append(escape_markdown(wi.description))

    if wi.gitlab_issue:
        lines.append("")
        lines.append(f"\U0001f4cc **GitLab Issue**: [{markdown_field(wi.gitlab_issue.title)}]({markdown_url(wi.gitlab_issue.web_url)}) (state: {markdown_field(wi.gitlab_issue.state)})")

    if wi.gitlab_mr:
        lines.append("")
        lines.append(
            f"\U0001f510 **Merge Request**: [{markdown_field(wi.gitlab_mr.title)}]({markdown_url(wi.gitlab_mr.web_url)}) "
            f"(state: {markdown_field(wi.gitlab_mr.state)}, branch: `{markdown_field(wi.gitlab_mr.source_branch)}` -> `{markdown_field(wi.gitlab_mr.target_branch)}`)"
        )

    return "\n".join(lines)


def _format_test_task(tt: TestTask) -> str:
    lines = [
        f"## \u2705 Test Task: {markdown_field(tt.title)}",
        f"_State: {markdown_field(tt.state)}_",
        "",
    ]
    for wi in tt.linked_work_items:
        lines.append(_format_work_item(wi))
        lines.append("")
    return "\n".join(lines)


def generate_markdown(release: Release) -> str:
    lines = [
        f"# \U0001f4e6 Release Notes — {markdown_field(release.title)}",
        "",
        f"**Version**: {markdown_field(release.version)}",
        f"**Release Date**: {markdown_field(release.release_date)}",
        "",
        escape_markdown(release.description) if release.description else "",
        "",
        f"---",
        "",
    ]

    if not release.test_tasks:
        lines.append("_No test tasks linked to this release._")
        return "\n".join(lines)

    for tt in release.test_tasks:
        lines.append(_format_test_task(tt))

    return "\n".join(lines)
