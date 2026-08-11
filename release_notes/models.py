from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


RTC_FIELD_KEY = "RTC Item"

_ADO_ID_RE = re.compile(
    r"https?://[^\s]*dev\.azure\.com[^\s]*"
    r"(?:_workitems/(?:edit/)?(\d+)"
    r"|[?&]workitem=(\d+)"
    r"|/(\d+)(?:[?#&]|$))",
    re.IGNORECASE,
)


def extract_ado_id(text: str) -> int | None:
    """Extract an ADO work-item ID from any known URL variant found in *text*.

    Handles these formats:

    * Standard:   ``.../_workitems/edit/3001``
    * Short:      ``.../_workitems/3001``
    * Sprint board: ``.../taskboard/...?workitem=3001``
    * Board view:  ``.../_boards/...?workitem=3001``
    * Bare suffix:  ``.../org/project/3001``
    """
    match = _ADO_ID_RE.search(text)
    if not match:
        return None
    for group in match.groups():
        if group is not None:
            return int(group)
    return None


class WorkItemType(Enum):
    USER_STORY = "User Story"
    BUG = "Bug"
    FEATURE = "Feature"
    EPIC = "Epic"


WORK_ITEM_ICONS: dict[WorkItemType, str] = {
    WorkItemType.USER_STORY: "\U0001f4d6",
    WorkItemType.BUG: "\U0001f41b",
    WorkItemType.FEATURE: "\U0001f4e6",
    WorkItemType.EPIC: "\U0001f30d",
}


@dataclass
class GitLabIssue:
    id: int
    iid: int
    title: str
    description: str
    state: str
    web_url: str
    labels: list[str] = field(default_factory=list)
    milestone: str = ""


@dataclass
class GitLabMergeRequest:
    id: int
    iid: int
    title: str
    description: str
    state: str
    web_url: str
    source_branch: str = ""
    target_branch: str = ""
    author: str = ""
    merged_at: str = ""


@dataclass
class ParentWorkItem:
    id: int
    title: str
    work_item_type: WorkItemType
    state: str = ""
    url: str = ""


@dataclass
class WorkItem:
    id: int
    title: str
    work_item_type: WorkItemType
    state: str
    description: str = ""
    assigned_to: str = ""
    iteration_path: str = ""
    area_path: str = ""
    priority: int = 0
    severity: str = ""
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, str] = field(default_factory=dict)
    parent_feature: ParentWorkItem | None = None
    parent_epic: ParentWorkItem | None = None
    gitlab_issue: GitLabIssue | None = None
    gitlab_mr: GitLabMergeRequest | None = None

    @property
    def rtc_item(self) -> str:
        return self.custom_fields.get(RTC_FIELD_KEY, "")

    @property
    def ado_url(self) -> str:
        from release_notes import config
        org = config.ADO_ORG_URL().rstrip("/")
        project = config.ADO_PROJECT()
        if org and project:
            return f"{org}/{project}/_workitems/edit/{self.id}"
        return ""


@dataclass
class TestTask:
    id: int
    title: str
    state: str
    linked_work_items: list[WorkItem] = field(default_factory=list)


@dataclass
class Release:
    id: int
    title: str
    version: str
    release_date: str = ""
    description: str = ""
    test_tasks: list[TestTask] = field(default_factory=list)
