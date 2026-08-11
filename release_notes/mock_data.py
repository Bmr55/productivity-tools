from release_notes.models import (
    GitLabIssue,
    GitLabMergeRequest,
    ParentWorkItem,
    Release,
    TestTask,
    WorkItem,
    WorkItemType,
)


def _make_mock_release() -> Release:
    return Release(
        id=1001,
        title="Q3 Platform Release v4.2.0",
        version="4.2.0",
        release_date="2026-07-15",
        description="Major platform release including dashboard overhaul, performance fixes, and new API capabilities.",
        test_tasks=[
            TestTask(
                id=2001,
                title="Validate new dashboard widgets",
                state="Passed",
                linked_work_items=[
                    WorkItem(
                        id=3001,
                        title="Add revenue chart widget to dashboard",
                        work_item_type=WorkItemType.USER_STORY,
                        state="Done",
                        description="As a user I want a revenue chart widget so that I can track income trends.",
                        assigned_to="Alice Chen",
                        iteration_path=r"Q3 Platform\Sprint 1",
                        area_path=r"Platform\Dashboard",
                        priority=1,
                        tags=["dashboard", "frontend", "analytics"],
                        custom_fields={"RTC Item": "RTC-4821"},
                        parent_feature=ParentWorkItem(
                            id=200, title="Dashboard V2 Widget Suite",
                            work_item_type=WorkItemType.FEATURE, state="Done",
                            url="https://dev.azure.com/org/project/_workitems/edit/200",
                        ),
                        parent_epic=ParentWorkItem(
                            id=100, title="Platform UX Modernization",
                            work_item_type=WorkItemType.EPIC, state="In Progress",
                            url="https://dev.azure.com/org/project/_workitems/edit/100",
                        ),
                    ),
                    WorkItem(
                        id=3002,
                        title="Add real-time alert panel to dashboard",
                        work_item_type=WorkItemType.USER_STORY,
                        state="Done",
                        description="As an operator I want a real-time alert panel so I can monitor system health.",
                        assigned_to="Bob Park",
                        iteration_path=r"Q3 Platform\Sprint 1",
                        area_path=r"Platform\Dashboard",
                        priority=2,
                        tags=["dashboard", "alerts", "real-time"],
                        custom_fields={"RTC Item": "RTC-4910"},
                        parent_feature=ParentWorkItem(
                            id=200, title="Dashboard V2 Widget Suite",
                            work_item_type=WorkItemType.FEATURE, state="Done",
                            url="https://dev.azure.com/org/project/_workitems/edit/200",
                        ),
                        parent_epic=ParentWorkItem(
                            id=100, title="Platform UX Modernization",
                            work_item_type=WorkItemType.EPIC, state="In Progress",
                            url="https://dev.azure.com/org/project/_workitems/edit/100",
                        ),
                    ),
                ],
            ),
            TestTask(
                id=2002,
                title="Validate performance improvements",
                state="Passed",
                linked_work_items=[
                    WorkItem(
                        id=3003,
                        title="Fix memory leak in data pipeline worker",
                        work_item_type=WorkItemType.BUG,
                        state="Resolved",
                        description="Worker processes leak ~50MB/hour under sustained load, causing OOM after ~6 hours.",
                        assigned_to="Diana Reyes",
                        iteration_path=r"Q3 Platform\Sprint 2",
                        area_path=r"Platform\Data Pipeline",
                        priority=0,
                        severity="Critical",
                        tags=["bug", "performance", "backend"],
                        custom_fields={"RTC Item": "RTC-5123"},
                        parent_feature=ParentWorkItem(
                            id=201, title="Performance & Stability",
                            work_item_type=WorkItemType.FEATURE, state="Done",
                            url="https://dev.azure.com/org/project/_workitems/edit/201",
                        ),
                        parent_epic=ParentWorkItem(
                            id=101, title="Platform Reliability",
                            work_item_type=WorkItemType.EPIC, state="In Progress",
                            url="https://dev.azure.com/org/project/_workitems/edit/101",
                        ),
                    ),
                    WorkItem(
                        id=3004,
                        title="Optimize database query for user search endpoint",
                        work_item_type=WorkItemType.BUG,
                        state="Resolved",
                        description="User search endpoint P99 latency is 2.3s. Target is <500ms.",
                        assigned_to="Evan Torres",
                        iteration_path=r"Q3 Platform\Sprint 2",
                        area_path=r"Platform\API",
                        priority=1,
                        severity="High",
                        tags=["bug", "performance", "backend", "api"],
                        custom_fields={"RTC Item": "RTC-5288"},
                        parent_feature=ParentWorkItem(
                            id=201, title="Performance & Stability",
                            work_item_type=WorkItemType.FEATURE, state="Done",
                            url="https://dev.azure.com/org/project/_workitems/edit/201",
                        ),
                        parent_epic=ParentWorkItem(
                            id=101, title="Platform Reliability",
                            work_item_type=WorkItemType.EPIC, state="In Progress",
                            url="https://dev.azure.com/org/project/_workitems/edit/101",
                        ),
                    ),
                ],
            ),
            TestTask(
                id=2003,
                title="Validate new API endpoints",
                state="Passed",
                linked_work_items=[
                    WorkItem(
                        id=3005,
                        title="Expose bulk export API endpoint",
                        work_item_type=WorkItemType.USER_STORY,
                        state="Done",
                        description="As an integrator I want a bulk export API so that I can extract large datasets programmatically.",
                        assigned_to="Fiona Gupta",
                        iteration_path=r"Q3 Platform\Sprint 3",
                        area_path=r"Platform\API",
                        priority=1,
                        tags=["api", "export", "backend"],
                        custom_fields={"RTC Item": "RTC-5402"},
                        parent_feature=ParentWorkItem(
                            id=202, title="API v2 Endpoints",
                            work_item_type=WorkItemType.FEATURE, state="Done",
                            url="https://dev.azure.com/org/project/_workitems/edit/202",
                        ),
                        parent_epic=ParentWorkItem(
                            id=102, title="API Expansion",
                            work_item_type=WorkItemType.EPIC, state="In Progress",
                            url="https://dev.azure.com/org/project/_workitems/edit/102",
                        ),
                    ),
                    WorkItem(
                        id=3006,
                        title="Entrypoint for deployments in next month",
                        work_item_type=WorkItemType.BUG,
                        state="Closed",
                        description="Deployment entrypoint returns 500 when no active deployments exist on the date range.",
                        assigned_to="George Holt",
                        iteration_path=r"Q3 Platform\Sprint 3",
                        area_path=r"Platform\API",
                        priority=2,
                        severity="Medium",
                        tags=["api", "deployments", "bug"],
                        custom_fields={"RTC Item": "RTC-5560"},
                        parent_feature=ParentWorkItem(
                            id=202, title="API v2 Endpoints",
                            work_item_type=WorkItemType.FEATURE, state="Done",
                            url="https://dev.azure.com/org/project/_workitems/edit/202",
                        ),
                        parent_epic=ParentWorkItem(
                            id=102, title="API Expansion",
                            work_item_type=WorkItemType.EPIC, state="In Progress",
                            url="https://dev.azure.com/org/project/_workitems/edit/102",
                        ),
                    ),
                ],
            ),
        ],
    )


