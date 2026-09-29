"""Tests for local repository cache and issue worktree preparation."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import call, patch

from localforge.workspace import IssueWorkspace, WorkspaceError, WorkspaceManager, issue_slug


class IssueSlugTests(unittest.TestCase):
    def test_normalizes_title_to_a_safe_path_component(self) -> None:
        self.assertEqual(issue_slug("Fix: café login / OAuth!"), "fix-cafe-login-oauth")

    def test_uses_a_fallback_for_an_empty_title(self) -> None:
        self.assertEqual(issue_slug("---"), "issue")


class WorkspaceManagerTests(unittest.TestCase):
    def test_pushes_the_issue_branch_to_origin(self) -> None:
        manager = WorkspaceManager(Path.cwd() / "workspaces", "octo", "widget")
        workspace = IssueWorkspace(
            Path("workspaces/issues/123-add-health-endpoint"),
            "ai/123-add-health-endpoint",
        )

        with patch.object(manager, "_git") as git:
            manager.push_issue_branch(workspace)

        git.assert_called_once_with(
            "push",
            "--set-upstream",
            "origin",
            "ai/123-add-health-endpoint",
            cwd=Path("workspaces/issues/123-add-health-endpoint"),
        )

    def test_creates_cache_then_issue_worktree(self) -> None:
        root = Path.cwd() / "workspaces"
        manager = WorkspaceManager(root, "octo", "widget")
        with (
            patch("localforge.workspace.Path.exists", return_value=False),
            patch("localforge.workspace.Path.mkdir"),
            patch.object(manager, "_git") as git,
        ):
            workspace = manager.prepare_issue(123, "Add health endpoint")

        self.assertEqual(workspace.branch, "ai/123-add-health-endpoint")
        self.assertEqual(workspace.path, root / "issues" / "123-add-health-endpoint")
        self.assertEqual(
            git.call_args_list,
            [
                call(
                    "clone",
                    "https://github.com/octo/widget.git",
                    str(manager.repository_path),
                ),
                call(
                    "worktree",
                    "add",
                    "-b",
                    "ai/123-add-health-endpoint",
                    str(workspace.path),
                    "origin/HEAD",
                    cwd=manager.repository_path,
                ),
            ],
        )

    def test_reuses_an_existing_worktree_on_the_expected_branch(self) -> None:
        root = Path.cwd() / "workspaces"
        manager = WorkspaceManager(root, "octo", "widget")
        path = root / "issues" / "123-add-health-endpoint"

        def exists(candidate: Path) -> bool:
            return candidate in {manager.repository_path / ".git", path, path / ".git"}

        with (
            patch("localforge.workspace.Path.exists", autospec=True, side_effect=exists),
            patch.object(manager, "_git", return_value="ai/123-add-health-endpoint") as git,
        ):
            workspace = manager.prepare_issue(123, "Add health endpoint")

        self.assertEqual(workspace.path, path)
        self.assertEqual(
            git.call_args_list,
            [
                call("fetch", "--prune", "origin", cwd=manager.repository_path),
                call("branch", "--show-current", cwd=path, capture_output=True),
            ],
        )

    def test_rejects_an_existing_directory_that_is_not_a_worktree(self) -> None:
        root = Path.cwd() / "workspaces"
        manager = WorkspaceManager(root, "octo", "widget")
        path = root / "issues" / "123-add-health-endpoint"

        def exists(candidate: Path) -> bool:
            return candidate in {manager.repository_path / ".git", path}

        with (
            patch("localforge.workspace.Path.exists", autospec=True, side_effect=exists),
            patch.object(manager, "_git"),
            self.assertRaises(WorkspaceError),
        ):
            manager.prepare_issue(123, "Add health endpoint")
