"""Tests for Codex prompt and command construction."""

from __future__ import annotations

import unittest

from localforge.codex_runner import build_codex_command, build_issue_prompt


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

    def test_uses_a_clear_placeholder_for_an_empty_description(self) -> None:
        prompt = build_issue_prompt(42, "Add a health endpoint", None)

        self.assertIn("No description was provided.", prompt)
