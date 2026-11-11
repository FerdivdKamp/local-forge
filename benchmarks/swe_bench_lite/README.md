# SWE-bench Lite five-instance pilot

The `localforge.swe_bench` command can fetch Lite metadata, select and run up to
ten pinned Python tasks, export their patches, and invoke the official evaluator.
It does not install SWE-bench/Docker. Keep this separate from the synthetic
suites under [`eval_cases/`](../../eval_cases/README.md).

The [local LM Studio model/VRAM matrix](MODEL_MATRIX.md) inventories downloaded
models and proposes bounded 8K–128K model/context profiles. Its [JSON draft](model_matrix.json)
is not yet accepted by the runner; see the [implementation prompt](NEXT_STEP_MODEL_MATRIX_PROMPT.md).

SWE-bench Lite has 300 test instances drawn from Python repositories. It does
**not** include Blender or Godot tasks. A 5–10 instance pilot is useful for
finding integration and model failures, but its pass rate is not a comparable
SWE-bench Lite leaderboard score. Do not label it as one.

## Five cases pinned now

[`five.json`](five.json) pins these cases from the official Lite `test` split:

| Instance ID | Repository | Issue summary |
| --- | --- | --- |
| `pytest-dev__pytest-9359` | pytest | Assertion error includes an extra source line on Python 3.9. |
| `matplotlib__matplotlib-25433` | matplotlib | Range-slider callback with `clf`/`draw` blocks widget input. |
| `sympy__sympy-21627` | SymPy | `is_zero` on a `cosh` expression reaches recursion depth. |
| `django__django-15202` | Django | `URLField.clean` raises `ValueError` instead of `ValidationError`. |
| `pylint-dev__pylint-7114` | Pylint | Linting fails with a namesake nested module. |

Selection was deterministic: SHA-256 ordering of IDs, taking the first five
distinct repositories. No model outcomes influenced selection. The observed
Hugging Face dataset commit is `b0dde1093fe417d83b7184254edf8199c1f0dff5`.
The manifest also pins the SHA-256 of the **local JSONL snapshot**. The viewer
API does not accept a revision parameter, so the repository SHA was observed
before and after downloading, but is not a guarantee the viewer served that
exact commit. Preserve the JSONL file for byte-for-byte reproducibility.

## Run the pinned sample

The 300-row Lite `test` metadata snapshot is already at
`.benchmark-data/lite-test.jsonl` on this machine; `.benchmark-data/` is ignored
by Git. From the repository root:

```powershell
poetry run python -m localforge.swe_bench run --dataset .benchmark-data/lite-test.jsonl --manifest benchmarks/swe_bench_lite/five.json --run-id pilot-001 --mode lm-studio --model qwen3.8-27b@q2_k_xl --timeout 600 --allow-clone
```

If the snapshot is missing, fetch it again with no extra Python dependency,
then generate a **new** manifest using the printed revision. Do not overwrite
an existing snapshot or manifest: a new dataset file may have a different hash.
The fetch command uses Hugging Face's [dataset viewer `/rows` API](https://huggingface.co/docs/dataset-viewer/en/rows).

```powershell
poetry run python -m localforge.swe_bench fetch --dataset .benchmark-data/lite-test.jsonl
poetry run python -m localforge.swe_bench select --dataset .benchmark-data/lite-test.jsonl --revision DATASET_COMMIT_SHA --manifest benchmarks/swe_bench_lite/five-new.json
```

### Add or replace cases

Find candidate `instance_id` values in the downloaded JSONL. Create a **new**
manifest with repeated `--instance` flags and a matching `--count` (1–10). To
expand this sample, list its five IDs plus each new ID. For example, the next
distinct-repository ID under the same selection rule is
`scikit-learn__scikit-learn-25747`:

