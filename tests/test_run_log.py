"""Tests for local Codex run logs."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from localforge.codex_runner import CodexRunResult
from localforge.run_log import store_run_log


class RunLogTests(unittest.TestCase):
    def test_stores_captured_output_in_a_local_log_file(self) -> None:
        result = CodexRunResult(
            ("codex", "exec", "--color", "never", "implement it"),
            1,
            "standard output",
            "standard error",
            2.5,
        )

        with (
            patch("localforge.run_log.Path.mkdir") as mkdir,
            patch("localforge.run_log.Path.write_text") as write_text,
        ):
            path = store_run_log(
                Path("workspaces") / "run-logs",
                42,
                Path("workspaces/issues/42-implement-it"),
                "ai/42-implement-it",
                result,
            )

        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        write_text.assert_called_once()
        contents = write_text.call_args.args[0]

        self.assertEqual(path.parent.name, "run-logs")
        self.assertIn("Issue: #42", contents)
        self.assertIn("Branch: ai/42-implement-it", contents)
        self.assertIn("Exit status: 1", contents)
        self.assertIn("standard output", contents)
        self.assertIn("standard error", contents)
        self.assertNotIn("implement it", contents)
