from __future__ import annotations

import io
import re
import unittest
import urllib.error
from unittest.mock import patch

from release_notes import config
from release_notes.ado_client import ADOClient, BATCH_SIZE
from release_notes.generator import generate_all
from release_notes.gitlab_client import GitLabClient
from release_notes.models import Release, WorkItemType


def _live_client() -> ADOClient:
    return ADOClient(
        org_url="https://dev.azure.com/example",
        pat="secret",
        project="Project",
    )


def _release_item() -> dict:
    return {
        "id": 1001,
        "fields": {
            "System.Title": "Q3 Platform Release v4.2.0",
            "System.State": "Done",
            "System.Description": "Major platform release",
            "Custom.Version": "4.2.0",
            "Microsoft.VSTS.Scheduling.TargetDate": "2026-07-15T00:00:00Z",
        },
        "relations": [],
        "_links": {"html": {"href": "https://dev.azure.com/example/Project/_workitems/edit/1001"}},
    }


def _test_task_item() -> dict:
    return {
        "id": 2001,
        "fields": {
            "System.WorkItemType": "Test Task",
            "System.Title": "Validate new dashboard widgets",
            "System.State": "Passed",
        },
        "relations": [
            {
                "rel": "System.LinkTypes.Hierarchy-Forward",
                "url": "https://dev.azure.com/example/Project/_apis/wit/workItems/3001",
            },
            {
                "rel": "System.LinkTypes.Hierarchy-Forward",
                "url": "https://dev.azure.com/example/Project/_apis/wit/workItems/3002",
            },
        ],
    }


def _story_item(parent_id: int = 200) -> dict:
    return {
        "id": 3001,
        "fields": {
            "System.WorkItemType": "User Story",
            "System.Title": "Add revenue chart widget to dashboard",
            "System.State": "Done",
            "System.Description": "As a user I want a revenue chart widget",
            "System.AssignedTo": {"displayName": "Alice Chen", "uniqueName": "alice@example.com"},
            "System.IterationPath": r"Q3 Platform\Sprint 1",
            "System.AreaPath": r"Platform\Dashboard",
            "Microsoft.VSTS.Common.Priority": 1,
            "System.Tags": "dashboard; frontend; analytics",
            "Custom.RTCItem": "RTC-4821",
        },
        "relations": [
            {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"https://dev.azure.com/example/Project/_apis/wit/workItems/{parent_id}",
            }
        ],
        "_links": {"html": {"href": "https://dev.azure.com/example/Project/_workitems/edit/3001"}},
    }


def _bug_item() -> dict:
    return {
        "id": 3002,
        "fields": {
            "System.WorkItemType": "Bug",
            "System.Title": "Dashboard flicker on dark mode toggle",
            "System.State": "Active",
            "System.Description": "Flickers when toggling dark mode.",
            "System.AssignedTo": {"uniqueName": "bob@example.com"},
            "Microsoft.VSTS.Common.Priority": 2,
            "Microsoft.VSTS.Common.Severity": "High",
            "System.Tags": "dashboard; bug",
        },
        "relations": [
            {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": "https://dev.azure.com/example/Project/_apis/wit/workItems/200",
            }
        ],
        "_links": {"html": {"href": "https://dev.azure.com/example/Project/_workitems/edit/3002"}},
    }


def _feature_item() -> dict:
    return {
        "id": 200,
        "fields": {
            "System.WorkItemType": "Feature",
            "System.Title": "Dashboard V2 Widget Suite",
            "System.State": "Done",
        },
        "relations": [
            {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": "https://dev.azure.com/example/Project/_apis/wit/workItems/100",
            }
        ],
        "_links": {"html": {"href": "https://dev.azure.com/example/Project/_workitems/edit/200"}},
    }


def _epic_item() -> dict:
    return {
        "id": 100,
        "fields": {
            "System.WorkItemType": "Epic",
            "System.Title": "Platform UX Modernization",
            "System.State": "In Progress",
        },
        "_links": {"html": {"href": "https://dev.azure.com/example/Project/_workitems/edit/100"}},
    }


