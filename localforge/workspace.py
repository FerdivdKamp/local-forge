"""Local Git repository and issue-worktree management."""

from __future__ import annotations

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(RuntimeError):
    """Raised when a repository workspace cannot be prepared."""


@dataclass(frozen=True)
class IssueWorkspace:
    """The local branch and directory assigned to one issue."""

    path: Path
    branch: str


def issue_slug(title: str) -> str:
    """Return a short, Git-safe path component based on an issue title."""
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return (slug or "issue")[:72].rstrip("-")


class WorkspaceManager:
    """Maintain one repository cache and one worktree for each issue."""

    def __init__(self, root: Path | str, owner: str, repository: str):
        # Git interprets a worktree path relative to the cached repository's
        # directory, so resolve configuration-relative paths before invoking it.
        self._root = Path(root).resolve()
        self._owner = owner
        self._repository = repository

    @property
    def repository_path(self) -> Path:
        return self._root / "repositories" / self._owner / self._repository

    def prepare_issue(self, issue_number: int, issue_title: str) -> IssueWorkspace:
        """Fetch the cached repository and create an isolated issue worktree."""
        if issue_number < 1:
            raise ValueError("issue_number must be positive")

        branch = f"ai/{issue_number}-{issue_slug(issue_title)}"
        workspace = IssueWorkspace(
            path=self._root / "issues" / f"{issue_number}-{issue_slug(issue_title)}",
            branch=branch,
        )
        self._ensure_repository_cache()

        if workspace.path.exists():
            self._validate_existing_workspace(workspace)
            return workspace

        workspace.path.parent.mkdir(parents=True, exist_ok=True)
        self._git(
            "worktree",
            "add",
            "-b",
            workspace.branch,
            str(workspace.path),
            "origin/HEAD",
            cwd=self.repository_path,
        )
        return workspace

    def push_issue_branch(self, workspace: IssueWorkspace) -> None:
        """Publish an issue branch after Codex has completed successfully."""
        self._git(
            "push",
            "--set-upstream",
            "origin",
            workspace.branch,
            cwd=workspace.path,
        )

    def commit_issue_changes(
        self,
        workspace: IssueWorkspace,
        issue_number: int,
        issue_title: str,
    ) -> bool:
        """Commit all Codex changes, returning whether a commit was created."""
        if not self._git("status", "--porcelain", cwd=workspace.path, capture_output=True):
            return False
        self._git("add", "--all", cwd=workspace.path)
        self._git(
            "commit",
            "-m",
            f"Implement issue #{issue_number}: {issue_title}",
            cwd=workspace.path,
        )
        return True

    def has_issue_branch_changes(self, workspace: IssueWorkspace) -> bool:
        """Return whether the issue branch has commits beyond its base branch."""
        commit_count = self._git(
            "rev-list",
            "--count",
            "origin/HEAD..HEAD",
            cwd=workspace.path,
            capture_output=True,
        )
        return int(commit_count) > 0

    def _ensure_repository_cache(self) -> None:
        repository = self.repository_path
        if (repository / ".git").exists():
            self._git("fetch", "--prune", "origin", cwd=repository)
            return

        if repository.exists() and any(repository.iterdir()):
            raise WorkspaceError(f"Repository cache exists but is not a Git repository: {repository}")

        repository.parent.mkdir(parents=True, exist_ok=True)
        self._git(
            "clone",
            f"https://github.com/{self._owner}/{self._repository}.git",
            str(repository),
        )

    def _validate_existing_workspace(self, workspace: IssueWorkspace) -> None:
        if not (workspace.path / ".git").exists():
            raise WorkspaceError(f"Issue workspace exists but is not a Git worktree: {workspace.path}")
        current_branch = self._git("branch", "--show-current", cwd=workspace.path, capture_output=True)
        if current_branch != workspace.branch:
            raise WorkspaceError(
                f"Issue workspace {workspace.path} is on {current_branch!r}, "
                f"expected {workspace.branch!r}"
            )

    @staticmethod
    def _git(*args: str, cwd: Path | None = None, capture_output: bool = False) -> str:
        command = ["git", *args]
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=True,
                text=True,
                capture_output=capture_output,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise WorkspaceError(f"Git command failed: {' '.join(command)}") from error
        return result.stdout.strip() if capture_output else ""
