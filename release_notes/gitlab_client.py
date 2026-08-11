from __future__ import annotations

from release_notes import config
from release_notes.models import GitLabIssue, GitLabMergeRequest, extract_ado_id


class GitLabClient:
    """GitLab client with an explicit opt-in mock mode.

    Searches GitLab for issues and merge requests linked to ADO work items.
    Follows the team convention of placing the ADO work-item URL in the
    GitLab issue description body.

    Credentials are read from environment variables or a .env file:

        GITLAB_BASE_URL       — https://gitlab.example.com
        GITLAB_PRIVATE_TOKEN  — personal or project access token

    Set ``use_mock=True`` to use the bundled mock index without credentials."""

    def __init__(self, base_url: str = "", private_token: str = "", *, use_mock: bool = False):
        self._use_mock = use_mock
        if use_mock:
            if any((base_url, private_token)):
                raise ValueError("Mock mode cannot be combined with GitLab credentials.")
            self._base_url = ""
            self._private_token = ""
            return

        self._base_url = base_url or config.GITLAB_BASE_URL()
        self._private_token = private_token or config.GITLAB_PRIVATE_TOKEN()

    def __repr__(self) -> str:
        return (
            f"GitLabClient(base_url={self._base_url!r}, "
            f"private_token={'***' if self._private_token else 'unset'}, "
            f"use_mock={self._use_mock!r})"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._private_token)

    def find_issue_by_ado_id(self, ado_work_item_id: int) -> GitLabIssue | None:
        """Return the GitLab issue whose description contains a link to the
        given ADO work item.  Handles all URL variants (standard, sprint
        board, board view, bare suffix)."""
        if self.is_configured:
            raise NotImplementedError("GitLab REST API not yet implemented")
        from release_notes.mock_data import MOCK_GITLAB_ISSUES_BY_ADO_ID
        for issue in MOCK_GITLAB_ISSUES_BY_ADO_ID.values():
            if extract_ado_id(issue.description) == ado_work_item_id:
                return issue
        return None

    def find_mr_for_issue(self, issue_iid: int) -> GitLabMergeRequest | None:
        """Return the merge request that closes the given GitLab issue."""
        if self.is_configured:
            raise NotImplementedError("GitLab REST API not yet implemented")
        from release_notes.mock_data import MOCK_GITLAB_MRS_BY_ISSUE_IID
        return MOCK_GITLAB_MRS_BY_ISSUE_IID.get(issue_iid)
