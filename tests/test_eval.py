"""Checks for the local evaluation runner without starting Codex."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from localforge import eval as evaluation


class EvalTests(unittest.TestCase):
    def test_expected_v1_cases_exist(self) -> None:
        self.assertEqual(evaluation.case_names(),
                         ["create_module", "fix_total", "ghapi_web_get", "review_discount"])

    def test_web_search_needs_tool_event(self) -> None:
        self.assertFalse(evaluation.observed_web_search(
            '{"type":"item.completed","item":{"type":"agent_message",'
            '"text":"I searched the web"}}'))
        self.assertTrue(evaluation.observed_web_search(
            '{"type":"item.completed","item":{"type":"web_search",'
            '"query":"ghapi v2 issues.get"}}'))

    def test_timeout_is_persisted_with_artifacts_and_no_zero_token_claim(self) -> None:
        original = evaluation.run_process

        def fake_process(command, cwd, timeout, environment):
            if command[0] == "codex":
                return None, "", "", True
            return original(command, cwd, timeout, environment)

        with tempfile.TemporaryDirectory() as temp, patch.object(
            evaluation, "run_process", side_effect=fake_process
        ):
            root = Path(temp)
            outcome = evaluation.run_case("create_module", root, "codex", "ignored", 1)
            with closing(sqlite3.connect(root / "localforge.sqlite3")) as db:
                row = db.execute("SELECT status, total_tokens, artifact_path "
                                 "FROM eval_attempts").fetchone()
            self.assertEqual(outcome, 1)
            self.assertEqual(row[0], "timeout")
            self.assertIsNone(row[1])
            self.assertTrue((Path(row[2]) / "metadata.json").is_file())
            self.assertTrue((Path(row[2]) / "diff.patch").is_file())

    def test_hidden_verifier_scores_change_and_records_performance(self) -> None:
        original = evaluation.run_process

        def fake_process(command, cwd, timeout, environment):
            if command[0] == "codex":
                (cwd / "slug.py").write_text(
                    "import re\n\ndef slugify(text):\n"
                    "    return re.sub(r'[ -]+', '-', text.lower()).strip('-')\n",
                    encoding="utf-8",
                )
                return (0, '{"type":"turn.completed","usage":'
                        '{"input_tokens":10,"output_tokens":5}}\n', "", False)
            return original(command, cwd, timeout, environment)

        with tempfile.TemporaryDirectory() as temp, patch.object(
            evaluation, "run_process", side_effect=fake_process
        ):
            root = Path(temp)
            outcome = evaluation.run_case("create_module", root, "codex", "ignored", 5)
            with closing(sqlite3.connect(root / "localforge.sqlite3")) as db:
                row = db.execute("SELECT status, verifier_passed, total_tokens, "
                                 "duration_seconds, artifact_path FROM eval_attempts").fetchone()
            self.assertEqual(outcome, 0)
            self.assertEqual(row[:3], ("passed", 1, 15))
            self.assertGreaterEqual(row[3], 0)
            self.assertIn("slug.py", (Path(row[4]) / "diff.patch").read_text(encoding="utf-8"))

    def test_ghapi_case_checks_exact_operation_and_records_web_use(self) -> None:
        original = evaluation.run_process
        implementations = (
            ("from ghapi.core import GhApi\n"
             "async def fetch_issue(owner, repo, issue_number):\n"
             "    issue = await GhApi().issues.get(owner=owner, repo=repo, "
             "issue_number=issue_number)\n"
             "    return {'title': issue.title, 'body': issue.body}\n", "passed"),
            ("from ghapi.core import GhApi\n"
             "async def fetch_issue(owner, repo, issue_number):\n"
             "    issue = await GhApi().issues.get(owner=owner, repo=repo, number=issue_number)\n"
             "    return {'title': issue.title, 'body': issue.body}\n", "failed"),
            ("from ghapi.core import GhApi\n"
             "async def fetch_issue(owner, repo, issue_number):\n"
             "    issue = await GhApi().issues.list_for_repo(owner=owner, repo=repo, "
             "issue_number=issue_number)\n"
             "    return {'title': issue.title, 'body': issue.body}\n", "failed"),
        )
        for code, expected in implementations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                def fake_process(command, cwd, timeout, environment):
                    if command[0] == "codex":
                        (cwd / "issue_lookup.py").write_text(code, encoding="utf-8")
                        return (0, '{"type":"item.completed","item":'
                                '{"type":"web_search","query":"ghapi v2 issues.get"}}\n'
                                '{"type":"item.completed","item":{"type":"agent_message",'
                                '"text":"Source: https://ghapi.fast.ai/fullapi.html"}}\n',
                                "", False)
                    return original(command, cwd, timeout, environment)

                with patch.object(evaluation, "run_process", side_effect=fake_process):
                    evaluation.run_case("ghapi_web_get", Path(temp), "codex", "ignored", 5)
                with closing(sqlite3.connect(Path(temp) / "localforge.sqlite3")) as db:
                    row = db.execute("SELECT status, web_search_status, source_cited "
                                     "FROM eval_attempts").fetchone()
                self.assertEqual(row, (expected, "observed", 1))


if __name__ == "__main__":
    unittest.main()
