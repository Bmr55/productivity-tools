from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode

from release_notes import config
from release_notes.models import GitLabIssue, GitLabMergeRequest, extract_ado_id

_CLOSES_ISSUE_RE = re.compile(
    r"\b(?:clos(?:e(?:s|d)?|ing)|fix(?:es|ed|ing)?|resolv(?:e(?:s|d)?|ing))\s+#?\s*(\d+)\b",
    re.IGNORECASE,
)

_PER_PAGE = 100


def _closes_issue(mr: GitLabMergeRequest, issue_iid: int) -> bool:
    """Return True if *mr* closes the issue with the given project-scoped IID
    (via a "Closes #N"-style keyword in its description)."""
    if not mr.description:
        return False
    for match in _CLOSES_ISSUE_RE.finditer(mr.description):
        if int(match.group(1)) == issue_iid:
            return True
    return False


class GitLabClient:
    """GitLab client with an explicit opt-in mock mode.

    Searches GitLab for issues and merge requests linked to ADO work items.
    Follows the team convention of placing the ADO work-item URL in the
    GitLab issue description body.

    Credentials are read from environment variables or a .env file:

        GITLAB_BASE_URL       — https://gitlab.example.com
        GITLAB_PRIVATE_TOKEN  — personal or project access token
        GITLAB_PROJECT_ID     — optional; scope lookups to a single project
                                (numeric ID or "group/project" path)

    Set ``use_mock=True`` to use the bundled mock index without credentials."""

    def __init__(
        self,
        base_url: str = "",
        private_token: str = "",
        project_id: str = "",
        *,
        use_mock: bool = False,
    ):
        self._use_mock = use_mock
        if use_mock:
            if any((base_url, private_token, project_id)):
                raise ValueError("Mock mode cannot be combined with GitLab credentials.")
            self._base_url = ""
            self._private_token = ""
            self._project_id = ""
            return

        self._base_url = base_url or config.GITLAB_BASE_URL()
        self._private_token = private_token or config.GITLAB_PRIVATE_TOKEN()
        self._project_id = project_id or config.GITLAB_PROJECT_ID()

        configured = {
            "GITLAB_BASE_URL": self._base_url,
            "GITLAB_PRIVATE_TOKEN": self._private_token,
        }
        if any(configured.values()) and not all(configured.values()):
            missing = ", ".join(key for key, value in configured.items() if not value)
            raise ValueError(f"Partial GitLab configuration; missing: {missing}.")

        self._project_path_by_issue_iid: dict[int, str] = {}

    def __repr__(self) -> str:
        return (
            f"GitLabClient(base_url={self._base_url!r}, "
            f"private_token={'***' if self._private_token else 'unset'}, "
            f"project_id={self._project_id!r}, use_mock={self._use_mock!r})"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._private_token)

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    def _request(self, method: str, path: str, params: dict[str, str] | None = None) -> dict | list:
        url = f"{self._base_url.rstrip('/')}/api/v4{path}"
        if params:
            url += "?" + urlencode(params)
        req = urllib.request.Request(url, method=method)
        req.add_header("PRIVATE-TOKEN", self._private_token)
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(body_text).get("message", body_text)
            except Exception:
                msg = body_text
            raise RuntimeError(f"GitLab API error {e.code}: {msg}") from None

    def _request_pages(self, path: str, params: dict[str, str] | None = None) -> list[dict]:
        """GET a list endpoint and follow pagination until exhausted."""
        results: list[dict] = []
        page = 1
        while True:
            page_params = dict(params or {})
            page_params["page"] = str(page)
            page_params["per_page"] = str(_PER_PAGE)
            page_results = self._request("GET", path, page_params)
            results.extend(page_results)
            if len(page_results) < _PER_PAGE:
                break
            page += 1
        return results

    @staticmethod
    def _project_path_from_url(web_url: str) -> str:
        """Extract the "group/project" path from an issue or MR web URL."""
        match = re.search(r"^https?://[^/]+/(.+?)/-/(?:issues|merge_requests)/\d+/?$", web_url)
        return match.group(1) if match else ""

    def _issue_from_dict(self, data: dict) -> GitLabIssue:
        milestone = data.get("milestone")
        return GitLabIssue(
            id=int(data["id"]),
            iid=int(data["iid"]),
            title=data.get("title") or "",
            description=data.get("description") or "",
            state=data.get("state") or "",
            web_url=data.get("web_url") or "",
            labels=list(data.get("labels") or []),
            milestone=milestone.get("title", "") if isinstance(milestone, dict) else "",
        )

    def _mr_from_dict(self, data: dict) -> GitLabMergeRequest:
        author = data.get("author") or {}
        return GitLabMergeRequest(
            id=int(data["id"]),
            iid=int(data["iid"]),
            title=data.get("title") or "",
            description=data.get("description") or "",
            state=data.get("state") or "",
            web_url=data.get("web_url") or "",
            source_branch=data.get("source_branch") or "",
            target_branch=data.get("target_branch") or "",
            author=author.get("name") or author.get("username", ""),
            merged_at=data.get("merged_at") or "",
        )

    def find_issue_by_ado_id(self, ado_work_item_id: int) -> GitLabIssue | None:
        """Return the GitLab issue whose description contains a link to the
        given ADO work item.  Handles all URL variants (standard, sprint
        board, board view, bare suffix)."""
        if self._use_mock:
            from release_notes.mock_data import MOCK_GITLAB_ISSUES_BY_ADO_ID
            for issue in MOCK_GITLAB_ISSUES_BY_ADO_ID.values():
                if extract_ado_id(issue.description) == ado_work_item_id:
                    return issue
            return None
        if not self.is_configured:
            raise RuntimeError(
                "GitLab credentials are not configured. "
                "Configure GITLAB_BASE_URL and GITLAB_PRIVATE_TOKEN "
                "or explicitly enable mock mode."
            )

        if self._project_id:
            path = f"/projects/{quote(self._project_id, safe='')}/issues"
        else:
            path = "/issues"
        candidates = self._request_pages(
            path,
            {"search": str(ado_work_item_id), "state": "all", "scope": "all"},
        )

        for raw in candidates:
            if extract_ado_id(raw.get("description") or "") != ado_work_item_id:
                continue
            issue = self._issue_from_dict(raw)
            project_path = self._project_path_from_url(issue.web_url)
            if project_path:
                self._project_path_by_issue_iid[issue.iid] = project_path
            return issue
        return None

    def find_mr_for_issue(self, issue_iid: int) -> GitLabMergeRequest | None:
        """Return the merge request that closes the given GitLab issue."""
        if self._use_mock:
            from release_notes.mock_data import MOCK_GITLAB_MRS_BY_ISSUE_IID
            return MOCK_GITLAB_MRS_BY_ISSUE_IID.get(issue_iid)
        if not self.is_configured:
            raise RuntimeError(
                "GitLab credentials are not configured. "
                "Configure GITLAB_BASE_URL and GITLAB_PRIVATE_TOKEN "
                "or explicitly enable mock mode."
            )

        project_path = self._project_path_by_issue_iid.get(issue_iid, "")
        if not project_path and self._project_id:
            project_path = self._project_id

        if project_path:
            quoted = quote(project_path, safe="")
            related = self._request_pages(
                f"/projects/{quoted}/issues/{issue_iid}/related_merge_requests"
            )
            for raw in related:
                mr = self._mr_from_dict(raw)
                if _closes_issue(mr, issue_iid):
                    return mr

        candidates = self._request_pages(
            "/merge_requests",
            {"scope": "all", "state": "all", "search": str(issue_iid)},
        )
        for raw in candidates:
            mr = self._mr_from_dict(raw)
            if _closes_issue(mr, issue_iid):
                return mr
        return None