def _fake_api() -> object:
    def fake(method: str, path: str, body: dict | None = None):
        if method == "POST":
            return {
                "workItems": [
                    {
                        "id": 2001,
                        "url": "https://dev.azure.com/example/Project/_apis/wit/workItems/2001",
                    }
                ]
            }
        if path.startswith("/wit/workitems/1001"):
            return _release_item()
        ids = [int(x) for x in re.search(r"ids=([\d,]+)", path).group(1).split(",")]
        mapping = {
            2001: _test_task_item(),
            3001: _story_item(),
            3002: _bug_item(),
            200: _feature_item(),
            100: _epic_item(),
        }
        return {"count": len(ids), "value": [mapping[i] for i in ids if i in mapping]}

    return fake


class ADOLiveFetchTests(unittest.TestCase):
    def test_get_release_by_id_builds_full_hierarchy(self) -> None:
        client = _live_client()
        with patch.object(ADOClient, "_request", side_effect=_fake_api()):
            release = client.get_release_by_id(1001)

        self.assertIsInstance(release, Release)
        self.assertEqual(release.id, 1001)
        self.assertEqual(release.title, "Q3 Platform Release v4.2.0")
        self.assertEqual(release.version, "4.2.0")
        self.assertEqual(release.release_date, "2026-07-15")
        self.assertEqual(release.description, "Major platform release")

        self.assertEqual(len(release.test_tasks), 1)
        task = release.test_tasks[0]
        self.assertEqual(task.id, 2001)
        self.assertEqual(task.title, "Validate new dashboard widgets")
        self.assertEqual(task.state, "Passed")
        self.assertEqual(len(task.linked_work_items), 2)

        story, bug = task.linked_work_items
        self.assertEqual(story.id, 3001)
        self.assertEqual(story.work_item_type, WorkItemType.USER_STORY)
        self.assertEqual(story.title, "Add revenue chart widget to dashboard")
        self.assertEqual(story.state, "Done")
        self.assertEqual(story.description, "As a user I want a revenue chart widget")
        self.assertEqual(story.assigned_to, "Alice Chen")
        self.assertEqual(story.iteration_path, r"Q3 Platform\Sprint 1")
        self.assertEqual(story.area_path, r"Platform\Dashboard")
        self.assertEqual(story.priority, 1)
        self.assertEqual(story.tags, ["dashboard", "frontend", "analytics"])
        self.assertEqual(story.rtc_item, "RTC-4821")
        self.assertIsNotNone(story.parent_feature)
        assert story.parent_feature is not None
        self.assertEqual(story.parent_feature.id, 200)
        self.assertEqual(story.parent_feature.work_item_type, WorkItemType.FEATURE)
        self.assertEqual(story.parent_feature.title, "Dashboard V2 Widget Suite")
        self.assertEqual(story.parent_feature.state, "Done")
        self.assertIsNotNone(story.parent_epic)
        assert story.parent_epic is not None
        self.assertEqual(story.parent_epic.id, 100)
        self.assertEqual(story.parent_epic.work_item_type, WorkItemType.EPIC)
        self.assertEqual(story.parent_epic.title, "Platform UX Modernization")

        self.assertEqual(bug.id, 3002)
        self.assertEqual(bug.work_item_type, WorkItemType.BUG)
        self.assertEqual(bug.assigned_to, "bob@example.com")
        self.assertEqual(bug.priority, 2)
        self.assertEqual(bug.severity, "High")
        self.assertEqual(bug.tags, ["dashboard", "bug"])
        self.assertIsNotNone(bug.parent_feature)
        self.assertIsNotNone(bug.parent_epic)

    def test_version_falls_back_to_title_when_no_custom_field(self) -> None:
        client = _live_client()
        release_item = _release_item()
        del release_item["fields"]["Custom.Version"]

        def fake(method, path, body=None):
            if method == "POST":
                return {"workItems": []}
            if path.startswith("/wit/workitems/1001"):
                return release_item
            raise AssertionError(f"unexpected request: {path}")

        with patch.object(ADOClient, "_request", side_effect=fake):
            release = client.get_release_by_id(1001)
        self.assertEqual(release.version, "4.2.0")
        self.assertEqual(release.release_date, "2026-07-15")
        self.assertEqual(release.test_tasks, [])

    def test_story_linked_directly_to_epic_skips_feature(self) -> None:
        client = _live_client()
        story = _story_item(parent_id=100)

        def fake(method, path, body=None):
            if method == "POST":
                return {"workItems": [{"id": 2001, "url": "..."}]}
            if path.startswith("/wit/workitems/1001"):
                return _release_item()
            ids = [int(x) for x in re.search(r"ids=([\d,]+)", path).group(1).split(",")]
            mapping = {
                2001: _test_task_item(),
                3001: story,
                3002: _bug_item(),
                100: _epic_item(),
            }
            return {"count": len(ids), "value": [mapping[i] for i in ids if i in mapping]}

        with patch.object(ADOClient, "_request", side_effect=fake):
            release = client.get_release_by_id(1001)
        story_model = release.test_tasks[0].linked_work_items[0]
        self.assertIsNone(story_model.parent_feature)
        self.assertIsNotNone(story_model.parent_epic)
        assert story_model.parent_epic is not None
        self.assertEqual(story_model.parent_epic.id, 100)

    def test_work_item_without_rtc_field_has_empty_rtc_item(self) -> None:
        client = _live_client()
        story = _story_item()
        del story["fields"]["Custom.RTCItem"]

        def fake(method, path, body=None):
            if method == "POST":
                return {"workItems": [{"id": 2001, "url": "..."}]}
            if path.startswith("/wit/workitems/1001"):
                return _release_item()
            ids = [int(x) for x in re.search(r"ids=([\d,]+)", path).group(1).split(",")]
            mapping = {2001: _test_task_item(), 3001: story, 3002: _bug_item(), 200: _feature_item(), 100: _epic_item()}
            return {"count": len(ids), "value": [mapping[i] for i in ids if i in mapping]}

        with patch.object(ADOClient, "_request", side_effect=fake):
            release = client.get_release_by_id(1001)
        self.assertEqual(release.test_tasks[0].linked_work_items[0].rtc_item, "")


