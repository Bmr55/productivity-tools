from __future__ import annotations

import copy
import json
import re
import urllib.error
import urllib.request
from base64 import b64encode
from urllib.parse import quote

from release_notes import config
from release_notes.mock_data import MOCK_RELEASE
from release_notes.models import (
    RTC_FIELD_KEY,
    ParentWorkItem,
    Release,
    TestTask,
    WorkItem,
    WorkItemType,
)

API_VERSION = "7.0"
LINK_HIERARCHY_FORWARD = "System.LinkTypes.Hierarchy-Forward"
LINK_HIERARCHY_REVERSE = "System.LinkTypes.Hierarchy-Reverse"
BATCH_SIZE = 200
_ID_FROM_URL_RE = re.compile(r"/(\d+)(?:[?#]|$)")


class ADOClient:
    """Azure DevOps client with an explicit opt-in mock mode.

    Credentials are read from environment variables or a .env file in the
    release_notes/ directory:

        ADO_ORG_URL    — https://dev.azure.com/your-org
        ADO_PAT        — personal access token
        ADO_PROJECT    — team project name

    Pass values directly to override auto-detection. Set ``use_mock=True`` to
    use the bundled fixture without reading credentials."""

    def __init__(
        self,
        org_url: str = "",
        pat: str = "",
        project: str = "",
        *,
        use_mock: bool = False,
    ):
        self._use_mock = use_mock
        if use_mock:
            if any((org_url, pat, project)):
                raise ValueError("Mock mode cannot be combined with ADO credentials.")
            self._org_url = ""
            self._pat = ""
            self._project = ""
            return

        self._org_url = org_url or config.ADO_ORG_URL()
        self._pat = pat or config.ADO_PAT()
        self._project = project or config.ADO_PROJECT()

        configured = {
            "ADO_ORG_URL": self._org_url,
            "ADO_PAT": self._pat,
            "ADO_PROJECT": self._project,
        }
        if any(configured.values()) and not all(configured.values()):
            missing = ", ".join(key for key, value in configured.items() if not value)
            raise ValueError(f"Partial Azure DevOps configuration; missing: {missing}.")

    def __repr__(self) -> str:
        return (
            f"ADOClient(org_url={self._org_url!r}, "
            f"pat={'***' if self._pat else 'unset'}, "
            f"project={self._project!r}, use_mock={self._use_mock!r})"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._org_url and self._pat and self._project)

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    # --- HTTP plumbing ---------------------------------------------------

    def _auth_header(self) -> str:
        return f"Basic {b64encode(f':{self._pat}'.encode()).decode()}"

    def _ado_url(self, path: str) -> str:
        org = self._org_url.rstrip("/")
        project = quote(self._project, safe="")
        return f"{org}/{project}/_apis{path}"

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | list:
        url = self._ado_url(path)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self._auth_header())
        req.add_header("Accept", "application/json")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(body_text).get("message", body_text)
            except Exception:
                msg = body_text
            raise RuntimeError(f"ADO API error {e.code}: {msg}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"ADO API connection error: {e.reason}") from None

    def _get_work_item(self, work_item_id: int) -> dict:
        return self._request(
            "GET",
            f"/wit/workitems/{work_item_id}?$expand=relations&api-version={API_VERSION}",
        )

    def _batch_get_work_items(self, ids: list[int]) -> list[dict]:
        results: list[dict] = []
        for i in range(0, len(ids), BATCH_SIZE):
            chunk = ids[i : i + BATCH_SIZE]
            resp = self._request(
                "GET",
                f"/wit/workitems?ids={','.join(map(str, chunk))}"
                f"&$expand=relations&api-version={API_VERSION}",
            )
            results.extend(resp.get("value", []))
        return results

    def _find_test_task_ids(self, release_id: int) -> list[int]:
        result = self._request(
            "POST",
            f"/wit/wiql?api-version={API_VERSION}",
            {
                "query": (
                    "SELECT [System.Id] FROM workitems "
                    f"WHERE [System.WorkItemType] = 'Test Task' "
                    f"AND [System.Parent] = {release_id} "
                    "ORDER BY [System.Id]"
                )
            },
        )
        return [ref["id"] for ref in result.get("workItems", [])]

    # --- Mapping helpers ---------------------------------------------------

    @staticmethod
    def _extract_id_from_url(url: str) -> int | None:
        match = _ID_FROM_URL_RE.search(url)
        return int(match.group(1)) if match else None

    @staticmethod
    def _work_item_type(item: dict) -> str:
        return ((item.get("fields") or {}).get("System.WorkItemType") or "").lower()

    @staticmethod
    def _display_name(field: object) -> str:
        if not field:
            return ""
        if isinstance(field, str):
            return field
        if isinstance(field, dict):
            return field.get("displayName") or field.get("uniqueName") or ""
        return ""

    @staticmethod
    def _child_ids(item: dict) -> list[int]:
        ids: list[int] = []
        for rel in item.get("relations", []):
            if rel.get("rel") != LINK_HIERARCHY_FORWARD:
                continue
            cid = ADOClient._extract_id_from_url(rel.get("url", ""))
            if cid:
                ids.append(cid)
        return ids

    @staticmethod
    def _custom_fields(fields: dict) -> dict[str, str]:
        """Collect ADO custom fields ("Custom.*"), and expose the RTC field
        (if present under any name) under the canonical "RTC Item" key."""
        custom: dict[str, str] = {}
        for name, value in fields.items():
            if not name.startswith("Custom."):
                continue
            custom[name[len("Custom.") :]] = "" if value is None else str(value)
        if RTC_FIELD_KEY not in custom:
            for key, value in custom.items():
                if "rtc" in key.lower():
                    custom[RTC_FIELD_KEY] = value
                    break
        return custom

    @staticmethod
    def _release_version(fields: dict, title: str) -> str:
        for name, value in fields.items():
            if name.lower().endswith("version") and value:
                return str(value)
        match = re.search(r"\bv?(\d+\.\d+(?:\.\d+)?)", title or "")
        return match.group(1) if match else ""

    @staticmethod
    def _release_date(fields: dict) -> str:
        for name, value in fields.items():
            if "release date" in name.lower() and value:
                return str(value)[:10]
        target_date = fields.get("Microsoft.VSTS.Scheduling.TargetDate")
        return str(target_date)[:10] if target_date else ""

    def _parent_work_item(self, item: dict) -> ParentWorkItem:
        fields = item.get("fields") or {}
        raw_type = fields.get("System.WorkItemType", "")
        work_item_type = (
            WorkItemType.FEATURE if raw_type.lower() == "feature" else WorkItemType.EPIC
        )
        return ParentWorkItem(
            id=item["id"],
            title=fields.get("System.Title", ""),
            work_item_type=work_item_type,
            state=fields.get("System.State", ""),
            url=item.get("_links", {}).get("html", {}).get("href", ""),
        )

    def _resolve_parents(
        self, item: dict, all_items: dict[int, dict]
    ) -> tuple[ParentWorkItem | None, ParentWorkItem | None]:
        """Resolve the parent Feature and grandparent Epic of a work item by
        walking Hierarchy-Reverse relations."""
        parent_feature: ParentWorkItem | None = None
        parent_epic: ParentWorkItem | None = None
        feature_item: dict | None = None
        for rel in item.get("relations", []):
            if rel.get("rel") != LINK_HIERARCHY_REVERSE:
                continue
            pid = self._extract_id_from_url(rel.get("url", ""))
            parent = all_items.get(pid) if pid else None
            if not parent:
                continue
            ptype = self._work_item_type(parent)
            if ptype == "feature" and parent_feature is None:
                parent_feature = self._parent_work_item(parent)
                feature_item = parent
            elif ptype == "epic" and parent_epic is None:
                parent_epic = self._parent_work_item(parent)
        if feature_item is not None and parent_epic is None:
            for rel in feature_item.get("relations", []):
                if rel.get("rel") != LINK_HIERARCHY_REVERSE:
                    continue
                gid = self._extract_id_from_url(rel.get("url", ""))
                grandparent = all_items.get(gid) if gid else None
                if grandparent and self._work_item_type(grandparent) == "epic":
                    parent_epic = self._parent_work_item(grandparent)
                    break
        return parent_feature, parent_epic

    def _build_work_item(self, item: dict, all_items: dict[int, dict]) -> WorkItem:
        fields = item.get("fields") or {}
        raw_type = fields.get("System.WorkItemType", "")
        work_item_type = (
            WorkItemType.USER_STORY if raw_type.lower() == "user story" else WorkItemType.BUG
        )
        try:
            priority = int(fields.get("Microsoft.VSTS.Common.Priority", 0))
        except (TypeError, ValueError):
            priority = 0
        tags = [
            tag.strip()
            for tag in str(fields.get("System.Tags", "")).split(";")
            if tag.strip()
        ]
        parent_feature, parent_epic = self._resolve_parents(item, all_items)
        return WorkItem(
            id=item["id"],
            title=fields.get("System.Title", ""),
            work_item_type=work_item_type,
            state=fields.get("System.State", ""),
            description=fields.get("System.Description") or "",
            assigned_to=self._display_name(fields.get("System.AssignedTo")),
            iteration_path=fields.get("System.IterationPath", ""),
            area_path=fields.get("System.AreaPath", ""),
            priority=priority,
            severity=fields.get("Microsoft.VSTS.Common.Severity") or "",
            tags=tags,
            custom_fields=self._custom_fields(fields),
            parent_feature=parent_feature,
            parent_epic=parent_epic,
        )

    def _fetch_release(self, release_id: int) -> Release:
        release_item = self._get_work_item(release_id)
        fields = release_item.get("fields") or {}

        test_task_ids = self._find_test_task_ids(release_id)

        all_items: dict[int, dict] = {release_id: release_item}
        for item in self._batch_get_work_items(test_task_ids):
            all_items[item["id"]] = item

        child_ids: set[int] = set()
        for wid in test_task_ids:
            child_ids.update(self._child_ids(all_items.get(wid, {})))
        for item in self._batch_get_work_items(sorted(child_ids)):
            all_items[item["id"]] = item

        story_or_bug_ids = {
            cid
            for cid in child_ids
            if cid in all_items and self._work_item_type(all_items[cid]) in ("user story", "bug")
        }

        parent_ids: set[int] = set()
        for cid in story_or_bug_ids:
            for rel in all_items[cid].get("relations", []):
                if rel.get("rel") == LINK_HIERARCHY_REVERSE:
                    pid = self._extract_id_from_url(rel.get("url", ""))
                    if pid:
                        parent_ids.add(pid)
        for item in self._batch_get_work_items(sorted(parent_ids)):
            all_items[item["id"]] = item

        grandparent_ids: set[int] = set()
        for pid in parent_ids:
            parent = all_items.get(pid)
            if not parent or self._work_item_type(parent) != "feature":
                continue
            for rel in parent.get("relations", []):
                if rel.get("rel") == LINK_HIERARCHY_REVERSE:
                    gid = self._extract_id_from_url(rel.get("url", ""))
                    if gid:
                        grandparent_ids.add(gid)
        for item in self._batch_get_work_items(sorted(grandparent_ids)):
            all_items[item["id"]] = item

        test_tasks: list[TestTask] = []
        for wid in test_task_ids:
            task = all_items.get(wid, {})
            task_fields = task.get("fields") or {}
            linked = [
                self._build_work_item(all_items[cid], all_items)
                for cid in self._child_ids(task)
                if cid in all_items and self._work_item_type(all_items[cid]) in ("user story", "bug")
            ]
            test_tasks.append(
                TestTask(
                    id=wid,
                    title=task_fields.get("System.Title", ""),
                    state=task_fields.get("System.State", ""),
                    linked_work_items=linked,
                )
            )

        title = fields.get("System.Title", "")
        return Release(
            id=release_id,
            title=title,
            version=self._release_version(fields, title),
            release_date=self._release_date(fields),
            description=fields.get("System.Description") or "",
            test_tasks=test_tasks,
        )

    def get_release_by_id(self, release_id: int) -> Release:
        if self._use_mock:
            if release_id != MOCK_RELEASE.id:
                raise ValueError(
                    f"No mock data for release {release_id}. "
                    f"The only mock release available is ID {MOCK_RELEASE.id}."
                )
            return copy.deepcopy(MOCK_RELEASE)
        if not self.is_configured:
            raise RuntimeError(
                "Azure DevOps credentials are not configured. "
                "Configure all ADO settings or explicitly enable mock mode."
            )
        return self._fetch_release(release_id)
