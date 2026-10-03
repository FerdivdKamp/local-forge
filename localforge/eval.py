"""Small, local Codex evaluation suite. No GitHub operations are performed."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from localforge.codex_events import parse_codex_events
from localforge.codex_runner import build_codex_command, sanitized_environment
from localforge.config import load_config


ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval_cases" / "v1"
PROMPT_VERSION = "v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_names() -> list[str]:
    return sorted(path.name for path in CASES.iterdir() if (path / "case.json").is_file())


def database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            case_id TEXT PRIMARY KEY, suite TEXT NOT NULL, category TEXT NOT NULL,
            fixture_revision TEXT NOT NULL, rubric_version TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS eval_attempts (
            id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, suite TEXT NOT NULL,
            fixture_revision TEXT NOT NULL, rubric_version TEXT NOT NULL,
            route TEXT NOT NULL,
            model TEXT NOT NULL, mode TEXT NOT NULL, settings_json TEXT NOT NULL,
            prompt_version TEXT NOT NULL, started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL, status TEXT NOT NULL, exit_code INTEGER,
            duration_seconds REAL NOT NULL, input_tokens INTEGER,
            output_tokens INTEGER, total_tokens INTEGER, artifact_path TEXT NOT NULL,
            verifier_passed INTEGER, verifier_exit_code INTEGER, failure_reason TEXT,
            agent_tests_json TEXT NOT NULL, web_search_status TEXT,
            source_cited INTEGER
        );
    """)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(eval_attempts)")}
    if "web_search_status" not in columns:
        connection.execute("ALTER TABLE eval_attempts ADD COLUMN web_search_status TEXT")
    if "source_cited" not in columns:
        connection.execute("ALTER TABLE eval_attempts ADD COLUMN source_cited INTEGER")
    return connection


def observed_web_search(stream: str) -> bool:
    """Only a completed search tool event counts, never the agent's own claim."""
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search" and item.get("query"):
            return True
        if (item.get("type") == "mcp_tool_call" and
                item.get("tool") in {"web.run", "web__run"}):
            return True
    return False


def run_process(command: tuple[str, ...] | list[str], cwd: Path, timeout: int,
                environment: dict[str, str]) -> tuple[int | None, str, str, bool]:
    try:
        result = subprocess.run(command, cwd=cwd, env=environment, text=True,
                                encoding="utf-8", errors="replace", capture_output=True,
                                timeout=timeout, check=False)
        return result.returncode, result.stdout, result.stderr, False
    except subprocess.TimeoutExpired as error:
        def decode(value: bytes | str | None) -> str:
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value or ""
        return None, decode(error.stdout), decode(error.stderr), True
    except OSError as error:
        return 127, "", str(error), False


