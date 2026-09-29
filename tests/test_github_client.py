"""Tests for GitHub pull-request operations."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from localforge.github_client import GitHubClient, PullRequest


class PullRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_an_issue_linked_pull_request_on_the_default_branch(self) -> None:
        client = GitHubClient("token")
        repos = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(default_branch="main"))
        )
        pulls = SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    number=7,
                    html_url="https://github.com/octo/widget/pull/7",
                )
            )
        )
        client._github = SimpleNamespace(repos=repos, pulls=pulls)

        pull_request = await client.create_pull_request(
            "octo", "widget", 42, "Fix the bug", "ai/42-fix-the-bug"
        )

        self.assertEqual(
            pull_request,
            PullRequest(7, "https://github.com/octo/widget/pull/7"),
        )
        repos.get.assert_awaited_once_with(owner="octo", repo="widget")
        pulls.create.assert_awaited_once_with(
            owner="octo",
            repo="widget",
            title="Fix the bug",
            head="ai/42-fix-the-bug",
            base="main",
            body="Closes #42\n\nCreated by LocalForge from the issue worktree.",
        )
