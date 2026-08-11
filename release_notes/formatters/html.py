from __future__ import annotations

import html as _html

from release_notes.formatters._escape import is_safe_url, sanitize_text
from release_notes.models import RTC_FIELD_KEY, WORK_ITEM_ICONS, Release, TestTask, WorkItem

CSS_STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; color: #1a1a1a; background: #fafafa; }
  h1 { border-bottom: 2px solid #0078d4; padding-bottom: 0.5rem; }
  h2 { margin-top: 2rem; color: #0078d4; }
  h3 { margin-top: 1.5rem; }
  .meta { color: #666; font-size: 0.95rem; margin-bottom: 1rem; }
  .wi-card { background: #fff; border: 1px solid #e1e4e8; border-radius: 6px; padding: 1rem 1.25rem; margin: 0.75rem 0; }
  .wi-card table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  .wi-card td { padding: 4px 8px; vertical-align: top; }
  .wi-card td:first-child { font-weight: 600; white-space: nowrap; width: 130px; color: #555; }
  .desc { margin-top: 0.75rem; padding: 0.75rem; background: #f6f8fa; border-radius: 4px; font-size: 0.92rem; }
  .links { margin-top: 0.5rem; font-size: 0.9rem; }
  .links a { color: #0366d6; text-decoration: none; }
  .links a:hover { text-decoration: underline; }
  .tt-header { background: #f0f7ff; padding: 0.5rem 1rem; border-radius: 6px; margin: 1.5rem 0 0.75rem 0; font-weight: 600; }
  .story { border-left: 3px solid #28a745; }
  .bug { border-left: 3px solid #d73a49; }
  .tag { display: inline-block; background: #e1e4e8; border-radius: 3px; padding: 1px 6px; font-size: 0.8rem; margin: 0 2px; }
  .footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e1e4e8; color: #999; font-size: 0.85rem; text-align: center; }
</style>
"""


def _safe_url(url: str) -> str:
    clean = sanitize_text(url)
    return _html.escape(clean) if is_safe_url(clean) else "#"


def _esc(value: object) -> str:
    """Escape any field for HTML. Model type hints are not enforced at runtime,
    so numeric-looking fields from the API are escaped like everything else."""
    return _html.escape(sanitize_text(value))


def _format_work_item_html(wi: WorkItem) -> str:
    css_class = "story" if wi.work_item_type.value == "User Story" else "bug"
    type_icon = WORK_ITEM_ICONS.get(wi.work_item_type, "\U0001f41b")

    parts = [
        f'<div class="wi-card {css_class}">',
        f"<h3>{type_icon} [{_esc(wi.work_item_type.value)}] {_esc(wi.title)}</h3>",
        "<table>",
        f"<tr><td>ID</td><td>{_esc(wi.id)}</td></tr>",
        f"<tr><td>State</td><td>{_esc(wi.state)}</td></tr>",
        f"<tr><td>Assigned to</td><td>{_esc(wi.assigned_to)}</td></tr>",
        f"<tr><td>Priority</td><td>{_esc(wi.priority)}</td></tr>",
    ]
    if wi.severity:
        parts.append(f"<tr><td>Severity</td><td>{_esc(wi.severity)}</td></tr>")
    if wi.area_path:
        parts.append(f"<tr><td>Area</td><td>{_esc(wi.area_path)}</td></tr>")
    if wi.iteration_path:
        parts.append(f"<tr><td>Iteration</td><td>{_esc(wi.iteration_path)}</td></tr>")
    if wi.tags:
        tags_html = " ".join(f'<span class="tag">{_esc(t)}</span>' for t in wi.tags)
        parts.append(f"<tr><td>Tags</td><td>{tags_html}</td></tr>")
    if wi.rtc_item:
        parts.append(f"<tr><td>RTC Item</td><td>{_esc(wi.rtc_item)}</td></tr>")
    if wi.parent_feature:
        parts.append(
            f"<tr><td>Feature</td><td>"
            f'<a href="{_safe_url(wi.parent_feature.url)}">[{_esc(wi.parent_feature.work_item_type.value)} {_esc(wi.parent_feature.id)}] '
            f"{_esc(wi.parent_feature.title)}</a> ({_esc(wi.parent_feature.state)})</td></tr>"
        )
    if wi.parent_epic:
        parts.append(
            f"<tr><td>Epic</td><td>"
            f'<a href="{_safe_url(wi.parent_epic.url)}">[{_esc(wi.parent_epic.work_item_type.value)} {_esc(wi.parent_epic.id)}] '
            f"{_esc(wi.parent_epic.title)}</a> ({_esc(wi.parent_epic.state)})</td></tr>"
        )
    for name, value in wi.custom_fields.items():
        if name == RTC_FIELD_KEY:
            continue
        parts.append(f"<tr><td>{_esc(name)}</td><td>{_esc(value)}</td></tr>")
    parts.append("</table>")

    if wi.description:
        parts.append(f'<div class="desc">{_esc(wi.description)}</div>')

    if wi.gitlab_issue or wi.gitlab_mr:
        parts.append('<div class="links">')
        if wi.gitlab_issue:
            parts.append(
                f'\U0001f4cc <strong>GitLab Issue:</strong> '
                f'<a href="{_safe_url(wi.gitlab_issue.web_url)}">{_esc(wi.gitlab_issue.title)}</a> '
                f"(state: {_esc(wi.gitlab_issue.state)})<br>"
            )
        if wi.gitlab_mr:
            parts.append(
                f'\U0001f510 <strong>Merge Request:</strong> '
                f'<a href="{_safe_url(wi.gitlab_mr.web_url)}">{_esc(wi.gitlab_mr.title)}</a> '
                f"(state: {_esc(wi.gitlab_mr.state)}, <code>{_esc(wi.gitlab_mr.source_branch)}</code> \u2192 "
                f"<code>{_esc(wi.gitlab_mr.target_branch)}</code>)"
            )
        parts.append("</div>")

    parts.append("</div>")
    return "\n".join(parts)


def _format_test_task_html(tt: TestTask) -> str:
    parts = [
        f'<div class="tt-header">\u2705 Test Task: {_esc(tt.title)} <em>(State: {_esc(tt.state)})</em></div>',
    ]
    for wi in tt.linked_work_items:
        parts.append(_format_work_item_html(wi))
    return "\n".join(parts)


def generate_html(release: Release) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        f"<title>Release Notes — {_esc(release.title)}</title>",
        CSS_STYLE,
        "</head>",
        "<body>",
        f"<h1>\U0001f4e6 Release Notes &mdash; {_esc(release.title)}</h1>",
        '<div class="meta">',
        f"<strong>Version:</strong> {_esc(release.version)}<br>",
        f"<strong>Release Date:</strong> {_esc(release.release_date)}",
        "</div>",
    ]

    if release.description:
        parts.append(f"<p>{_esc(release.description)}</p>")

    if not release.test_tasks:
        parts.append("<p><em>No test tasks linked to this release.</em></p>")
    else:
        for tt in release.test_tasks:
            parts.append(_format_test_task_html(tt))

    parts.append(
        '<div class="footer">Generated by release-notes tool | '
        f"{_esc(release.version)}</div>"
    )
    parts.append("</body></html>")
    return "\n".join(parts)
