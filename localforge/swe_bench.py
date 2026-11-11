"""Small SWE-bench Lite pilot; no GitHub issue or PR operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from localforge.codex_events import parse_codex_events
from localforge.codex_runner import build_codex_command, sanitized_environment
from localforge.config import load_config
from localforge.eval import run_process


DATASET = "SWE-bench/SWE-bench_Lite"
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_INSTANCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
# Codex's Windows sandbox may create this virtual system-drive cache in cwd.
_PATCH_PATHS = (".", ":(exclude)%SystemDrive%/")


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_rows(path: Path) -> dict[str, dict]:
    """Read an exported test-split JSONL without importing benchmark dependencies."""
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"dataset line {number} is not an object")
            row = item.get("row", item)
            if not isinstance(row, dict):
                raise ValueError(f"dataset line {number} has no row object")
            instance_id = row.get("instance_id")
            if not isinstance(instance_id, str) or not instance_id:
                raise ValueError(f"dataset line {number} has no instance_id")
            if instance_id in rows:
                raise ValueError(f"duplicate instance_id: {instance_id}")
            rows[instance_id] = row
    return rows


def _validate_row(row: dict) -> None:
    instance_id = row.get("instance_id")
    if not isinstance(instance_id, str) or not _INSTANCE.fullmatch(instance_id) or ".." in instance_id:
        raise ValueError(f"invalid instance_id: {instance_id}")
    repo, commit, problem = (row.get(key) for key in
                             ("repo", "base_commit", "problem_statement"))
    if not isinstance(repo, str) or not _REPO.fullmatch(repo) or ".." in repo:
        raise ValueError(f"invalid repository for {row.get('instance_id')}")
    if not isinstance(commit, str) or not _SHA.fullmatch(commit):
        raise ValueError(f"invalid base_commit for {row.get('instance_id')}")
    if not isinstance(problem, str) or not problem.strip():
        raise ValueError(f"missing problem_statement for {row.get('instance_id')}")


def _fetch_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": "LocalForge-SWE-bench-pilot"})
    with urlopen(request, timeout=60) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError(f"unexpected response from {url}")
    return value


def fetch(output: Path) -> tuple[str, int]:
    """Download the complete Lite test metadata through the dataset viewer API."""
    if output.exists():
        raise FileExistsError(f"dataset file already exists: {output}")
    info_url = "https://huggingface.co/api/datasets/SWE-bench/SWE-bench_Lite"
    revision = _fetch_json(info_url).get("sha")
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise ValueError("Hugging Face did not provide a dataset commit SHA")
    rows: list[dict] = []
    total = None
    while total is None or len(rows) < total:
        query = urlencode({"dataset": DATASET, "config": "default", "split": "test",
                           "offset": len(rows), "length": 100})
        page = _fetch_json(f"https://datasets-server.huggingface.co/rows?{query}")
        if total is None:
            total = page.get("num_rows_total")
            if type(total) is not int or total < 5 or total > 1000:
                raise ValueError("unexpected Lite test split size")
        if page.get("num_rows_total") != total or page.get("partial"):
            raise ValueError("incomplete or changing dataset viewer response")
        items = page.get("rows")
        if not isinstance(items, list) or not items:
            raise ValueError("dataset viewer returned no rows")
        for item in items:
            if (not isinstance(item, dict) or item.get("row_idx") != len(rows) or
                    item.get("truncated_cells") or not isinstance(item.get("row"), dict)):
                raise ValueError("dataset viewer returned a truncated or unordered row")
            rows.append(item["row"])
    if len(rows) != total or _fetch_json(info_url).get("sha") != revision:
        raise ValueError("dataset revision changed during download")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                      encoding="utf-8")
    _json(output.with_suffix(".meta.json"), {"dataset": DATASET, "split": "test",
                                             "revision": revision, "rows": total,
                                             "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                                             "source": "Hugging Face dataset viewer /rows API"})
    return revision, total


def select(dataset: Path, revision: str, output: Path, count: int = 5,
           ids: list[str] | None = None) -> list[str]:
    if not revision.strip():
        raise ValueError("a pinned dataset revision is required")
    if not 1 <= count <= 10:
        raise ValueError("select between one and ten instances")
    rows = load_rows(dataset)
    if ids is not None:
        if len(ids) != count or len(set(ids)) != count or any(item not in rows for item in ids):
            raise ValueError("--instance IDs must be unique, present in the dataset, and match --count")
        candidates = [rows[item] for item in ids]
    else:
        candidates = sorted(rows.values(), key=lambda row: hashlib.sha256(
            str(row["instance_id"]).encode("utf-8")).hexdigest())
    chosen: list[dict] = []
    repos: set[str] = set()
    for row in candidates:
        _validate_row(row)
        if ids is None and row["repo"] in repos:
            continue
        chosen.append({key: row[key] for key in ("instance_id", "repo", "base_commit")})
        repos.add(row["repo"])
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise ValueError(f"need {count} valid instances from distinct repositories")
    if output.exists():
        raise FileExistsError(f"manifest already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    _json(output, {"dataset": DATASET, "split": "test", "revision": revision,
                   "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                   "selection": ("explicit instance IDs" if ids is not None else
                                 "SHA-256 instance_id order; distinct repositories"),
                   "instances": chosen})
    return [entry["instance_id"] for entry in chosen]


def selected_rows(dataset: Path, manifest: Path) -> tuple[dict, list[dict]]:
    spec = json.loads(manifest.read_text(encoding="utf-8"))
    if spec.get("dataset") != DATASET or spec.get("split") != "test":
        raise ValueError("manifest must identify the SWE-bench Lite test split")
    if not isinstance(spec.get("revision"), str) or not spec["revision"].strip():
        raise ValueError("manifest is missing the dataset revision")
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != spec.get("dataset_sha256"):
        raise ValueError("dataset file does not match the manifest SHA-256")
    entries = spec.get("instances")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 10:
        raise ValueError("the pilot manifest must have one to ten instances")
    rows = load_rows(dataset)
    selected = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid manifest entry")
        instance_id = entry.get("instance_id")
        if not isinstance(instance_id, str):
            raise ValueError("manifest entry is missing instance_id")
        if instance_id in seen or instance_id not in rows:
            raise ValueError(f"duplicate or missing instance: {instance_id}")
        seen.add(instance_id)
        row = rows[instance_id]
        _validate_row(row)
        if any(entry.get(key) != row[key] for key in ("repo", "base_commit")):
            raise ValueError(f"manifest mismatch: {instance_id}")
        selected.append(row)
    return spec, selected


def _git(command: tuple[str, ...], cwd: Path, timeout: int = 180) -> str:
    environment = sanitized_environment()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    code, stdout, stderr, timed_out = run_process(("git", *command), cwd, timeout,
                                                   environment)
    if code != 0 or timed_out:
        raise RuntimeError(f"git {command[0]} failed: {stderr.strip() or stdout.strip()}")
    return stdout


def _repo_cache(repo: str, cache: Path, allow_clone: bool) -> Path:
    path = cache / repo.replace("/", "__")
    if not path.is_dir():
        if not allow_clone:
            raise FileNotFoundError(f"missing {path}; populate it or pass --allow-clone")
        cache.mkdir(parents=True, exist_ok=True)
        _git(("clone", "--quiet", f"https://github.com/{repo}.git", str(path)), cache, 1800)
    if _git(("rev-parse", "--is-inside-work-tree"), path).strip() != "true":
        raise ValueError(f"not a Git repository: {path}")
    return path


def _prepare(row: dict, cache: Path, workspace: Path, allow_clone: bool) -> None:
    source = _repo_cache(row["repo"], cache, allow_clone)
    _git(("cat-file", "-e", f"{row['base_commit']}^{{commit}}"), source)
    _git(("clone", "--quiet", "--no-hardlinks", str(source), str(workspace)),
         workspace.parent, 1800)
    _git(("checkout", "--quiet", "--detach", row["base_commit"]), workspace)
    if _git(("rev-parse", "HEAD"), workspace).strip() != row["base_commit"]:
        raise RuntimeError("checkout did not reach the expected base commit")
    if _git(("status", "--porcelain"), workspace).strip():
        raise RuntimeError("workspace is not clean at the base commit")


def _prompt(problem: str) -> str:
    return ("Solve the following issue in this repository. Read the repository "
            "instructions. Work only in this workspace. Do not commit, push, "
            "create a pull request, or access external credentials or network "
            "resources. On Windows, the shell is PowerShell; write source files "
            "as UTF-8 rather than using echo redirection. Make the smallest "
            "correct code change and run relevant "
            "local tests if possible. The benchmark will grade the final patch.\n\n"
            "Issue:\n" + problem.strip())


def run_instance(row: dict, cache: Path, run_dir: Path, mode: str, model: str,
                 timeout: int, allow_clone: bool) -> dict:
    instance_id = row["instance_id"]
    attempt = run_dir / instance_id
    attempt.mkdir()
    workspace = attempt / "workspace"
    result = {"instance_id": instance_id, "repo": row["repo"],
              "base_commit": row["base_commit"], "status": "setup_error",
              "exit_code": None, "duration_seconds": 0.0, "total_tokens": None,
              "artifact_path": str(attempt)}
    started = time.monotonic()
    try:
        _prepare(row, cache, workspace, allow_clone)
        prompt = _prompt(row["problem_statement"])
        (attempt / "prompt.txt").write_text(prompt, encoding="utf-8")
        command = (*build_codex_command(mode, model), "--sandbox", "workspace-write",
                   "--ask-for-approval", "never", "exec", "-c",
                   'web_search="disabled"', "-c", 'model_reasoning_effort="low"',
                   "--json", "--color", "never", prompt)
        code, stdout, stderr, timed_out = run_process(command, workspace, timeout,
                                                       sanitized_environment())
        (attempt / "codex.jsonl").write_text(stdout, encoding="utf-8")
        (attempt / "stderr.txt").write_text(stderr, encoding="utf-8")
        events = parse_codex_events(stdout)
        (attempt / "response.txt").write_text(events.final_message or "", encoding="utf-8")
        _git(("add", "-N", "--", *_PATCH_PATHS), workspace)
        patch = _git(("diff", "--binary", row["base_commit"], "--", *_PATCH_PATHS),
                     workspace)
        (attempt / "diff.patch").write_text(patch, encoding="utf-8")
        result.update(exit_code=code,
                      total_tokens=events.usage.total_tokens if events.usage else None,
                      status=("timeout" if timed_out else "agent_failed" if code != 0
                              else "empty_patch" if not patch else "ready"))
        result["model_patch"] = patch
    except (OSError, RuntimeError, ValueError) as error:
        result["error"] = str(error)
        result["model_patch"] = ""
    finally:
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        _json(attempt / "result.json", {key: value for key, value in result.items()
                                         if key != "model_patch"})
    return result


def run(dataset: Path, manifest: Path, root: Path, run_id: str, mode: str,
        model: str, timeout: int, cache: Path, allow_clone: bool) -> int:
    spec, rows = selected_rows(dataset, manifest)
    if not _RUN_ID.fullmatch(run_id) or ".." in run_id or timeout < 1:
        raise ValueError("run ID must be a safe name and timeout must be positive")
    run_dir = root / "run-logs" / "swe-bench-lite" / run_id
    if run_dir.exists():
        raise FileExistsError(f"run already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    _json(run_dir / "run.json", {"dataset": DATASET, "split": "test",
                                  "revision": spec["revision"], "model": model,
                                  "mode": mode, "timeout_seconds": timeout,
                                  "web_access": "disabled", "reasoning_effort": "low",
                                  "dataset_sha256": spec["dataset_sha256"],
                                  "instance_ids": [row["instance_id"] for row in rows]})
    results = [run_instance(row, cache, run_dir, mode, model, timeout, allow_clone)
               for row in rows]
    predictions = run_dir / "predictions.jsonl"
    with predictions.open("w", encoding="utf-8") as stream:
        for result in results:
            stream.write(json.dumps({"instance_id": result["instance_id"],
                                     "model_name_or_path": model,
                                     "model_patch": result["model_patch"]},
                                    ensure_ascii=False) + "\n")
    _json(run_dir / "results.json", [{key: value for key, value in result.items()
                                      if key != "model_patch"} for result in results])
    print(f"Predictions: {predictions}")
    for result in results:
        print(f"{result['instance_id']}: {result['status']}")
    return 0 if all(result["status"] == "ready" for result in results) else 1


def grade(root: Path, run_id: str, swebench: str) -> int:
    if not _RUN_ID.fullmatch(run_id) or ".." in run_id:
        raise ValueError("invalid run ID")
    run_dir = root / "run-logs" / "swe-bench-lite" / run_id
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    predictions = run_dir / "predictions.jsonl"
    if not predictions.is_file():
        raise FileNotFoundError(predictions)
    harness_id = f"{run_id}-grade-{uuid.uuid4().hex[:8]}"
    command = (swebench, "eval", "lite", "-p", str(predictions),
               "--run-id", harness_id, "-j", "1", *(arg for instance_id in
               meta["instance_ids"] for arg in ("-i", instance_id)))
    completed = subprocess.run(command, cwd=run_dir,
                               env=sanitized_environment(), check=False)
    print(f"Harness results: {run_dir / 'logs' / 'evaluation' / harness_id}")
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("fetch", help="download Lite test metadata to local JSONL")
    download.add_argument("--dataset", type=Path, required=True)
    pick = sub.add_parser("select", help="pin Lite test instances")
    pick.add_argument("--dataset", type=Path, required=True)
    pick.add_argument("--revision", required=True)
    pick.add_argument("--manifest", type=Path, required=True)
    pick.add_argument("--count", type=int, default=5)
    pick.add_argument("--instance", action="append", dest="instances")
    execute = sub.add_parser("run", help="run the five pinned instances")
    execute.add_argument("--dataset", type=Path, required=True)
    execute.add_argument("--manifest", type=Path, required=True)
    execute.add_argument("--run-id", required=True)
    execute.add_argument("--mode", choices=("lm-studio", "codex"), default="lm-studio")
    execute.add_argument("--model")
    execute.add_argument("--timeout", type=int, default=600)
    execute.add_argument("--repo-cache", type=Path)
    execute.add_argument("--allow-clone", action="store_true")
    evaluate = sub.add_parser("grade", help="run the official SWE-bench harness")
    evaluate.add_argument("--run-id", required=True)
    evaluate.add_argument("--swebench", default="swebench")
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            revision, total = fetch(args.dataset)
            print(f"Downloaded {total} Lite test rows; dataset revision: {revision}")
            return 0
        if args.command == "select":
            for instance_id in select(args.dataset, args.revision, args.manifest,
                                      args.count, args.instances):
                print(instance_id)
            return 0
        root = Path(load_config().workspace_root or "../workspaces").resolve()
        if args.command == "grade":
            return grade(root, args.run_id, args.swebench)
        return run(args.dataset, args.manifest, root, args.run_id, args.mode,
                   args.model or load_config().codex_model, args.timeout,
                   (args.repo_cache or root / "swe-bench-repos").resolve(),
                   args.allow_clone)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
