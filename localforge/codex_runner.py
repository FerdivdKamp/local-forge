"""Build Codex task prompts and command lines for LocalForge runs."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from localforge.codex_events import TestRun, TokenUsage, parse_codex_events


DEFAULT_OSS_MODEL = "unsloth/qwen3-coder-30b-a3b-instruct"
_SAFE_ENVIRONMENT_VARIABLES = frozenset(
    {
        "APPDATA",
        "COMSPEC",
        "HOME",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
)


@dataclass(frozen=True)
class CodexRunResult:
    """The captured outcome of one non-interactive Codex invocation."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    usage: TokenUsage | None = None
    test_runs: tuple[TestRun, ...] = ()
    event_stream: str = ""


def build_codex_command(mode: str, model: str = DEFAULT_OSS_MODEL) -> tuple[str, ...]:
    """Return the configured Codex CLI command without starting a process.

    ``lm-studio`` selects Codex's OSS mode. LM Studio must already be running
    and configured as the local model provider before that command is used.
    """
    if mode == "codex":
        return ("codex",)
    if mode == "lm-studio":
        if not model:
            raise ValueError("CODEX_MODEL is required when CODEX_MODE is lm-studio")
        return ("codex", "--oss", "-m", model)
    raise ValueError("CODEX_MODE must be 'codex' or 'lm-studio'")


def build_issue_prompt(issue_number: int, title: str, body: str | None) -> str:
    """Build the coding task passed to Codex for one GitHub issue."""
    if issue_number < 1:
        raise ValueError("issue_number must be positive")
    if not title.strip():
        raise ValueError("issue title must not be empty")

    description = body.strip() if body and body.strip() else "No description was provided."
    return dedent(
        f"""\
        Implement GitHub issue #{issue_number} in the current repository worktree.

        Read AGENTS.md and relevant project documentation before making changes.
        Work only in this worktree. Do not push branches, create pull requests,
        commit changes, change GitHub issue state, or access LocalForge credentials.

        Issue title: {title.strip()}

        Issue description:
        {description}

        Implement the requested change, add or update relevant tests, and run the
        appropriate test commands. At the end, report the files changed and the
        tests run with their result. LocalForge will commit and publish completed
        work after this run succeeds.
        """
    ).strip()


def sanitized_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return only the operating-system variables Codex needs to run locally."""
    environment = source if source is not None else os.environ
    return {
        name: value
        for name, value in environment.items()
        if name.upper() in _SAFE_ENVIRONMENT_VARIABLES
    }


def run_codex(
    workspace: Path | str,
    mode: str,
    model: str,
    prompt: str,
) -> CodexRunResult:
    """Run Codex non-interactively in an issue worktree and capture its result."""
    command = (*build_codex_command(mode, model), "exec", "--approve-for-me", "--json", "--color", "never", prompt)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=sanitized_environment(),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return CodexRunResult(
            command=command,
            exit_code=127,
            stdout="",
            stderr=str(error),
            duration_seconds=time.monotonic() - started,
        )

    events = parse_codex_events(completed.stdout)
    return CodexRunResult(
        command=command,
        exit_code=completed.returncode,
        stdout=events.final_message or completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.monotonic() - started,
        usage=events.usage,
        test_runs=events.test_runs,
        event_stream=completed.stdout if events.final_message else "",
    )
