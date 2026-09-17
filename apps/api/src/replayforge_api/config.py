"""Settings from environment variables. Values are never logged; only missing names are reported."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'data' / 'replayforge.db'}")
    )
    web_origin: str = field(default_factory=lambda: os.environ.get("WEB_ORIGIN", "http://localhost:5173"))
    public_base_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173"))
    sandbox_backend: str = field(default_factory=lambda: os.environ.get("SANDBOX_BACKEND", "local"))
    max_experiment_cases: int = field(default_factory=lambda: _int("MAX_EXPERIMENT_CASES", 50))
    max_provider_calls: int = field(default_factory=lambda: _int("MAX_PROVIDER_CALLS_PER_EXPERIMENT", 250))
    max_concurrency: int = field(default_factory=lambda: _int("MAX_CONCURRENCY_PER_PROVIDER", 3))
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    github_webhook_secret: str = field(default_factory=lambda: os.environ.get("GITHUB_WEBHOOK_SECRET", ""))
    suites_dir: Path = REPO_ROOT / "fixtures" / "suites"
    solutions_dir: Path = REPO_ROOT / "fixtures" / "solutions"

    def missing(self) -> list[str]:
        names = ["NEBIUS_TOKEN_FACTORY_API_KEY", "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET"]
        return [name for name in names if not os.environ.get(name)]


def get_settings() -> Settings:
    return Settings()
