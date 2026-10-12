"""SQLite history of local issue runs."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    """Persist each run independently of the GitHub issue state."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY,
                    owner TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    workspace_path TEXT,
                    branch TEXT,
                    model TEXT,
                    exit_code INTEGER,
                    duration_seconds REAL,
                    log_path TEXT,
                    pr_number INTEGER,
                    pr_url TEXT,
                    error TEXT,
                    input_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    output_tokens INTEGER,
                    reasoning_output_tokens INTEGER,
                    total_tokens INTEGER,
                    tests_json TEXT,
                    tests_status TEXT,
                    files_changed_json TEXT,
                    files_changed_count INTEGER
                )
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
            for name, kind in (
                ("input_tokens", "INTEGER"), ("cached_input_tokens", "INTEGER"),
                ("output_tokens", "INTEGER"), ("reasoning_output_tokens", "INTEGER"),
                ("total_tokens", "INTEGER"), ("tests_json", "TEXT"),
                ("tests_status", "TEXT"), ("files_changed_json", "TEXT"),
                ("files_changed_count", "INTEGER"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {kind}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def start(self, owner: str, repository: str, issue_number: int, model: str | None) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO runs (owner, repository, issue_number, status, started_at, model) "
                "VALUES (?, ?, ?, 'running', ?, ?)",
                (owner, repository, issue_number, _now(), model),
            )
            return cursor.lastrowid

    def update(self, run_id: int, **fields: object) -> None:
        allowed = {
            "status", "workspace_path", "branch", "exit_code", "duration_seconds",
            "log_path", "pr_number", "pr_url", "error",
            "input_tokens", "cached_input_tokens", "output_tokens",
            "reasoning_output_tokens", "total_tokens", "tests_json",
            "tests_status", "files_changed_json", "files_changed_count",
        }
        if not fields or fields.keys() - allowed:
            raise ValueError("invalid run fields")
        if fields.get("status") in {"completed", "blocked", "failed"}:
            fields["finished_at"] = _now()
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                f"UPDATE runs SET {assignments} WHERE id = ?",
                (*fields.values(), run_id),
            )
