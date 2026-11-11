"""SWE-bench pilot tests use local Git repositories, never Docker or a model."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from localforge import swe_bench


class SweBenchPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "repos"
        self.cache.mkdir()
        self.dataset = self.root / "lite.jsonl"
        self.manifest = self.root / "five.json"
        self.rows = []
        for index in range(5):
            repo = f"example/project{index}"
            source = self.cache / repo.replace("/", "__")
            source.mkdir()
            self.git(source, "init", "-q")
            self.git(source, "-c", "user.name=Test", "-c",
                     "user.email=test@example.com", "commit", "-qm", "base", "--allow-empty")
            commit = self.git(source, "rev-parse", "HEAD").strip()
            self.rows.append({"instance_id": f"example__project{index}-1",
                              "repo": repo, "base_commit": commit,
                              "problem_statement": f"Create answer for project {index}.",
                              "patch": "SECRET_REFERENCE_PATCH",
                              "test_patch": "SECRET_HIDDEN_TEST"})
        self.dataset.write_text("".join(json.dumps(row) + "\n" for row in self.rows),
                                encoding="utf-8")

    @staticmethod
    def git(cwd: Path, *args: str) -> str:
        result = subprocess.run(("git", *args), cwd=cwd, text=True,
                                capture_output=True, check=True)
        return result.stdout

    def test_select_pins_five_and_rejects_dataset_drift(self) -> None:
        ids = swe_bench.select(self.dataset, "pinned-revision", self.manifest)
        self.assertEqual(len(ids), 5)
        spec, selected = swe_bench.selected_rows(self.dataset, self.manifest)
        self.assertEqual(spec["revision"], "pinned-revision")
        self.assertEqual({row["repo"] for row in selected},
                         {row["repo"] for row in self.rows})
        self.dataset.write_text(self.dataset.read_text(encoding="utf-8") + "\n",
                                encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            swe_bench.selected_rows(self.dataset, self.manifest)

    def test_explicit_manifest_can_add_another_case(self) -> None:
        extra = dict(self.rows[0], instance_id="example__project0-2")
        self.dataset.write_text(self.dataset.read_text(encoding="utf-8") +
                                json.dumps(extra) + "\n", encoding="utf-8")
        ids = [row["instance_id"] for row in self.rows] + [extra["instance_id"]]
        swe_bench.select(self.dataset, "pinned-revision", self.manifest,
                         count=6, ids=ids)
        _, selected = swe_bench.selected_rows(self.dataset, self.manifest)
        self.assertEqual([row["instance_id"] for row in selected], ids)

    def test_fetch_saves_dataset_and_revision_without_dependencies(self) -> None:
        sha = "a" * 40
        page = {"num_rows_total": 5, "partial": False,
                "rows": [{"row_idx": index, "truncated_cells": [], "row": row}
                         for index, row in enumerate(self.rows)]}
        target = self.root / "download" / "lite.jsonl"
        with patch.object(swe_bench, "_fetch_json",
                          side_effect=[{"sha": sha}, page, {"sha": sha}]):
            self.assertEqual(swe_bench.fetch(target), (sha, 5))
        self.assertEqual(len(swe_bench.load_rows(target)), 5)
        metadata = json.loads(target.with_suffix(".meta.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["revision"], sha)

    def test_run_exports_five_patches_without_reference_data(self) -> None:
        swe_bench.select(self.dataset, "pinned-revision", self.manifest)
        script = "from pathlib import Path; Path('answer.py').write_text('value = 1\\n')"
        with patch.object(swe_bench, "build_codex_command",
                          return_value=(sys.executable, "-c", script)):
            status = swe_bench.run(self.dataset, self.manifest, self.root, "pilot-001",
                                   "lm-studio", "local-test-model", 30, self.cache, False)
        self.assertEqual(status, 0)
        run_dir = self.root / "run-logs" / "swe-bench-lite" / "pilot-001"
        predictions = [json.loads(line) for line in
                       (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(predictions), 5)
        self.assertTrue(all("diff --git a/answer.py b/answer.py" in item["model_patch"]
                            for item in predictions))
        self.assertTrue(all(item["model_name_or_path"] == "local-test-model"
                            for item in predictions))
        for row in self.rows:
            prompt = (run_dir / row["instance_id"] / "prompt.txt").read_text(encoding="utf-8")
            self.assertIn(row["problem_statement"], prompt)
            self.assertNotIn("SECRET_REFERENCE_PATCH", prompt)
            self.assertNotIn("SECRET_HIDDEN_TEST", prompt)
        self.assertTrue(all(item["status"] == "ready" for item in
                            json.loads((run_dir / "results.json").read_text(encoding="utf-8"))))

    def test_windows_sandbox_cache_is_not_a_model_patch(self) -> None:
        row = self.rows[0]
        script = ("from pathlib import Path; "
                  "p = Path('%SystemDrive%/ProgramData/Microsoft/Windows/Caches'); "
                  "p.mkdir(parents=True, exist_ok=True); "
                  "(p / 'cache.db').write_bytes(b'cache')")
        with patch.object(swe_bench, "build_codex_command",
                          return_value=(sys.executable, "-c", script)):
            result = swe_bench.run_instance(row, self.cache, self.root,
                                            "lm-studio", "local-test-model", 30, False)
        stderr = (self.root / row["instance_id"] / "stderr.txt").read_text(encoding="utf-8")
        self.assertEqual(result["status"], "empty_patch", stderr)
        self.assertEqual(result["model_patch"], "")

    def test_grade_only_selected_ids_with_one_worker(self) -> None:
        swe_bench.select(self.dataset, "pinned-revision", self.manifest)
        run_dir = self.root / "run-logs" / "swe-bench-lite" / "pilot-001"
        run_dir.mkdir(parents=True)
        (run_dir / "predictions.jsonl").write_text("{}\n", encoding="utf-8")
        (run_dir / "run.json").write_text(json.dumps({
            "instance_ids": [row["instance_id"] for row in self.rows]}), encoding="utf-8")
        with patch.object(swe_bench.subprocess, "run") as runner:
            runner.return_value.returncode = 0
            self.assertEqual(swe_bench.grade(self.root, "pilot-001", "swebench"), 0)
        command = runner.call_args.args[0]
        self.assertEqual(command[:4], ("swebench", "eval", "lite", "-p"))
        self.assertEqual(command[command.index("-j") + 1], "1")
        self.assertEqual(command.count("-i"), 5)


if __name__ == "__main__":
    unittest.main()