class ADOHttpErrorTests(unittest.TestCase):
    def test_http_error_raises_runtime_error_with_message(self) -> None:
        client = _live_client()
        error = urllib.error.HTTPError(
            "https://dev.azure.com/example/Project/_apis/wit/workitems/1001",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"message": "access denied"}'),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "ADO API error 401: access denied"):
                client.get_release_by_id(1001)

    def test_connection_error_raises_runtime_error(self) -> None:
        client = _live_client()
        error = urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "ADO API connection error"):
                client.get_release_by_id(1001)


class ADOBatchTests(unittest.TestCase):
    def test_batch_fetch_chunks_at_200_items(self) -> None:
        client = _live_client()
        calls: list[str] = []

        def fake(method, path, body=None):
            calls.append(path)
            ids = [int(x) for x in re.search(r"ids=([\d,]+)", path).group(1).split(",")]
            return {"value": [{"id": i, "fields": {"System.Title": "t"}} for i in ids]}

        with patch.object(ADOClient, "_request", side_effect=fake):
            items = client._batch_get_work_items(list(range(1, BATCH_SIZE + 51)))
        self.assertEqual(len(items), BATCH_SIZE + 50)
        self.assertEqual(len(calls), 2)

    def test_project_with_spaces_is_url_encoded(self) -> None:
        client = ADOClient(
            org_url="https://dev.azure.com/example",
            pat="secret",
            project="Platform Team",
        )
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = urllib.error.HTTPError(
                "url", 404, "Not Found", {}, io.BytesIO(b'{"message": "not found"}')
            )
            with self.assertRaises(RuntimeError):
                client.get_release_by_id(1001)
        requested = urlopen.call_args.args[0].full_url
        self.assertIn("Platform%20Team", requested)


class GeneratorLiveErrorTests(unittest.TestCase):
    def test_configured_client_api_error_propagates(self) -> None:
        client = _live_client()
        with patch.object(
            ADOClient, "_request", side_effect=RuntimeError("ADO API error 500: boom")
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                generate_all(
                    1001,
                    ado_client=client,
                    gl_client=GitLabClient(use_mock=True),
                )

    def test_unconfigured_client_falls_back_to_mock(self) -> None:
        with patch.object(config, "ADO_ORG_URL", return_value=""), \
                patch.object(config, "ADO_PAT", return_value=""), \
                patch.object(config, "ADO_PROJECT", return_value=""):
            client = ADOClient()
        _, _, _, release = generate_all(
            1001,
            ado_client=client,
            gl_client=GitLabClient(use_mock=True),
        )
        self.assertEqual(release.id, 1001)


if __name__ == "__main__":
    unittest.main()
