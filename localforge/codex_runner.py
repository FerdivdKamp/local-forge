"""Build Codex task prompts and command lines for LocalForge runs."""

from __future__ import annotations

from textwrap import dedent


DEFAULT_OSS_MODEL = "unsloth/qwen3-coder-30b-a3b-instruct"


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
        change GitHub issue state, or access LocalForge credentials.

        Issue title: {title.strip()}

        Issue description:
        {description}

        Implement the requested change, add or update relevant tests, and run the
        appropriate test commands. At the end, report the files changed and the
        tests run with their result.
        """
    ).strip()
