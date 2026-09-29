"""Local, human-readable logs for completed Codex runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from localforge.codex_runner import CodexRunResult


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
            )
        ),
        encoding="utf-8",
    )
    return path
