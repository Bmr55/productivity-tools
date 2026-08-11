from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes import config
from release_notes.ado_client import ADOClient
from release_notes.formatters._escape import sanitize_text
from release_notes.formatters.csv import _safe, generate_csv
from release_notes.formatters.html import generate_html
from release_notes.formatters.markdown import generate_markdown
from release_notes.generator import _release_id_component, _sanitize, export
from release_notes.models import (
    GitLabIssue,
    GitLabMergeRequest,
    Release,
    TestTask,
    WorkItem,
    WorkItemType,
)


class CsvSecurityTests(unittest.TestCase):
    def test_all_formula_prefixes_and_leading_whitespace_are_sanitized(self) -> None:
        for value in ("=x", "+x", "-x", "@x", "\t=x", "\r=x", "  =x"):
            with self.subTest(value=repr(value)):
                self.assertTrue(_safe(value).startswith("'"))

    def test_every_csv_field_is_formula_sanitized(self) -> None:
        formula = "=FORMULA_TEST()"
        issue = GitLabIssue(
            id=formula,
            iid=formula,
            title=formula,
            description="",
            state="closed",
            web_url="https://gitlab.example.test/issue",
        )
        merge_request = GitLabMergeRequest(
            id=formula,
            iid=formula,
            title=formula,
            description="",
            state="merged",
            web_url="https://gitlab.example.test/mr",
        )
        work_item = WorkItem(
            id=formula,
            title=formula,
            work_item_type=WorkItemType.BUG,
            state="Done",
            priority=formula,
            gitlab_issue=issue,
            gitlab_mr=merge_request,
        )
        release = Release(
            id=formula,
            title=formula,
            version="1",
            test_tasks=[
                TestTask(
                    id=formula,
                    title="Task",
                    state="Done",
                    linked_work_items=[work_item],
                )
            ],
        )

        row = list(csv.reader(io.StringIO(generate_csv(release))))[1]

        for index in (0, 1, 4, 7, 8, 13, 25, 26, 27, 30, 31, 32):
            with self.subTest(column=index):
                self.assertTrue(row[index].startswith("'="))


class ControlCharacterTests(unittest.TestCase):
    def test_all_formats_remove_terminal_controls(self) -> None:
        malicious = "before\x1b]52;c;payload\x07after\x85"
        work_item = WorkItem(
            id=1,
            title=malicious,
            work_item_type=WorkItemType.BUG,
            state="Done",
        )
        release = Release(
            id=1,
            title=malicious,
            version="1",
            test_tasks=[
                TestTask(
                    id=1,
                    title=malicious,
                    state="Done",
                    linked_work_items=[work_item],
                )
            ],
        )

        for output in (
            generate_markdown(release),
            generate_html(release),
            generate_csv(release),
        ):
            with self.subTest(format=output[:15]):
                self.assertNotIn("\x1b", output)
                self.assertNotIn("\x07", output)
                self.assertNotIn("\x85", output)

    def test_carriage_returns_are_normalized(self) -> None:
        self.assertEqual(sanitize_text("one\r\ntwo\rthree"), "one\ntwo\nthree")

    def test_all_c0_and_c1_controls_are_removed_except_tab_and_newline(self) -> None:
        controls = "".join(chr(value) for value in (*range(32), *range(127, 160)))
        sanitized = sanitize_text(controls)
        self.assertEqual(sanitized, "\t\n\n")


class ADOConfigurationTests(unittest.TestCase):
    def _empty_config(self):
        return (
            patch.object(config, "ADO_ORG_URL", return_value=""),
            patch.object(config, "ADO_PAT", return_value=""),
            patch.object(config, "ADO_PROJECT", return_value=""),
        )

    def test_missing_credentials_do_not_fall_back_to_mock(self) -> None:
        org_patch, pat_patch, project_patch = self._empty_config()
        with org_patch, pat_patch, project_patch:
            client = ADOClient()
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            client.get_release_by_id(1001)

    def test_partial_credentials_are_rejected(self) -> None:
        org_patch, pat_patch, project_patch = self._empty_config()
        with org_patch, pat_patch, project_patch:
            with self.assertRaisesRegex(ValueError, "Partial Azure DevOps"):
                ADOClient(org_url="https://dev.azure.com/example")

    def test_mock_mode_is_explicit_and_id_checked(self) -> None:
        client = ADOClient(use_mock=True)
        self.assertTrue(client.is_mock)
        self.assertEqual(client.get_release_by_id(1001).id, 1001)
        with self.assertRaisesRegex(ValueError, "only mock release"):
            client.get_release_by_id(999999)

    def test_complete_credentials_never_fall_back_to_mock(self) -> None:
        client = ADOClient(
            org_url="https://dev.azure.com/example",
            pat="secret",
            project="Project",
        )
        self.assertTrue(client.is_configured)
        with self.assertRaisesRegex(NotImplementedError, "not yet implemented"):
            client.get_release_by_id(1001)


class ExportPathTests(unittest.TestCase):
    def test_slug_is_bounded_and_avoids_windows_device_names(self) -> None:
        self.assertEqual(_sanitize("CON"), "_con")
        self.assertEqual(_sanitize("ＣＯＮ"), "_con")
        self.assertEqual(len(_sanitize("A" * 300)), 80)
        self.assertLessEqual(len(_sanitize("𐐀" * 300).encode("utf-8")), 200)

    def test_release_id_must_be_a_bounded_positive_integer(self) -> None:
        for invalid in (True, 0, -1, "../escape", 2**63):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    _release_id_component(invalid)

    def test_export_directory_includes_release_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = export(1001, base_dir=temp_dir, ado_client=ADOClient(use_mock=True))
            self.assertEqual(paths[0].parent.name, "q3_platform_release_v420_1001")
            self.assertTrue(all(Path(path).is_file() for path in paths))


if __name__ == "__main__":
    unittest.main()
