"""
Export the ADO epic/feature/user-story/bug tree to JSON + self-contained HTML.

Usage:
    python release_notes/epic_tree_export.py          # live ADO (reads .env)
    python release_notes/epic_tree_export.py --mock   # use bundled fixture data

Outputs:
    release_notes/exports/epic_tree.json   — tree data
    release_notes/exports/epic_tree.html   — self-contained interactive page
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from base64 import b64encode
from pathlib import Path

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path and os.path.isdir(os.path.join(_parent, "release_notes")):
    sys.path.append(_parent)

from release_notes import config

API_VERSION = "7.0"
LINK_HIERARCHY_FORWARD = "System.LinkTypes.Hierarchy-Forward"
EXCLUDED_STATES = {"closed", "removed", "done"}

EXPORTS_DIR = Path(__file__).resolve().parent / "exports"
TEMPLATE_PATH = Path(__file__).resolve().parent / "epic_tree.html"


def _auth_header() -> str:
    pat = config.ADO_PAT()
    return f"Basic {b64encode(f':{pat}'.encode()).decode()}"


def _ado_url(path: str) -> str:
    org = config.ADO_ORG_URL().rstrip("/")
    project = config.ADO_PROJECT()
    return f"{org}/{project}/_apis{path}"


def ado_request(method: str, path: str, body: dict | None = None) -> dict | list:
    url = _ado_url(path)
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth_header())
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


def _extract_id_from_url(url: str) -> int | None:
    import re
    m = re.search(r"/(\d+)(?:[?#]|$)", url)
    return int(m.group(1)) if m else None


def _batch_get_work_items(ids: list[int]) -> list[dict]:
    results: list[dict] = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        resp = ado_request(
            "GET",
            f"/wit/workitems?ids={','.join(map(str, chunk))}&$expand=relations&api-version={API_VERSION}"
        )
        results.extend(resp.get("value", []))
    return results


def _html_url(wid: int) -> str:
    from urllib.parse import quote, unquote
    org = config.ADO_ORG_URL().rstrip("/")
    project = quote(unquote(config.ADO_PROJECT()), safe="")
    return f"{org}/{project}/_workitems/edit/{wid}"


def _display_name(field: object) -> str:
    if not field:
        return ""
    if isinstance(field, str):
        return field
    if isinstance(field, dict):
        return field.get("displayName", field.get("uniqueName", ""))
    return ""


def build_tree(use_mock: bool = False) -> list[dict]:
    if use_mock:
        return MOCK_EPIC_TREE

    # Step 1: WIQL query for open Epics
    print("Querying open Epics...")
    wiql_result = ado_request(
        "POST",
        f"/wit/wiql?api-version={API_VERSION}",
        {
            "query": (
                "SELECT [System.Id], [System.Title], [System.State] "
                "FROM workitems "
                "WHERE [System.WorkItemType] = 'Epic' "
                "AND [System.State] <> 'Closed' "
                "AND [System.State] <> 'Removed' "
                "ORDER BY [System.Title]"
            )
        }
    )
    epic_refs = wiql_result.get("workItems", [])
    if not epic_refs:
        print("No open Epics found.")
        return []

    epic_ids = [r["id"] for r in epic_refs]
    print(f"Found {len(epic_ids)} Epic(s).")

    # Step 2: Batch get Epic details with relations
    print("Fetching Epic details...")
    epic_items = _batch_get_work_items(epic_ids)

    all_items: dict[int, dict] = {}
    feature_ids: set[int] = set()
    direct_child_ids: set[int] = set()

    epic_id_set = set(epic_ids)
    parent_epic: dict[int, int | None] = {eid: None for eid in epic_ids}

    for item in epic_items:
        all_items[item["id"]] = item
        for rel in item.get("relations", []):
            if rel.get("rel") == LINK_HIERARCHY_FORWARD:
                cid = _extract_id_from_url(rel["url"])
                if not cid:
                    continue
                if cid in epic_id_set and cid != item["id"]:
                    parent_epic[cid] = item["id"]
                elif cid not in epic_id_set:
                    feature_ids.add(cid)

    # Step 3: Batch get Features
    feature_items: list[dict] = []
    if feature_ids:
        print(f"Fetching {len(feature_ids)} Feature(s)...")
        feature_items = _batch_get_work_items(list(feature_ids))
        for item in feature_items:
            all_items[item["id"]] = item
            item_type = (item.get("fields", {}).get("System.WorkItemType", "")).lower()
            if item_type == "feature":
                for rel in item.get("relations", []):
                    if rel.get("rel") == LINK_HIERARCHY_FORWARD:
                        cid = _extract_id_from_url(rel["url"])
                        if cid:
                            direct_child_ids.add(cid)

    # Also collect non-Feature direct children of Epics (excluding child Epics)
    for item in epic_items:
        for rel in item.get("relations", []):
            if rel.get("rel") == LINK_HIERARCHY_FORWARD:
                cid = _extract_id_from_url(rel["url"])
                if cid and cid not in feature_ids and cid not in epic_id_set:
                    direct_child_ids.add(cid)

    # Step 4: Batch get child User Stories/Bugs
    if direct_child_ids:
        print(f"Fetching {len(direct_child_ids)} child item(s)...")
        child_items = _batch_get_work_items(list(direct_child_ids))
        for item in child_items:
            all_items[item["id"]] = item

    # Step 5: Build tree nodes
    def _leaf_node(wid: int, wtype: str) -> dict:
        item = all_items.get(wid, {})
        fields = item.get("fields", {})
        return {
            "id": wid,
            "title": fields.get("System.Title", "(untitled)"),
            "type": "User Story" if wtype == "user story" else "Bug",
            "state": fields.get("System.State", ""),
            "assignedTo": _display_name(fields.get("System.AssignedTo")),
            "url": _html_url(wid),
            "children": [],
            "childStats": {"stories": 0, "bugs": 0},
        }

    def _feature_node(fid: int) -> dict:
        item = all_items.get(fid, {})
        fields = item.get("fields", {})
        children: list[dict] = []
        stats = {"stories": 0, "bugs": 0}
        for rel in item.get("relations", []):
            if rel.get("rel") != LINK_HIERARCHY_FORWARD:
                continue
            cid = _extract_id_from_url(rel["url"])
            if not cid or cid not in all_items:
                continue
            cfields = all_items[cid].get("fields", {})
            ctype = (cfields.get("System.WorkItemType", "")).lower()
            if ctype in ("user story", "bug"):
                children.append(_leaf_node(cid, ctype))
                if ctype == "user story":
                    stats["stories"] += 1
                else:
                    stats["bugs"] += 1
        return {
            "id": fid,
            "title": fields.get("System.Title", "(untitled)"),
            "type": "Feature",
            "state": fields.get("System.State", ""),
            "assignedTo": _display_name(fields.get("System.AssignedTo")),
            "url": _html_url(fid),
            "children": children,
            "childStats": stats,
        }

    def _epic_node(eid: int, visited: set[int]) -> dict:
        item = all_items.get(eid, {})
        fields = item.get("fields", {})
        sub_epics: list[dict] = []
        features: list[dict] = []
        direct_children: list[dict] = []
        stats = {"epics": 0, "features": 0, "stories": 0, "bugs": 0}
        for rel in item.get("relations", []):
            if rel.get("rel") != LINK_HIERARCHY_FORWARD:
                continue
            cid = _extract_id_from_url(rel["url"])
            if not cid or cid not in all_items:
                continue
            cfields = all_items[cid].get("fields", {})
            ctype = (cfields.get("System.WorkItemType", "")).lower()
            if ctype == "epic":
                if parent_epic.get(cid) == eid and cid not in visited:
                    sub = _epic_node(cid, visited | {cid})
                    sub_epics.append(sub)
                    stats["epics"] += 1 + sub["childStats"]["epics"]
                    stats["features"] += sub["childStats"]["features"]
                    stats["stories"] += sub["childStats"]["stories"]
                    stats["bugs"] += sub["childStats"]["bugs"]
            elif ctype == "feature":
                feat = _feature_node(cid)
                features.append(feat)
                stats["features"] += 1
                stats["stories"] += feat["childStats"]["stories"]
                stats["bugs"] += feat["childStats"]["bugs"]
            elif ctype in ("user story", "bug"):
                direct_children.append(_leaf_node(cid, ctype))
                if ctype == "user story":
                    stats["stories"] += 1
                else:
                    stats["bugs"] += 1
        return {
            "id": eid,
            "title": fields.get("System.Title", "(untitled)"),
            "type": "Epic",
            "state": fields.get("System.State", ""),
            "assignedTo": _display_name(fields.get("System.AssignedTo")),
            "url": _html_url(eid),
            "children": sub_epics + features + direct_children,
            "childStats": stats,
        }

    epics = [
        _epic_node(eid, {eid})
        for eid in epic_ids
        if parent_epic[eid] is None
    ]
    print(f"Tree built: {len(epics)} top-level Epic(s), {len(epic_ids)} total.")
    return epics


MOCK_EPIC_TREE: list[dict] = [
    {
        "id": 100,
        "title": "Platform UX Modernization",
        "type": "Epic",
        "state": "In Progress",
        "assignedTo": "Alice Chen",
        "url": "https://dev.azure.com/org/project/_workitems/edit/100",
        "children": [
            {
                "id": 102,
                "title": "Mobile Experience",
                "type": "Epic",
                "state": "In Progress",
                "assignedTo": "Alice Chen",
                "url": "https://dev.azure.com/org/project/_workitems/edit/102",
                "children": [
                    {
                        "id": 204,
                        "title": "Offline Mode",
                        "type": "Feature",
                        "state": "In Progress",
                        "assignedTo": "Hina Ito",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/204",
                        "children": [
                            {
                                "id": 3011, "title": "Cache dashboard data for offline viewing",
                                "type": "User Story", "state": "Active",
                                "assignedTo": "Hina Ito",
                                "url": "https://dev.azure.com/org/project/_workitems/edit/3011",
                                "children": [], "childStats": {"stories": 0, "bugs": 0},
                            },
                            {
                                "id": 3012, "title": "Sync conflicts when editing offline notes",
                                "type": "Bug", "state": "New",
                                "assignedTo": "",
                                "url": "https://dev.azure.com/org/project/_workitems/edit/3012",
                                "children": [], "childStats": {"stories": 0, "bugs": 0},
                            },
                        ],
                        "childStats": {"stories": 1, "bugs": 1},
                    },
                ],
                "childStats": {"epics": 0, "features": 1, "stories": 1, "bugs": 1},
            },
            {
                "id": 200,
                "title": "Dashboard V2 Widget Suite",
                "type": "Feature",
                "state": "Done",
                "assignedTo": "Alice Chen",
                "url": "https://dev.azure.com/org/project/_workitems/edit/200",
                "children": [
                    {
                        "id": 3001, "title": "Add revenue chart widget to dashboard",
                        "type": "User Story", "state": "Active",
                        "assignedTo": "Alice Chen",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3001",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                    {
                        "id": 3002, "title": "Add real-time alert panel to dashboard",
                        "type": "User Story", "state": "New",
                        "assignedTo": "Bob Park",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3002",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                    {
                        "id": 3007, "title": "Dashboard flicker on dark mode toggle",
                        "type": "Bug", "state": "Active",
                        "assignedTo": "Bob Park",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3007",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                ],
                "childStats": {"stories": 2, "bugs": 1},
            },
            {
                "id": 201,
                "title": "Performance & Stability",
                "type": "Feature",
                "state": "In Progress",
                "assignedTo": "Diana Reyes",
                "url": "https://dev.azure.com/org/project/_workitems/edit/201",
                "children": [
                    {
                        "id": 3003, "title": "Fix memory leak in data pipeline worker",
                        "type": "Bug", "state": "Resolved",
                        "assignedTo": "Diana Reyes",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3003",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                    {
                        "id": 3008, "title": "Optimize database query for user search endpoint",
                        "type": "Bug", "state": "Active",
                        "assignedTo": "Evan Torres",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3008",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                ],
                "childStats": {"stories": 0, "bugs": 2},
            },
        ],
        "childStats": {"epics": 1, "features": 3, "stories": 3, "bugs": 3},
    },
    {
        "id": 101,
        "title": "API Expansion",
        "type": "Epic",
        "state": "In Progress",
        "assignedTo": "Fiona Gupta",
        "url": "https://dev.azure.com/org/project/_workitems/edit/101",
        "children": [
            {
                "id": 202,
                "title": "API v2 Endpoints",
                "type": "Feature",
                "state": "In Progress",
                "assignedTo": "Fiona Gupta",
                "url": "https://dev.azure.com/org/project/_workitems/edit/202",
                "children": [
                    {
                        "id": 3005, "title": "Expose bulk export API endpoint",
                        "type": "User Story", "state": "Active",
                        "assignedTo": "Fiona Gupta",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3005",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                    {
                        "id": 3009, "title": "Add webhook support for deployment events",
                        "type": "User Story", "state": "New",
                        "assignedTo": "",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3009",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                ],
                "childStats": {"stories": 2, "bugs": 0},
            },
            {
                "id": 203,
                "title": "Rate Limiting & Throttling",
                "type": "Feature",
                "state": "New",
                "assignedTo": "George Holt",
                "url": "https://dev.azure.com/org/project/_workitems/edit/203",
                "children": [
                    {
                        "id": 3010, "title": "Implement per-user rate limiting middleware",
                        "type": "User Story", "state": "New",
                        "assignedTo": "George Holt",
                        "url": "https://dev.azure.com/org/project/_workitems/edit/3010",
                        "children": [], "childStats": {"stories": 0, "bugs": 0},
                    },
                ],
                "childStats": {"stories": 1, "bugs": 0},
            },
        ],
        "childStats": {"features": 2, "stories": 3, "bugs": 0},
    },
]


def main() -> None:
    use_mock = "--mock" in sys.argv

    if not use_mock:
        org = config.ADO_ORG_URL()
        pat = config.ADO_PAT()
        proj = config.ADO_PROJECT()
        if not all([org, pat, proj]):
            print("ERROR: ADO credentials not fully configured.")
            print("       Set ADO_ORG_URL, ADO_PAT, ADO_PROJECT in environment or release_notes/.env")
            print("       Or use --mock for demo data.")
            sys.exit(1)

    try:
        tree = build_tree(use_mock=use_mock)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = EXPORTS_DIR / "epic_tree.json"
    json_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported data to {json_path}")

    # Read template, inject data, write HTML
    if TEMPLATE_PATH.is_file():
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        html = template.replace(
            "window.EPIC_TREE_DATA = [];",
            f"window.EPIC_TREE_DATA = {json.dumps(tree, ensure_ascii=False)};"
        )
        html_path = EXPORTS_DIR / "epic_tree.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"Exported page to {html_path}")
    else:
        print(f"WARNING: Template not found at {TEMPLATE_PATH}, skipping HTML output.")


if __name__ == "__main__":
    main()
