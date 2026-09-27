"""Configuration loading for LocalForge."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    github_owner: str | None
    github_repository: str | None
    poll_interval_seconds: int | None
    workspace_root: str | None
    ai_ready_label: str | None
    ai_working_label: str | None
    codex_mode: str
    codex_model: str


def load_config(config_path: Path | str = "config.ini") -> Settings:
    """Load settings from the environment, falling back to ``config.ini``."""
    parser = configparser.ConfigParser()
    parser.read(config_path)
    values = parser["localforge"] if parser.has_section("localforge") else {}

    def get(name: str) -> str | None:
        return os.getenv(name) or values.get(name.lower()) or None

    poll_interval = get("POLL_INTERVAL_SECONDS")

    return Settings(
        github_token=get("GITHUB_TOKEN"),
        github_owner=get("GITHUB_OWNER"),
        github_repository=get("GITHUB_REPOSITORY"),
        poll_interval_seconds=int(poll_interval) if poll_interval else None,
        workspace_root=get("WORKSPACE_ROOT"),
        ai_ready_label=get("AI_READY_LABEL"),
        ai_working_label=get("AI_WORKING_LABEL"),
        codex_mode=get("CODEX_MODE") or "codex",
        codex_model=get("CODEX_MODEL") or "unsloth/qwen3-coder-30b-a3b-instruct",
    )
