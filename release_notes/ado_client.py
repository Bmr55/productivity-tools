from __future__ import annotations

import copy

from release_notes import config
from release_notes.mock_data import MOCK_RELEASE
from release_notes.models import Release


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

    def get_release_by_id(self, release_id: int) -> Release:
        if self._use_mock:
            if release_id != MOCK_RELEASE.id:
                raise ValueError(
                    f"No mock data for release {release_id}. "
                    f"The only mock release available is ID {MOCK_RELEASE.id}."
                )
            return copy.deepcopy(MOCK_RELEASE)
        if self.is_configured:
            raise NotImplementedError("ADO REST API not yet implemented")
        raise RuntimeError(
            "Azure DevOps credentials are not configured. "
            "Configure all ADO settings or explicitly enable mock mode."
        )
