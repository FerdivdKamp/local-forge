"""Local, human-readable logs for completed Codex runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from localforge.codex_runner import CodexRunResult


def log_event(log_root: Path | str, event: str, **fields: object) -> None:
    """Append a small structured event without publishing Codex output or secrets."""
    directory = Path(log_root)
    directory.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def store_run_log(
    log_root: Path | str,
    issue_number: int,
    workspace: Path | str,
    branch: str,
    result: CodexRunResult,
) -> Path:
    """Write one local log file and return its path.

    The log stays outside the Git worktree and is never sent to GitHub.  It
    includes the captured Codex streams so a reviewer can diagnose a run
    without relying on terminal scrollback.
    """
    if issue_number < 1:
        raise ValueError("issue_number must be positive")

    completed_at = datetime.now(timezone.utc)
    directory = Path(log_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"issue-{issue_number}-{completed_at:%Y%m%dT%H%M%S%fZ}.log"
    command = " ".join(result.command[:-1])
    path.write_text(
        "\n".join(
            (
                "LocalForge run log",
                f"Completed at: {completed_at.isoformat()}",
                f"Issue: #{issue_number}",
                f"Workspace: {Path(workspace)}",
                f"Branch: {branch}",
                f"Command: {command}",
                f"Exit status: {result.exit_code}",
                f"Duration: {result.duration_seconds:.1f}s",
                "",
                "--- Codex stdout ---",
                result.stdout,
                "",
                "--- Codex stderr ---",
                result.stderr,
                "",
                "--- Codex events (JSONL) ---",
                result.event_stream,
                "",
            )
        ),
        encoding="utf-8",
    )
    return path