```powershell
poetry run python -m localforge.swe_bench select --dataset .benchmark-data/lite-test.jsonl --revision b0dde1093fe417d83b7184254edf8199c1f0dff5 --manifest benchmarks/swe_bench_lite/six.json --count 6 --instance pytest-dev__pytest-9359 --instance matplotlib__matplotlib-25433 --instance sympy__sympy-21627 --instance django__django-15202 --instance pylint-dev__pylint-7114 --instance scikit-learn__scikit-learn-25747
```

Pass the new manifest to `run` with a new run ID. This real-repository suite is
defined by the manifest, not by adding fixture directories. `select --count 10`
without explicit IDs takes ten distinct repositories by the same deterministic
rule, if available. Keep `five.json` unchanged after recording results, and
report the denominator for each manifest separately.

`--allow-clone` permits Git to fetch only the selected repositories from GitHub
into `WORKSPACE_ROOT/swe-bench-repos`. Omit it when that cache is already
populated. This is Git source retrieval, not a GitHub issue/PR operation. Each
run uses a new `--run-id`; an existing run directory is never overwritten.
Inference is sequential, with Codex web search disabled and no approval prompts.
The run writes prompts, traces, diffs, per-instance outcomes, and
`predictions.jsonl` under `WORKSPACE_ROOT/run-logs/swe-bench-lite/<run-id>/`.
An unsuccessful agent or empty patch still gets a prediction record with an
empty patch and a separate local failure status. No model run is performed by
`select`.

For this Windows setup, grade from Ubuntu/WSL 2 using the exact commands in
[Windows + WSL grading](WINDOWS_WSL_GRADING.md). Docker Desktop supplies the
Linux container engine; no dual boot is involved. The `grade` subcommand runs
the official CLI in the **same OS** as LocalForge, so running it from Windows
does not move grading into Linux. Use the Ubuntu commands until a cross-OS
handoff is implemented.

The official harness writes its `results.json` and per-instance `report.json`
under the Ubuntu working directory's `logs/evaluation/<harness-id>/`.
Read those reports alongside LocalForge's `results.json`; the latter records
agent/export status, **not** the official resolved verdict. `grade` does not
currently import harness verdicts into LocalForge's database. Re-running grade
uses a fresh harness ID so changed predictions cannot silently reuse a cached
verdict. See the [official CLI reference](https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/cli.md).

## Remaining integration work

1. **Acquire and pin the dataset.** Use the official
   [`SWE-bench_Lite`](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite)
   dataset. Record its revision, split, selected instance IDs, and selection
   criteria in a checked-in manifest. Keep dataset data in an ignored local
   folder or an external cache, and repository sources outside the Git worktree;
   do not commit source checkouts, Docker
   images, issue text, or generated patches. Use a separate environment for the
   SWE-bench package if its dependencies conflict with LocalForge's minimal
   `pyproject.toml`.
2. **Prepare one isolated task workspace per attempt.** Checkout the exact
   repository and `base_commit` from the instance, with a clean tree. Make the
   task prompt from the issue description and normal repository instructions.
   Do not expose the reference patch (`patch`), hidden test patch (`test_patch`),
   or expected result to the agent. The agent must not have LocalForge's GitHub
   credentials, push a branch, or create a PR during a benchmark run.
3. **Adapt the existing runner.** The first adapter reuses Codex/LM Studio
   command construction, timeout handling, trace capture, and run metadata with
   a benchmark-specific workspace provider. It is sequential and records setup,
   agent, timeout, and empty-patch failures. Patch-application and graded
   failures remain in the official harness reports.
   Do not treat a visible test pass or a successful Codex exit as resolution.
4. **Export predictions.** Capture `git diff` against the pristine base commit
   before cleanup. Write one JSONL record per attempt with `instance_id`,
   `model_name_or_path`, and `model_patch`, as required by the
   [official evaluation guide](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/evaluation.md).
   Preserve the full diff and Codex trace locally for diagnosis; never include
   harness-only tests in the prediction. Use one model/settings combination per
   predictions file, with a unique attempt ID for retries.
