"""Run LocalForge's GitHub issue-status test flow."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from localforge.config import Settings, load_config
from localforge.codex_runner import build_issue_prompt, run_codex
from localforge.github_client import GitHubClient
from localforge.run_log import store_run_log
from localforge.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="replace the ready label with the working label",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="maximum eligible issues to inspect (default: 1)",
    )
    return parser.parse_args()


def require_github_settings(settings: Settings) -> tuple[str, str, str, str, str]:
    values = {
        "GITHUB_TOKEN": settings.github_token,
        "GITHUB_OWNER": settings.github_owner,
        "GITHUB_REPOSITORY": settings.github_repository,
        "AI_READY_LABEL": settings.ai_ready_label,
        "AI_WORKING_LABEL": settings.ai_working_label,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    return tuple(values.values())  # type: ignore[return-value]


def build_run_comment(
    workspace_path: object,
    branch: str,
    exit_code: int,
    duration_seconds: float,
    log_path: object,
) -> str:
    """Describe where a completed local run can be reviewed without publishing code."""
    status = "completed successfully" if exit_code == 0 else "failed"
    return (
        "## LocalForge run\n\n"
        f"Codex {status} (exit status: {exit_code}; duration: {duration_seconds:.1f}s).\n\n"
        f"Local branch: `{branch}` (not pushed)\n"
        f"Review worktree: `{workspace_path}`\n"
        f"Local run log: `{log_path}`\n"
    )


async def run(apply: bool, limit: int) -> int:
    """List eligible issues and optionally move them from ready to working."""
    if limit < 1:
        raise ValueError("--limit must be at least 1")

    settings = load_config()
    token, owner, repo, ready_label, working_label = require_github_settings(settings)
    client = GitHubClient(token)
    issues = (await client.get_issues(owner, repo, ready_label))[:limit]

    if not issues:
        print(f"No open issues with the {ready_label!r} label.")
        return 0

    for issue in issues:
        print(f"#{issue.number}: {issue.title}")
        if apply:
            await client.move_issue_to_label(
                owner,
                repo,
                issue.number,
                ready_label,
                working_label,
            )
            print(f"  moved from {ready_label!r} to {working_label!r}")
            if not settings.workspace_root:
                raise ValueError("Missing required configuration: WORKSPACE_ROOT")
            workspace = WorkspaceManager(settings.workspace_root, owner, repo).prepare_issue(
                issue.number,
                issue.title,
            )
            print(f"  workspace: {workspace.path}")
            print(f"  branch: {workspace.branch}")
            prompt = build_issue_prompt(issue.number, issue.title, getattr(issue, "body", None))
            result = run_codex(
                workspace.path,
                settings.codex_mode,
                settings.codex_model,
                prompt,
            )
            print(f"  Codex exit status: {result.exit_code}")
            print(f"  Codex duration: {result.duration_seconds:.1f}s")
            if result.stdout:
                print("  Codex stdout:")
                print(result.stdout)
            if result.stderr:
                print("  Codex stderr:", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
            log_path = store_run_log(
                Path(settings.workspace_root) / "run-logs",
                issue.number,
                workspace.path,
                workspace.branch,
                result,
            )
            print(f"  run log: {log_path}")
            target_label = (
                settings.human_review_label
                if result.exit_code == 0
                else settings.ai_blocked_label
            )
            await client.move_issue_to_label(
                owner,
                repo,
                issue.number,
                working_label,
                target_label,
            )
            await client.create_issue_comment(
                owner,
                repo,
                issue.number,
                build_run_comment(
                    workspace.path,
                    workspace.branch,
                    result.exit_code,
                    result.duration_seconds,
                    log_path,
                ),
            )
            print(f"  moved from {working_label!r} to {target_label!r}")
            if result.exit_code != 0:
                return result.exit_code
        else:
            print("  dry run; pass --apply to update its label")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args.apply, args.limit))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    except Exception:
        logger.exception("LocalForge test run failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
