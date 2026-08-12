from __future__ import annotations

import unittest
from unittest.mock import patch

from release_notes import config
from release_notes.gitlab_client import GitLabClient, _closes_issue
from release_notes.models import GitLabMergeRequest


def _live_client(project_id: str = "") -> GitLabClient:
    return GitLabClient(
        base_url="https://gitlab.example.com",
        private_token="secret",
        project_id=project_id,
    )


class GitLabConfigurationTests(unittest.TestCase):
    def _empty_config(self):
        return (
            patch.object(config, "GITLAB_BASE_URL", return_value=""),
            patch.object(config, "GITLAB_PRIVATE_TOKEN", return_value=""),
            patch.object(config, "GITLAB_PROJECT_ID", return_value=""),
        )

    def test_missing_credentials_do_not_fall_back_to_mock(self) -> None:
        base_patch, token_patch, project_patch = self._empty_config()
        with base_patch, token_patch, project_patch:
            client = GitLabClient()
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            client.find_issue_by_ado_id(3001)
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            client.find_mr_for_issue(12)

    def test_partial_credentials_are_rejected(self) -> None:
        base_patch, token_patch, project_patch = self._empty_config()
        with base_patch, token_patch, project_patch:
            with self.assertRaisesRegex(ValueError, "Partial GitLab"):
                GitLabClient(base_url="https://gitlab.example.com")

    def test_mock_mode_is_explicit(self) -> None:
        client = GitLabClient(use_mock=True)
        self.assertTrue(client.is_mock)
        self.assertFalse(client.is_configured)

    def test_mock_mode_cannot_combine_with_credentials(self) -> None:
        for kwargs in (
            {"base_url": "https://gitlab.example.com"},
            {"private_token": "secret"},
            {"project_id": "group/project"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "Mock mode"):
                    GitLabClient(use_mock=True, **kwargs)

    def test_mock_mode_resolves_mock_issue_and_mr(self) -> None:
        client = GitLabClient(use_mock=True)
        issue = client.find_issue_by_ado_id(3001)
        self.assertIsNotNone(issue)
        assert issue is not None
        self.assertEqual(issue.iid, 12)
        self.assertIsNone(client.find_issue_by_ado_id(999999))
        mr = client.find_mr_for_issue(12)
        self.assertIsNotNone(mr)
        assert mr is not None
        self.assertEqual(mr.iid, 34)
        self.assertIsNone(client.find_mr_for_issue(999999))


class GitLabIssueLookupTests(unittest.TestCase):
    def test_find_issue_filters_candidates_by_exact_ado_id(self) -> None:
        client = _live_client()
        payload = [
            {
                "id": 1,
                "iid": 12,
                "title": "Unrelated issue",
                "description": "ADO: https://dev.azure.com/org/project/_workitems/edit/9999",
                "state": "opened",
                "web_url": "https://gitlab.example.com/group/proj/-/issues/12",
                "labels": [],
                "milestone": None,
            },
            {
                "id": 2,
                "iid": 13,
                "title": "Revenue chart widget",
                "description": "ADO: https://dev.azure.com/org/project/_workitems/edit/3001",
                "state": "closed",
                "web_url": "https://gitlab.example.com/group/proj/-/issues/13",
                "labels": ["frontend", "dashboard"],
                "milestone": {"title": "Q3 Sprint 1"},
            },
        ]
        with patch.object(GitLabClient, "_request_pages", return_value=payload) as pages:
            issue = client.find_issue_by_ado_id(3001)
        self.assertIsNotNone(issue)
        assert issue is not None
        self.assertEqual(issue.iid, 13)
        self.assertEqual(issue.title, "Revenue chart widget")
        self.assertEqual(issue.state, "closed")
        self.assertEqual(issue.labels, ["frontend", "dashboard"])
        self.assertEqual(issue.milestone, "Q3 Sprint 1")
        pages.assert_called_once()
        call_args = pages.call_args
        self.assertEqual(call_args.args[0], "/issues")
        self.assertEqual(call_args.args[1]["search"], "3001")

    def test_find_issue_returns_none_when_no_match(self) -> None:
        client = _live_client()
        payload = [
            {
                "id": 1,
                "iid": 12,
                "title": "Unrelated issue",
                "description": "No ADO link here.",
                "state": "opened",
                "web_url": "https://gitlab.example.com/group/proj/-/issues/12",
                "labels": [],
                "milestone": None,
            }
        ]
        with patch.object(GitLabClient, "_request_pages", return_value=payload):
            self.assertIsNone(client.find_issue_by_ado_id(3001))

    def test_find_issue_scopes_to_configured_project(self) -> None:
        client = _live_client(project_id="group/proj")
        with patch.object(GitLabClient, "_request_pages", return_value=[]) as pages:
            self.assertIsNone(client.find_issue_by_ado_id(3001))
            self.assertEqual(pages.call_args.args[0], "/projects/group%2Fproj/issues")


class GitLabMrLookupTests(unittest.TestCase):
    def _mr_payload(self) -> dict:
        return {
            "id": 5,
            "iid": 40,
            "title": "feat: add revenue chart widget",
            "description": "Closes #13. Adds revenue chart.",
            "state": "merged",
            "web_url": "https://gitlab.example.com/group/proj/-/merge_requests/40",
            "source_branch": "feat/revenue-widget",
            "target_branch": "main",
            "author": {"name": "Alice Chen", "username": "alice"},
            "merged_at": "2026-07-02T14:30:00Z",
        }

    def test_find_mr_uses_cached_project_path_from_resolved_issue(self) -> None:
        client = _live_client()
        issue_payload = [
            {
                "id": 2,
                "iid": 13,
                "title": "Revenue chart widget",
                "description": "ADO: https://dev.azure.com/org/project/_workitems/edit/3001",
                "state": "closed",
                "web_url": "https://gitlab.example.com/group/proj/-/issues/13",
                "labels": [],
                "milestone": None,
            }
        ]
        with patch.object(
            GitLabClient, "_request_pages", side_effect=[issue_payload, [self._mr_payload()]]
        ) as pages:
            client.find_issue_by_ado_id(3001)
            mr = client.find_mr_for_issue(13)
        self.assertIsNotNone(mr)
        assert mr is not None
        self.assertEqual(mr.iid, 40)
        self.assertEqual(mr.source_branch, "feat/revenue-widget")
        self.assertEqual(mr.author, "Alice Chen")
        self.assertEqual(mr.merged_at, "2026-07-02T14:30:00Z")
        self.assertEqual(
            pages.call_args_list[1].args[0],
            "/projects/group%2Fproj/issues/13/related_merge_requests",
        )

    def test_find_mr_falls_back_to_global_search(self) -> None:
        client = _live_client()
        payload = [
            dict(self._mr_payload(), description="No keyword here, just a link to #13."),
            self._mr_payload(),
        ]
        with patch.object(GitLabClient, "_request_pages", side_effect=[payload]) as pages:
            mr = client.find_mr_for_issue(13)
            self.assertEqual(pages.call_args_list[0].args[0], "/merge_requests")
        self.assertIsNotNone(mr)
        assert mr is not None
        self.assertEqual(mr.iid, 40)

    def test_find_mr_returns_none_when_nothing_closes_the_issue(self) -> None:
        client = _live_client()
        with patch.object(GitLabClient, "_request_pages", return_value=[]):
            self.assertIsNone(client.find_mr_for_issue(13))


class ClosingKeywordTests(unittest.TestCase):
    def test_closing_keyword_variants_match(self) -> None:
        for description, iid in (
            ("Closes #12", 12),
            ("closes 12", 12),
            ("Closed #12.", 12),
            ("Closing #12", 12),
            ("Fixes #12", 12),
            ("fix #12", 12),
            ("fixed #12", 12),
            ("Resolves #12", 12),
            ("resolve 12", 12),
            ("resolved #12", 12),
            ("Resolving #12", 12),
        ):
            with self.subTest(description=description):
                mr = GitLabMergeRequest(
                    id=1, iid=1, title="t", description=description, state="merged", web_url=""
                )
                self.assertTrue(_closes_issue(mr, 12))

    def test_non_matching_issue_ids_do_not_match(self) -> None:
        for description in ("Closes #13", "Fixes 120", "No keyword at all", ""):
            with self.subTest(description=description):
                mr = GitLabMergeRequest(
                    id=1, iid=1, title="t", description=description, state="merged", web_url=""
                )
                self.assertFalse(_closes_issue(mr, 12))


class ProjectPathTests(unittest.TestCase):
    def test_project_path_extraction(self) -> None:
        self.assertEqual(
            GitLabClient._project_path_from_url(
                "https://gitlab.example.com/group/proj/-/issues/12"
            ),
            "group/proj",
        )
        self.assertEqual(
            GitLabClient._project_path_from_url(
                "https://gitlab.example.com/a/b/c/-/merge_requests/40"
            ),
            "a/b/c",
        )
        self.assertEqual(GitLabClient._project_path_from_url("not-a-url"), "")
        self.assertEqual(GitLabClient._project_path_from_url("https://gitlab.example.com"), "")


if __name__ == "__main__":
    unittest.main()
