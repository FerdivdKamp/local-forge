# Evaluate local coding models

This document defines a repeatable way to evaluate the quality, reliability,
speed, and tool usage of local models used through Codex and LM Studio.

The purpose is to choose a model and configuration using evidence from the
same kind of GitHub issues that LocalForge will handle. An evaluation run must
not push branches, create pull requests, change issue labels, or use a real
GitHub token.

## Canonical evaluation system

The implemented evaluation system already lives in this repository. Use it
instead of creating a separate `benchmarks/` directory or manually invoking
Codex in a fixture.

| Purpose | Canonical location |
| --- | --- |
| How to run a suite or report results | [`eval_cases/README.md`](eval_cases/README.md) |
| Case prompts, public fixtures, and case metadata | `eval_cases/<suite>/<case>/` |
| Independent hidden verifiers | `eval_verifiers/` |
| Runner, artifact capture, and SQLite persistence | `localforge/eval.py` |
| Runner tests | `tests/test_eval.py` |
| Evaluation design/background | `side-quest.md` |

`eval_cases/README.md` is the operational source of truth. This document
defines the evaluation policy, required metrics, gaps, and roadmap. Its short
quick-start command below intentionally mirrors the canonical guide; add or
change detailed operational instructions only in the canonical guide.

## Evaluation principles

- Evaluate a model against a fixed benchmark, not an ad-hoc issue selected at
  run time.
- Run every model with the same repository revision, task prompt, agent
  settings, and time limit.
- Keep a complete local record of each run, including failures and timeouts.
- Measure acceptance criteria with deterministic checks where possible.
- Record the exact model and serving configuration: model name/version,
  quantization, context window, temperature, GPU/CPU settings, and LM Studio
  version.
- Do not treat a successful process exit as a successful task. A run succeeds
  only when the task's verification checks pass.
- Keep benchmark repositories and fixtures free of credentials and external
  services so a run can be repeated offline.

## What to evaluate

Use small, representative tasks that mirror intended LocalForge issues. Each
task should have an unambiguous acceptance test and a known starting commit.

Suggested task groups:

| Group | Example task | Primary signal |
| --- | --- | --- |
| Small bug fix | Correct an edge case and add a regression test. | Tests pass; diff is focused. |
| Feature | Add a small endpoint or command. | Acceptance tests and documentation pass. |
| Refactor | Remove duplication without changing behaviour. | Existing suite stays green; scope is controlled. |
| Repository discovery | Make a change requiring use of project conventions. | Correct files and patterns are used. |
| Tool use | Run the appropriate targeted tests and inspect failures. | Useful commands, minimal retries, correct diagnosis. |
| Safety | Encounter an unavailable credential or ambiguous requirement. | Stops safely and explains the blocker. |

Start with 10--20 tasks. Include tasks that are easy, typical, and difficult;
do not select only tasks that are known to work with a preferred model.

## Implemented case format

Every case is already stored under `eval_cases/<suite>/<case>/`:

```text
eval_cases/
  v1/
    fix_total/
      case.json
      prompt.txt
      fixture/
  godot_v1/
    godot_health/
      case.json
      prompt.txt
      fixture/
eval_verifiers/
  fix_total.py
  godot_v1/godot_health.gd
```

`prompt.txt` contains the task supplied to Codex. `fixture/` is copied to a
fresh disposable workspace for each attempt and committed by the runner before
Codex starts. `case.json` supplies the category, evaluation route, fixture
revision, and rubric version. The corresponding verifier is deliberately kept
in `eval_verifiers/`, outside the agent workspace, so the agent cannot inspect
or edit it.

Avoid including the intended implementation in prompts or checks. The verifier
may inspect behaviour and required files, but it must not depend on an exact
diff unless the task specifically requires one.

## Standard run procedure

1. Start LM Studio and load the candidate model.
2. Run the named case through `localforge.eval`.
3. The runner copies and commits the fixture in a fresh workspace, invokes
   Codex, captures its JSONL trace, saves the final diff, and runs the hidden
   verifier after Codex exits.
4. The runner preserves all artifacts below `WORKSPACE_ROOT/run-logs/eval/`
   and records an attempt in `WORKSPACE_ROOT/localforge.sqlite3`.
5. Run the report command to compare attempts.

Run each model/configuration on every task at least three times. Local models
can be nondeterministic even at low temperature; use the median for latency and
the pass rate for correctness. Randomize task order to reduce the effect of
thermal throttling and background load.

### Run one case with an LM Studio model

Start LM Studio's local server and load the candidate model. From the
LocalForge repository root, run a specific existing case with:

```powershell
poetry run python -m localforge.eval run --suite v1 --case fix_total --mode lm-studio --model 'unsloth/qwen3-coder-30b-a3b-instruct' --repeat 1 --timeout 600
```

For the Godot suite, pass the Godot executable too:

```powershell
poetry run python -m localforge.eval run --suite godot_v1 --case godot_health --mode lm-studio --model 'unsloth/qwen3-coder-30b-a3b-instruct' --godot 'C:/Tools/Godot/Godot_v4.4-stable_win64_console.exe'
```

To run all cases in a suite three times and then view the comparison:

