"""Tests for local SQLite run state and structured events."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from localforge.run_log import log_event
from localforge.run_state import RunStore


class RunStateTests(unittest.TestCase):
    def test_records_run_lifecycle_and_reopens_database(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "localforge.sqlite3"
            store = RunStore(path)
            run_id = store.start("octo", "widget", 42, "local-model")
            store.update(run_id, workspace_path="issues/42", branch="ai/42-fix")
            RunStore(path).update(
                run_id, status="completed", exit_code=0, duration_seconds=2.5,
                log_path="run-logs/42.log", pr_number=7, pr_url="https://example.test/pr/7",
                input_tokens=100, cached_input_tokens=20, output_tokens=30,
                reasoning_output_tokens=5, total_tokens=130,
                tests_json='[{"command": "pytest", "exit_code": 0}]',
                tests_status="passed", files_changed_json='["src/app.py"]',
                files_changed_count=1,
            )
            with closing(sqlite3.connect(path)) as connection:
                row = connection.execute(
                    "SELECT owner, repository, issue_number, status, started_at, "
                    "finished_at, model, branch, exit_code, duration_seconds, pr_number "
                    "FROM runs WHERE id = ?", (run_id,),
                ).fetchone()
            self.assertEqual(row[:4], ("octo", "widget", 42, "completed"))
            self.assertTrue(row[4])
            self.assertTrue(row[5])
            self.assertEqual(row[6:], ("local-model", "ai/42-fix", 0, 2.5, 7))
            with closing(sqlite3.connect(path)) as connection:
                metrics = connection.execute(
                    "SELECT total_tokens, tests_status, files_changed_count FROM runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
            self.assertEqual(metrics, (130, "passed", 1))

    def test_adds_metrics_columns_to_existing_database(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "localforge.sqlite3"
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY)")
            RunStore(path)
            with closing(sqlite3.connect(path)) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
            self.assertIn("total_tokens", columns)
            self.assertIn("files_changed_count", columns)

    def test_structured_events_are_json_lines(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            log_event(directory, "run_started", run_id=1, issue_number=42)
            log_event(directory, "run_finished", run_id=1, status="completed")
            lines = (Path(directory) / "events.jsonl").read_text(encoding="utf-8").splitlines()
            records = [json.loads(line) for line in lines]
            self.assertEqual([record["event"] for record in records],
                             ["run_started", "run_finished"])
            self.assertEqual(records[0]["issue_number"], 42)
            self.assertTrue(all(record["timestamp"] for record in records))