def run_case(name: str, root: Path, mode: str, model: str, timeout: int,
             web_access: str = "live") -> int:
    case_dir = CASES / name
    spec = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    artifacts = root / "run-logs" / "eval"
    artifacts.mkdir(parents=True, exist_ok=True)
    # A unique artifact directory also preserves failed and timed-out attempts.
    import uuid
    attempt_dir = artifacts / f"{name}-{uuid.uuid4().hex[:12]}"
    attempt_dir.mkdir()
    workspace = attempt_dir / "workspace"
    shutil.copytree(case_dir / "fixture", workspace)
    git_env = sanitized_environment()
    git_env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    for command in (("git", "init", "-q"), ("git", "add", "."),
                    ("git", "-c", "user.name=LocalForge Eval", "-c",
                     "user.email=eval@localhost", "commit", "-qm", "fixture")):
        code, _, stderr, _ = run_process(command, workspace, 30, git_env)
        if code != 0:
            raise RuntimeError(f"Could not create fixture commit: {stderr}")
    revision = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=workspace,
                                       text=True).strip()
    prompt = (case_dir / "prompt.txt").read_text(encoding="utf-8").strip()
    prompt = ("Read AGENTS.md. Work only in this repository. Do not commit, push, "
              "create pull requests, or access external credentials.\n\n" + prompt)
    (attempt_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    started_at = now()
    started = time.monotonic()
    web_override = ("-c", f'web_search="{web_access}"') if spec.get("web_search") else ()
    command = (*build_codex_command(mode, model), "exec", *web_override,
               "--approve-for-me", "--json", "--color", "never", prompt)
    exit_code, stdout, stderr, timed_out = run_process(command, workspace, timeout,
                                                        sanitized_environment())
    duration = time.monotonic() - started
    events = parse_codex_events(stdout)
    web_status = ("not_required" if not spec.get("web_search") else
                  "unavailable" if web_access == "disabled" else
                  "observed" if observed_web_search(stdout) else "unobserved")
    source_cited = ("https://ghapi.fast.ai/" in (events.final_message or "")
                    if spec.get("web_search") else None)
    (attempt_dir / "codex.jsonl").write_text(stdout, encoding="utf-8")
    (attempt_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    (attempt_dir / "response.txt").write_text(events.final_message or "", encoding="utf-8")
    # Intent-to-add makes newly created files visible in the saved diff.
    subprocess.run(("git", "add", "-N", "."), cwd=workspace,
                   capture_output=True, check=False)
    diff = subprocess.run(("git", "diff", "HEAD", "--"), cwd=workspace, text=True,
                          encoding="utf-8", errors="replace", capture_output=True,
                          check=False).stdout
    (attempt_dir / "diff.patch").write_text(diff, encoding="utf-8")
    verifier_code = None
    verifier_passed = None
    reason = None
    if timed_out:
        status = "timeout"
        reason = "Codex timeout"
    elif spec["route"] == "review":
        # Review accuracy needs adjudication against the answer key by a person.
        status = "needs_review" if exit_code == 0 else "failed"
        if diff or subprocess.run(("git", "ls-files", "--others", "--exclude-standard"),
                                  cwd=workspace, text=True, capture_output=True,
                                  check=False).stdout.strip():
            status = "failed"
            reason = "Review changed repository files"
    elif exit_code != 0:
        status = "failed"
        reason = f"Codex exit {exit_code}"
    else:
        verify_env = sanitized_environment()
        verify_env["PYTHONPATH"] = str(workspace)
        verifier = ROOT / "eval_verifiers" / f"{name}.py"
        verifier_code, verify_out, verify_err, verify_timeout = run_process(
            (sys.executable, str(verifier)), workspace, 30, verify_env)
        (attempt_dir / "verification.txt").write_text(verify_out + verify_err,
                                                      encoding="utf-8")
        verifier_passed = verifier_code == 0 and not verify_timeout
        status = "passed" if verifier_passed else "failed"
        if not verifier_passed:
            reason = "Verifier timeout" if verify_timeout else f"Verifier exit {verifier_code}"
    changed = subprocess.run(("git", "status", "--short"), cwd=workspace, text=True,
                             capture_output=True, check=False).stdout
    (attempt_dir / "changed-files.txt").write_text(changed, encoding="utf-8")
    metadata = {"case": name, "suite": "v1", "fixture_revision": spec["revision"],
                "starting_commit": revision, "mode": mode, "model": model,
                "command": list(command[:-1]), "timeout_seconds": timeout,
                "web_search_status": web_status,
                "source_cited": source_cited,
                "codex_version": "unknown", "seed": "unknown", "settings": "unknown",
                "started_at": started_at, "finished_at": now()}
    (attempt_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with closing(database(root / "localforge.sqlite3")) as db, db:
        db.execute("INSERT OR REPLACE INTO eval_cases VALUES (?, ?, ?, ?, ?)",
                   (name, "v1", spec["category"], spec["revision"], spec["rubric_version"]))
        cursor = db.execute("""INSERT INTO eval_attempts (
            case_id, suite, fixture_revision, rubric_version, route, model, mode,
            settings_json, prompt_version, started_at,
            finished_at, status, exit_code, duration_seconds, input_tokens,
            output_tokens, total_tokens, artifact_path, verifier_passed,
            verifier_exit_code, failure_reason, agent_tests_json, web_search_status,
            source_cited
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, "v1", spec["revision"], spec["rubric_version"], spec["route"],
             model, mode, json.dumps({"timeout_seconds": timeout,
             "inference_settings": "unknown", "web_access": web_access}),
             PROMPT_VERSION, started_at, now(),
             status, exit_code, duration, events.usage.input_tokens if events.usage else None,
             events.usage.output_tokens if events.usage else None,
             events.usage.total_tokens if events.usage else None, str(attempt_dir),
             verifier_passed, verifier_code, reason,
             json.dumps([vars(test) for test in events.test_runs]), web_status,
             source_cited))
        attempt_id = cursor.lastrowid
    print(f"{attempt_id}: {name}: {status} ({duration:.2f}s) {attempt_dir}")
    return 0 if status in {"passed", "needs_review"} else 1


def report(root: Path) -> None:
    with closing(database(root / "localforge.sqlite3")) as db:
        rows = db.execute("""SELECT suite, case_id, fixture_revision, rubric_version,
            route, model, mode, settings_json,
            status, duration_seconds, total_tokens, artifact_path, failure_reason,
            web_search_status, source_cited
            FROM eval_attempts ORDER BY case_id, route, model, id""").fetchall()
    groups: dict[tuple[str, ...], list[sqlite3.Row]] = {}
    for row in rows:
        key = tuple(row[field] for field in ("suite", "case_id", "fixture_revision",
                                            "rubric_version", "route", "model", "mode",
                                            "settings_json"))
        groups.setdefault(key, []).append(row)
    if not groups:
        print("No evaluation attempts recorded.")
    for key, attempts in groups.items():
        passed = sum(row["status"] == "passed" for row in attempts)
        durations = [row["duration_seconds"] for row in attempts]
        tokens = [row["total_tokens"] for row in attempts if row["total_tokens"] is not None]
        web_observed = sum(row["web_search_status"] == "observed" for row in attempts)
        print(f"{key[0]} / {key[1]} rev {key[2]} / {key[4]} / {key[5]} "
              f"({key[6]}, {key[7]}): {passed}/{len(attempts)} verified; "
              f"time median {statistics.median(durations):.2f}s "
              f"(range {min(durations):.2f}-{max(durations):.2f}s); "
              f"tokens median {statistics.median(tokens) if tokens else 'unknown'}")
        if any(row["web_search_status"] != "not_required" for row in attempts):
            citations = sum(bool(row["source_cited"]) for row in attempts)
            print(f"  web search observed: {web_observed}/{len(attempts)}; "
                  f"official source cited: {citations}/{len(attempts)}")
        for row in attempts:
            print(f"  {row['status']}: {row['failure_reason'] or '-'} {row['artifact_path']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--suite", choices=["v1"], default="v1")
    run.add_argument("--case", choices=case_names())
    run.add_argument("--mode", choices=["codex", "lm-studio"], default="lm-studio")
    run.add_argument("--model")
    run.add_argument("--repeat", type=int, default=1)
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--web-access", choices=["live", "disabled"], default="live")
    sub.add_parser("report")
    args = parser.parse_args(argv)
    configured = load_config()
    root = Path(configured.workspace_root or "../workspaces").resolve()
    if args.command == "report":
        report(root)
        return 0
    if args.repeat < 1 or args.timeout < 1:
        parser.error("--repeat and --timeout must be positive")
    model = args.model or configured.codex_model
    failures = 0
    for _ in range(args.repeat):
        for name in ([args.case] if args.case else case_names()):
            failures += run_case(name, root, args.mode, model, args.timeout,
                                 args.web_access)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
