"""Asynchronous GitHub issue operations for LocalForge."""

from __future__ import annotations

import logging
from typing import Any, Literal

from ghapi.core import GhApi
from ghapi.page import paged

logger = logging.getLogger(__name__)


class GitHubClient:
    """Small async wrapper around the GitHub operations LocalForge uses in V1."""

    def __init__(self, token: str):
        self._github = GhApi(token=token)

    async def get_issues(self, owner: str, repo: str, label: str) -> list[Any]:
        """Return all open issues bearing ``label``, excluding pull requests."""
        try:
            issues: list[Any] = []
            pages = paged(
                self._github.issues.list_for_repo,
                owner=owner,
                repo=repo,
                state="open",
                labels=label,
                per_page=100,
            )
            async for page in pages:
                issues.extend(issue for issue in page if "pull_request" not in issue)
            return issues
        except Exception:
            logger.exception("Error fetching issues for %s/%s", owner, repo)
            raise

    async def update_issue_state(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        state: Literal["open", "closed"],
    ) -> bool:
        """Set an issue's GitHub state and return whether the update succeeded."""
        try:
            await self._github.issues.update(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                state=state,
            )
            return True
        except Exception:
            logger.exception("Error updating issue %s", issue_number)
            raise

    async def move_issue_to_label(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        source_label: str,
        target_label: str,
    ) -> None:
        """Replace ``source_label`` with ``target_label`` without losing other labels."""
        try:
            issue = await self._github.issues.get(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
            )
            labels = [label.name for label in issue.labels if label.name != source_label]
            if target_label not in labels:
                labels.append(target_label)
            await self._github.issues.set_labels(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                labels=labels,
            )
        except Exception:
            logger.exception("Error moving issue %s to label %s", issue_number, target_label)
            raise

    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> None:
        """Add a concise LocalForge run-status comment to an issue."""
        try:
            await self._github.issues.create_comment(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                body=body,
            )
        except Exception:
            logger.exception("Error adding a comment to issue %s", issue_number)
            raise