MOCK_RELEASE = _make_mock_release()


MOCK_GITLAB_ISSUES_BY_ADO_ID: dict[int, GitLabIssue] = {
    3001: GitLabIssue(
        id=401, iid=12,
        title="Dashboard revenue chart widget",
        description=(
            "Implements revenue chart widget on main dashboard.\n\n"
            "ADO: https://dev.azure.com/org/project/_workitems/edit/3001"
        ),
        state="closed",
        web_url="https://gitlab.example.com/platform/frontend/-/issues/12",
        labels=["frontend", "dashboard"],
        milestone="Q3 Sprint 1",
    ),
    3002: GitLabIssue(
        id=402, iid=15,
        title="Real-time alert panel",
        description=(
            "Implement alert panel with WebSocket-based live updates.\n\n"
            "ADO: https://dev.azure.com/org/project/_workitems/3002"
        ),
        state="closed",
        web_url="https://gitlab.example.com/platform/frontend/-/issues/15",
        labels=["frontend", "real-time"],
        milestone="Q3 Sprint 1",
    ),
    3003: GitLabIssue(
        id=403, iid=28,
        title="Data pipeline memory leak investigation",
        description=(
            "Root cause: unreleased buffer in retry queue.\n\n"
            "ADO: https://dev.azure.com/org/project/_sprints/taskboard/Platform%20Team/Q3%20Sprint%202?workitem=3003"
        ),
        state="closed",
        web_url="https://gitlab.example.com/platform/backend/-/issues/28",
        labels=["bug", "performance"],
        milestone="Q3 Sprint 2",
    ),
    3004: GitLabIssue(
        id=404, iid=31,
        title="User search query optimization",
        description=(
            "Add composite index and refactor ORM queries.\n\n"
            "ADO: https://dev.azure.com/org/project/_workitems/edit/3004"
        ),
        state="closed",
        web_url="https://gitlab.example.com/platform/backend/-/issues/31",
        labels=["performance", "backend"],
        milestone="Q3 Sprint 2",
    ),
    3005: GitLabIssue(
        id=405, iid=35,
        title="Bulk export API endpoint",
        description=(
            "REST endpoint for async bulk data export with pagination.\n\n"
            "ADO: https://dev.azure.com/org/project/_boards/board/t/Platform%20Team/Features/?workitem=3005"
        ),
        state="closed",
        web_url="https://gitlab.example.com/platform/backend/-/issues/35",
        labels=["api", "backend"],
        milestone="Q3 Sprint 3",
    ),
    3006: GitLabIssue(
        id=406, iid=39,
        title="Handle empty deployments gracefully",
        description=(
            "Return 200 with empty array instead of 500.\n\n"
            "ADO: https://dev.azure.com/org/project/_workitems/edit/3006"
        ),
        state="closed",
        web_url="https://gitlab.example.com/platform/backend/-/issues/39",
        labels=["api", "bug"],
        milestone="Q3 Sprint 3",
    ),
}


