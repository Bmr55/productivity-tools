from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from tempfile import NamedTemporaryFile

from release_notes.ado_client import ADOClient
from release_notes.gitlab_client import GitLabClient
from release_notes.formatters.markdown import generate_markdown
from release_notes.formatters.html import generate_html
from release_notes.formatters.csv import generate_csv
from release_notes.models import Release, TestTask, WorkItem

_MAX_SLUG_LENGTH = 80
_MAX_SLUG_BYTES = 200
_MAX_ADO_ID = 2**63 - 1
_WINDOWS_RESERVED_NAMES = {
    "aux", "clock", "con", "conin", "conout", "nul", "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def _sanitize(name: object) -> str:
    """Convert a release title to a bounded, filesystem-safe slug."""
    slug = unicodedata.normalize("NFKC", str(name)).strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "_", slug)
    slug = slug.strip("._- ")[:_MAX_SLUG_LENGTH].rstrip("._- ")
    while len(slug.encode("utf-8")) > _MAX_SLUG_BYTES:
        slug = slug[:-1].rstrip("._- ")
    if slug.casefold() in _WINDOWS_RESERVED_NAMES:
        slug = f"_{slug}"
    return slug


def _release_id_component(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= _MAX_ADO_ID:
        raise ValueError("Release ID must be a positive signed 64-bit integer.")
    return str(value)


def _write_file(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError:
        tmp = NamedTemporaryFile(mode="w", suffix=path.suffix, encoding="utf-8", delete=False, dir=path.parent)
        try:
            tmp.write(content)
            tmp.close()
            Path(tmp.name).replace(path)
        except OSError:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise


def _resolve_gitlab_links(release: Release, gl_client: GitLabClient) -> None:
    """Walk all work items in the release and resolve their GitLab
    issue and MR links by searching GitLab for issues that reference
    the ADO work-item URL."""
    for tt in release.test_tasks:
        for wi in tt.linked_work_items:
            issue = gl_client.find_issue_by_ado_id(wi.id)
            if issue is not None:
                wi.gitlab_issue = issue
                mr = gl_client.find_mr_for_issue(issue.iid)
                if mr is not None:
                    wi.gitlab_mr = mr


def generate_all(
    ado_release_id: int,
    ado_client: ADOClient | None = None,
    gl_client: GitLabClient | None = None,
) -> tuple[str, str, str, Release]:
    if ado_client is None:
        try:
            ado_client = ADOClient()
        except (RuntimeError, ValueError):
            ado_client = ADOClient(use_mock=True)
    if gl_client is None:
        gl_client = GitLabClient(use_mock=True)

    try:
        release: Release = ado_client.get_release_by_id(ado_release_id)
    except RuntimeError:
        release = ADOClient(use_mock=True).get_release_by_id(ado_release_id)
    _resolve_gitlab_links(release, gl_client)
    md = generate_markdown(release)
    html = generate_html(release)
    csv_content = generate_csv(release)
    return md, html, csv_content, release


def _default_export_dir() -> Path:
    return Path(__file__).resolve().parent / "exports"


def export(release_id: int, base_dir: str = "", ado_client: ADOClient | None = None) -> tuple[Path, Path, Path]:
    if not base_dir:
        base_dir = str(_default_export_dir())
    md_content, html_content, csv_content, release = generate_all(release_id, ado_client)

    release_id = _release_id_component(release.id)
    dirname = f"{_sanitize(release.title) or 'release'}_{release_id}"
    out_dir = Path(base_dir) / dirname
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "release_notes.md"
    html_path = out_dir / "release_notes.html"
    csv_path = out_dir / "release_notes.csv"

    _write_file(md_path, md_content)
    _write_file(html_path, html_content)
    _write_file(csv_path, csv_content)

    return md_path, html_path, csv_path
