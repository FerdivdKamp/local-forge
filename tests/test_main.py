"""Tests for the LocalForge issue execution flow."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from localforge.codex_runner import CodexRunResult
from localforge.config import Settings
from localforge.github_client import PullRequest
from localforge.main import run


class MainRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_apply_runs_codex_in_the_prepared_issue_workspace(self) -> None:
        settings = Settings(
            github_token="token",
            github_owner="octo",
            github_repository="widget",
            poll_interval_seconds=None,
            workspace_root="workspaces",
            ai_ready_label="ai-ready",
            ai_working_label="ai-working",
            ai_blocked_label="ai-blocked",
            human_review_label="human-review",
            codex_mode="codex",
            codex_model="model",
        )
        issue = SimpleNamespace(number=42, title="Fix the bug", body="Make it work.")
        client = Mock()
        client.get_issues = AsyncMock(return_value=[issue])
        client.move_issue_to_label = AsyncMock()
        client.create_issue_comment = AsyncMock()
        client.create_pull_request = AsyncMock(
            return_value=PullRequest(7, "https://github.com/octo/widget/pull/7")
        )
        workspace = SimpleNamespace(path=Path("workspaces/issues/42-fix-the-bug"), branch="ai/42-fix-the-bug")
        result = CodexRunResult(("codex",), 0, "done", "", 1.0)

        with (
            patch("localforge.main.load_config", return_value=settings),
            patch("localforge.main.GitHubClient", return_value=client),
            patch("localforge.main.WorkspaceManager") as manager,
            patch("localforge.main.run_codex", return_value=result) as run_codex,
            patch("localforge.main.store_run_log", return_value=Path("workspaces/run-logs/issue-42.log")) as store_log,
        ):
            manager.return_value.prepare_issue.return_value = workspace
            exit_code = await run(apply=True, limit=1)

        self.assertEqual(exit_code, 0)
        run_codex.assert_called_once()
        args = run_codex.call_args.args
        self.assertEqual(args[:3], (workspace.path, "codex", "model"))
        self.assertIn("GitHub issue #42", args[3])
        manager.return_value.push_issue_branch.assert_called_once_with(workspace)
        client.create_pull_request.assert_awaited_once_with(
            "octo", "widget", 42, "Fix the bug", "ai/42-fix-the-bug"
        )
        store_log.assert_called_once_with(
            Path("workspaces") / "run-logs",
            42,
            workspace.path,
            workspace.branch,
            result,
        )
        client.move_issue_to_label.assert_has_awaits(
            [
                unittest.mock.call("octo", "widget", 42, "ai-ready", "ai-working"),
                unittest.mock.call("octo", "widget", 42, "ai-working", "human-review"),
            ]
        )
        client.create_issue_comment.assert_awaited_once()
        comment = client.create_issue_comment.call_args.args[3]
        self.assertIn("Published branch: `ai/42-fix-the-bug`", comment)
        self.assertIn("Pull request: [#7](https://github.com/octo/widget/pull/7)", comment)

    async def test_failed_codex_run_marks_the_issue_blocked(self) -> None:
        settings = Settings(
            github_token="token",
            github_owner="octo",
            github_repository="widget",
            poll_interval_seconds=None,
            workspace_root="workspaces",
            ai_ready_label="ai-ready",
            ai_working_label="ai-working",
            ai_blocked_label="ai-blocked",
            human_review_label="human-review",
            codex_mode="codex",
            codex_model="model",
        )
        issue = SimpleNamespace(number=42, title="Fix the bug", body="Make it work.")
        client = Mock()
        client.get_issues = AsyncMock(return_value=[issue])
        client.move_issue_to_label = AsyncMock()
        client.create_issue_comment = AsyncMock()
        client.create_pull_request = AsyncMock()
        workspace = SimpleNamespace(path=Path("workspaces/issues/42-fix-the-bug"), branch="ai/42-fix-the-bug")
        result = CodexRunResult(("codex",), 1, "", "failed", 1.0)

        with (
            patch("localforge.main.load_config", return_value=settings),
            patch("localforge.main.GitHubClient", return_value=client),
            patch("localforge.main.WorkspaceManager") as manager,
            patch("localforge.main.run_codex", return_value=result),
            patch("localforge.main.store_run_log", return_value=Path("workspaces/run-logs/issue-42.log")),
        ):
            manager.return_value.prepare_issue.return_value = workspace
            exit_code = await run(apply=True, limit=1)

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            client.move_issue_to_label.await_args_list[-1].args,
            ("octo", "widget", 42, "ai-working", "ai-blocked"),
        )
        self.assertIn("Codex failed", client.create_issue_comment.call_args.args[3])
        manager.return_value.push_issue_branch.assert_not_called()
        client.create_pull_request.assert_not_awaited()