5. **Grade with the official harness.** Run SWE-bench's Docker-based evaluator
   on the exported predictions, not LocalForge's current fixture verifiers.
   On Windows, this requires Docker Desktop with WSL 2 and enough disk/RAM for
   repository images; check resources before downloading or building them.
   Start with one worker and a gold-patch smoke test. Use a new `run_id` if a
   prediction changes because the harness can reuse cached results by run ID.
   Keep generated Docker/log/cache data outside this repository.
6. **Join the results (next step).** Import the harness verdict and error category back to
   the corresponding LocalForge attempt. Report resolved/graded counts,
   infrastructure failures, duration, and tokens *when reported*. Record model
   ID, weight quantization, context length, KV-cache quantization, LM Studio
   version, Codex version, prompt revision, timeout, web-access setting, dataset
   revision, and harness revision. Unknown settings must remain unknown, not
   default silently. Add unit tests for dataset mapping, prompt leakage
   prevention, diff export, JSONL validation, and verdict parsing; use a tiny
   fake repository and fake harness so normal unit tests need no Docker/network.

The reference [quick start](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/quickstart.md)
shows a one-instance gold smoke test to validate Docker before grading. Use a
case from this manifest:

```bash
# Run in Ubuntu/WSL with SWE-bench installed and Docker Desktop running.
swebench eval lite --gold -i pytest-dev__pytest-9359 --run-id pilot-gold -j 1
```

Check `swebench eval lite --help` against the installed harness version. Do not
build all images just to start the pilot. On this machine, `docker` and
`swebench` were not on `PATH` when the dataset was pinned, so this gold check
has **not** run. Install/configure Docker Desktop with WSL 2 and the official
SWE-bench CLI first. Prefer running the harness inside WSL/Linux: a reported
[Windows line-ending issue](https://github.com/SWE-bench/SWE-bench/issues/652)
can make even gold patches grade unresolved on native Windows. Verify the gold
result before trusting any model score.

## Pilot: five, then up to ten Python instances

1. Select five Lite **test** instances before any model run. The selection
   command uses SHA-256 ordering of instance IDs and the first five distinct
   repositories. Record its exact IDs and dataset revision in the manifest.
   Do not pick or replace cases based on model success.
   The small `dev` split can be used for adapter debugging, but keep it out of
   the reported test pilot.
2. Run one gold-patch smoke test and one model attempt end to end. Confirm the
   checkout matches `base_commit`, the prediction applies, the harness reports
   a verdict, and the artifacts are linked to the same `instance_id`. Fix setup
   problems before spending model time on the other four.
3. Run the remaining four sequentially with the same model, prompt, context,
   timeout, and web-access settings. Record every attempt, including timeouts
   and setup failures. Do not rerun a failure without recording a new attempt.
4. If the pipeline works, preselect five more Lite test instances using the
   same rules. Run them under unchanged settings. If resources or infrastructure
   prevent this, stop at five and report that limitation.
5. Review each failed run's diff, Codex trace, and harness log. Separate model
   behavior from environment/patch-application errors. Report `resolved/N`
   with N explicitly stated (5 or 10), plus per-instance outcomes; avoid
   extrapolating to all 300 tasks. A later repeat run can measure variance.

## Separate secondary tracks

- **Godot:** The existing [`godot_v1`](../../eval_cases/README.md#godot-4-gdscript-cases)
  suite has three headless GDScript cases. Run and report it separately from
  SWE-bench Lite, using its own case IDs and denominator. It is not a SWE-bench
  result.
- **Blender:** No Blender evaluation cases or verifier exist in this repository
  yet. If Blender is available, add a separate small suite with a pinned
  Blender version, headless execution, deterministic fixtures, and hidden
  verifiers. Do not substitute Blender examples for Lite instances or combine
  their scores. This is optional after the Python pipeline works.

## Done for the first implementation

The initial adapter supports one to ten pinned instances, runs without
GitHub issue/PR side effects, emits valid predictions, and invokes the official
harness for per-instance verdicts. It preserves local artifacts. Importing
verdicts, fuller inference-setting capture, ten instances, and Blender/Godot
comparisons remain follow-ups.
