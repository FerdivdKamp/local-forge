"""Tests for Codex prompt and command construction."""

from __future__ import annotations

import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from localforge.codex_runner import (
    build_codex_command,
    build_issue_prompt,
    run_codex,
    sanitized_environment,
)


class CodexCommandTests(unittest.TestCase):
    def test_standard_mode_uses_the_normal_codex_command(self) -> None:
        self.assertEqual(build_codex_command("codex"), ("codex",))

    def test_lm_studio_mode_uses_oss_with_the_configured_model(self) -> None:
        self.assertEqual(
            build_codex_command("lm-studio", "local/model"),
            ("codex", "--oss", "-m", "local/model"),
        )

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_codex_command("other")


class IssuePromptTests(unittest.TestCase):
    def test_includes_issue_details_and_v1_boundaries(self) -> None:
        prompt = build_issue_prompt(42, "Add a health endpoint", "Return the version too.")

        self.assertIn("GitHub issue #42", prompt)
        self.assertIn("Issue title: Add a health endpoint", prompt)
        self.assertIn("Return the version too.", prompt)
        self.assertIn("Do not push branches", prompt)
        self.assertIn("commit changes", prompt)
        self.assertIn("LocalForge will commit and publish", prompt)

    def test_uses_a_clear_placeholder_for_an_empty_description(self) -> None:
        prompt = build_issue_prompt(42, "Add a health endpoint", None)

        self.assertIn("No description was provided.", prompt)


class CodexRunnerTests(unittest.TestCase):
    def test_sanitized_environment_excludes_credentials(self) -> None:
        environment = sanitized_environment(
            {
                "Path": "C:\\Windows",
                "GITHUB_TOKEN": "secret",
                "OPENAI_API_KEY": "secret",
                "UNRELATED_SETTING": "value",
            }
        )

        self.assertEqual(environment, {"Path": "C:\\Windows"})

    def test_runs_codex_exec_in_the_workspace_and_captures_result(self) -> None:
        completed = CompletedProcess(
            args=(), returncode=0, stdout="implemented", stderr=""
        )
        with (
            patch("localforge.codex_runner.subprocess.run", return_value=completed) as run,
            patch("localforge.codex_runner.time.monotonic", side_effect=(10.0, 12.5)),
            patch("localforge.codex_runner.sanitized_environment", return_value={"Path": "safe"}),
        ):
            result = run_codex(Path("worktree"), "codex", "ignored", "Fix the bug")

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "implemented")
        self.assertEqual(result.duration_seconds, 2.5)
        run.assert_called_once_with(
            ("codex", "exec", "--approve-for-me", "--color", "never", "Fix the bug"),
            cwd=Path("worktree"),
            env={"Path": "safe"},
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

    def test_returns_a_failed_result_when_codex_cannot_start(self) -> None:
        with (
            patch("localforge.codex_runner.subprocess.run", side_effect=FileNotFoundError("codex")),
            patch("localforge.codex_runner.time.monotonic", side_effect=(10.0, 10.5)),
        ):
            result = run_codex(Path("worktree"), "codex", "ignored", "Fix the bug")

        self.assertEqual(result.exit_code, 127)
        self.assertIn("codex", result.stderr)