```powershell
poetry run python -m localforge.eval run --suite v1 --mode lm-studio --model 'unsloth/qwen3-coder-30b-a3b-instruct' --repeat 3 --timeout 600
poetry run python -m localforge.eval report
```

The runner is the only supported entry point: it creates the disposable
workspace, invokes Codex with the configured model, runs the hidden verifier,
and persists the artifacts and SQLite records. Use the same model identifier,
timeout, suite revision, and inference settings for comparable runs.

## Metrics to record

Record raw data first, then derive summaries from it.

### Identification and reproducibility

- run ID and timestamp
- benchmark task ID and fixture/base commit
- LocalForge commit and Codex CLI version
- model identifier, model file/version, quantization, context window
- LM Studio version and inference settings (temperature, top-p, seed if
  supported, maximum output tokens)
- host OS, CPU, GPU, RAM, and available VRAM

### Outcome quality

- verifier result: pass, fail, timeout, or infrastructure error
- acceptance-check output and exit code
- Codex exit code
- human review score (optional, use a published rubric)
- regression-test result
- changed-file count and lines added/deleted
- whether documentation or tests were added when the task requires them

### Efficiency and tool use

- total wall-clock duration and time to first tool call
- input, cached input, output, reasoning-output, and total tokens where
  available
- number and type of tool/command calls
- commands that failed, retries, and command exit codes
- tests attempted by the agent and whether it acted on a failed test
- peak RAM/VRAM and average generated tokens per second, when available

### Safety and behaviour

- attempted network access or credential access
- commands outside the workspace
- destructive commands and whether they were justified by the task
- scope violations: unrelated files, dependency additions, or configuration
  changes
- explicit blockers reported instead of unsafe guessing

## Result schema

The implemented store is SQLite, not a separate JSONL results file. The runner
writes one row per attempt to `WORKSPACE_ROOT/localforge.sqlite3` in
`eval_cases` and `eval_attempts`; it stores prompts, Codex JSONL traces, final
responses, diffs, changed-file lists, verifier output, and `metadata.json`
under `WORKSPACE_ROOT/run-logs/eval/<case>-<attempt-id>/`.

`eval_attempts` already records model, mode, timeout, suite/case and fixture
revisions, status, exit code, duration, reported token usage, verifier result,
detected agent test runs, web-search observations, failure reason, and the
artifact directory. Unknown provider values remain `NULL` or `unknown`; they
must never be reported as zero.

## Scoring and review

The main ranking should be task pass rate. Use the following secondary signals
to distinguish models with similar pass rates:

- median time for passing runs;
- median token count and command count for passing runs;
- rate of unsafe or out-of-scope behaviour;
- quality of the final explanation and recovery from failed tests;
- human-review score for a blinded sample of successful diffs.

Do not aggregate all metrics into one score until the team has decided how to
trade correctness, cost, and speed. A faster model that fails acceptance tests
is not the better coding model.

## TODO

### Establish the benchmark

- [x] Define initial Python and Godot suites, with task categories.
- [x] Create disposable fixture workspaces.
- [x] Record a fixture revision in each `case.json`.
- [x] Write independent deterministic verifiers.
- [ ] Add a deliberately blocked/safety task.
- [ ] Review prompts and verifiers to remove solution leakage.
- [ ] Define a human-review rubric for correctness, scope, tests, and clarity.
- [ ] Expand the suite toward 10--20 representative cases before making a
      model-selection decision.

### Improve the existing evaluation harness

- [x] Provide the local-only `localforge.eval` runner and report command.
- [x] Create/reset a fresh fixture workspace for each attempt.
- [x] Keep evaluation runs independent of GitHub labels, branches, and PRs.
- [x] Capture Codex JSONL, response, stderr, diff, changed files, verifier
      output, SQLite records, and artifact paths.
- [x] Persist timeouts and basic failure reasons; test runner behaviour.
- [ ] Capture actual Codex CLI version and host hardware in `metadata.json`.
- [ ] Accept and persist declared LM Studio settings: model file/revision,
      quantization, context window, temperature, top-p, seed, and GPU settings.
- [ ] Derive command/tool-call counts, failed commands, retries, and time to
      first tool call from the Codex event stream.
- [ ] Classify infrastructure, Codex, verifier, timeout, and model failures
      distinctly.
- [ ] Add an export command if JSONL/CSV is needed for external analysis.

### Establish a baseline and compare models

- [ ] Choose one candidate model/configuration as the baseline.
- [ ] Run the full benchmark three times per task.
- [ ] Investigate and annotate every verifier failure before changing prompts or
      settings.
- [ ] Repeat with alternative quantizations and context windows before changing
      the model family.
- [ ] Compare candidates using the same hardware and benchmark revision.
- [ ] Publish a local evaluation report with raw-result paths and conclusions.

## Next step

Run the existing `v1` suite three times with one declared LM Studio
configuration, then run the report command. Before comparing it to another
model, record the missing LM Studio provenance beside the run: quantization,
context window, temperature, top-p, seed, LM Studio version, and host hardware.
The first implementation task should then be a `--settings` or metadata-file
option to persist those values with each attempt; this turns the current report
into a defensible model/configuration comparison.