MOCK_GITLAB_MRS_BY_ISSUE_IID: dict[int, GitLabMergeRequest] = {
    12: GitLabMergeRequest(
        id=501, iid=34,
        title="feat: add revenue chart widget",
        description="Closes #12. Adds revenue chart with configurable time range.",
        state="merged",
        web_url="https://gitlab.example.com/platform/frontend/-/merge_requests/34",
        source_branch="feat/revenue-widget", target_branch="main",
        author="Alice Chen", merged_at="2026-07-02T14:30:00Z",
    ),
    15: GitLabMergeRequest(
        id=502, iid=36,
        title="feat: real-time alert panel",
        description="Closes #15. Websocket-driven alert panel.",
        state="merged",
        web_url="https://gitlab.example.com/platform/frontend/-/merge_requests/36",
        source_branch="feat/alert-panel", target_branch="main",
        author="Bob Park", merged_at="2026-07-05T09:15:00Z",
    ),
    28: GitLabMergeRequest(
        id=503, iid=41,
        title="fix: resolve memory leak in pipeline retry buffer",
        description="Closes #28. Frees retry queue buffer after each batch flush.",
        state="merged",
        web_url="https://gitlab.example.com/platform/backend/-/merge_requests/41",
        source_branch="fix/pipeline-memleak", target_branch="main",
        author="Diana Reyes", merged_at="2026-07-08T11:00:00Z",
    ),
    31: GitLabMergeRequest(
        id=504, iid=44,
        title="perf: optimize user search with composite index",
        description="Closes #31. Adds GIN index and eager-loads relations.",
        state="merged",
        web_url="https://gitlab.example.com/platform/backend/-/merge_requests/44",
        source_branch="perf/user-search-idx", target_branch="main",
        author="Evan Torres", merged_at="2026-07-10T16:45:00Z",
    ),
    35: GitLabMergeRequest(
        id=505, iid=48,
        title="feat: bulk export API with async job support",
        description="Closes #35. Adds POST /api/v2/exports/bulk endpoint.",
        state="merged",
        web_url="https://gitlab.example.com/platform/backend/-/merge_requests/48",
        source_branch="feat/bulk-export", target_branch="main",
        author="Fiona Gupta", merged_at="2026-07-13T12:20:00Z",
    ),
    39: GitLabMergeRequest(
        id=506, iid=51,
        title="fix: return empty list when no deployments exist",
        description="Closes #39. Guards against null response from deployment service.",
        state="merged",
        web_url="https://gitlab.example.com/platform/backend/-/merge_requests/51",
        source_branch="fix/deployment-empty", target_branch="main",
        author="George Holt", merged_at="2026-07-14T08:00:00Z",
    ),
}
