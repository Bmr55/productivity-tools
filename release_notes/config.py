import os
from pathlib import Path


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (no dependencies required)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


class _LazyConfig:
    """Lazy-loads config so secrets are only read from .env when first accessed."""

    _dotenv: dict[str, str] | None = None

    @staticmethod
    def _ensure_loaded() -> dict[str, str]:
        if _LazyConfig._dotenv is None:
            _env_file = Path(__file__).resolve().parent / ".env"
            _LazyConfig._dotenv = _load_dotenv(_env_file)
        return _LazyConfig._dotenv

    @staticmethod
    def get(key: str, default: str = "") -> str:
        val = os.environ.get(key)
        if val is not None:
            return val
        return _LazyConfig._ensure_loaded().get(key, default)

    @staticmethod
    def _resolve_ado_org_url() -> str:
        return _LazyConfig.get("ADO_ORG_URL")

    @staticmethod
    def _resolve_ado_pat() -> str:
        return _LazyConfig.get("ADO_PAT")

    @staticmethod
    def _resolve_ado_project() -> str:
        return _LazyConfig.get("ADO_PROJECT")

    @staticmethod
    def _resolve_gitlab_base_url() -> str:
        return _LazyConfig.get("GITLAB_BASE_URL")

    @staticmethod
    def _resolve_gitlab_token() -> str:
        return _LazyConfig.get("GITLAB_PRIVATE_TOKEN")


# Lazy accessors — secrets are only resolved from env/.env on first call.
ADO_ORG_URL = _LazyConfig._resolve_ado_org_url
ADO_PAT = _LazyConfig._resolve_ado_pat
ADO_PROJECT = _LazyConfig._resolve_ado_project
GITLAB_BASE_URL = _LazyConfig._resolve_gitlab_base_url
GITLAB_PRIVATE_TOKEN = _LazyConfig._resolve_gitlab_token
