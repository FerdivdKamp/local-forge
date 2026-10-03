# Side quest: find useful roles for local models in Codex

## Goal

Build a small, repeatable evaluation suite that answers a practical question: which coding tasks can a local model complete reliably through Codex, and which tasks should an online model plan, verify, or do itself? Keep the first version local and independent of the GitHub issue workflow. The result is a report card for each model and settings combination, stored in the existing `WORKSPACE_ROOT/localforge.sqlite3` database.

This is an evaluation plan, not a proposal to route real issues automatically yet. A successful Codex exit or a plausible final message is not enough evidence that the work is correct.

## Questions to answer

1. Can the local model read repository instructions, inspect the right files, create and edit files, run tests, and leave a focused diff?
2. Can it identify the right package API from installed code or documentation, and use web search when Codex actually provides that capability?
3. Can it implement a whole, well-scoped issue? Does an online model's decomposition into smaller tasks improve the finished result enough to justify the extra work?
4. Is it more useful as a reviewer: finding real defects, explaining them precisely, and avoiding false alarms?
5. Which model, inference settings, and task shape give the best quality for the elapsed time and available token budget?

## First suite: small tasks with objective outcomes

Start with 8-10 versioned cases in tiny fixture repositories. Each case has a starting commit, a task prompt, any repository rules, a hidden verifier, and a scoring rubric. Prefer Python cases because LocalForge is Python; add another language only after the runner works. Include both easy cases and realistic failure modes:

| Case | What it probes | Independent check |
| --- | --- | --- |
| Create a module and test | File creation, imports, tests, instructions | Hidden tests and expected paths |
| Edit an existing function | Finding the right code, minimal patch | Regression and edge-case tests |
| Change code plus README | Coordinated edits, scope control | Tests and documentation checklist |
| Diagnose a failing test | Investigation and repair | Previously failing test passes without breaking others |
| Use `ghapi` correctly | Inspect dependency and current API before coding | Pinned `ghapi` version, mocked calls and expected behavior |
| Documentation lookup | Search authoritative package docs when needed | Correct API usage, cited source and tool trace |
| Ambiguous request | Ask or state a bounded assumption | Rubric checks whether uncertainty was surfaced |
| Review a seeded diff | Defect detection and restraint | Known defects, severity, location, false positives |
| Whole issue vs subtasks | Planning, integration, task boundaries | Same end-to-end acceptance tests for both routes |

For the package case, pin the dependency version in the fixture, choose a version-sensitive function, and write the expected call against that version. Give the agent an opportunity to inspect the installed package. For the web case, supply a fresh question whose answer is in an authoritative source, record the URLs and access date, and verify that the answer and code agree with the source. Do not score a model as having searched the web just because it says it did: require a tool event or equivalent trace. Run a paired case with web access disabled to measure whether access changes the answer. If the Codex/local-provider setup has no web tool or network access, record `unavailable` for that capability rather than a model failure.

Keep hidden tests outside the agent worktree. Include at least one case where visible tests pass but hidden edge cases fail, so the suite measures more than willingness to run tests. Never use a live GitHub issue or production repository as an initial fixture.

## Paths to compare

Run the same whole-issue cases through three routes, with the same starting commit and acceptance criteria:

1. **Direct implementation:** give the local model the complete issue through Codex.
2. **Planned implementation:** an online model converts the issue into small, ordered tasks with acceptance criteria. Give each task to the local model in a fresh or sequential worktree as appropriate. The online model checks each diff and test result, requests a bounded repair if needed, and checks the integrated result before human review.
3. **Review role:** an implementation is supplied; the local model reviews the diff without editing files. Compare its findings with seeded defects and an online or human reference review. Also test whether it can say that a clean diff is clean.

Do not let the planner write the solution into the subtask prompt. Save the plan and prompt text so a gain can be attributed to task splitting rather than leaked implementation. The online evaluator should see the task, diff, test results, and rubric; blind it to model identity where practical. Human review remains the final check for any proposed real-world change.

## Minimal runner

- Add a separate command such as `poetry run python -m localforge.eval run --suite v1 --model ...`. It should reuse Codex command construction, environment sanitization, event parsing, and SQLite location where sensible, but must not call `main --apply`, change issue labels, push branches, or create PRs. Check `pyproject.toml` before introducing any dependency; the first version can use `unittest`, `sqlite3`, `subprocess`, and Git.
- Copy each fixture to a disposable worktree or directory, capture its starting commit, run Codex with a fixed prompt template and a timeout, then collect exit code, final response, event trace, changed files, diff, test results, duration, and tokens when reported. Run hidden verification from the harness after Codex stops. Put time and iteration limits on each attempt.
- Separate evaluator checks from agent actions. Record whether the model ran tests, but score correctness using tests run by the harness. A test command seen in Codex's event stream is evidence of behavior, not proof that the change passes verification.
- Keep full prompts, diffs, and traces in local artifacts under `WORKSPACE_ROOT/run-logs/eval/`. Store paths and concise scores in SQLite. Scrub credentials from the Codex environment and logs; do not give the agent access to hidden tests or the answer key.
- Run each route at least three times per case, since model behavior varies. Record the seed if supported; otherwise mark it unknown. Fix case versions, timeout, prompt template, tool availability, and inference settings for comparisons. Preserve failures and timeouts instead of silently retrying them.

## Report card in the existing SQLite database

Add separate `eval_*` tables rather than mixing synthetic cases with the existing `runs` table for GitHub issues. A compact first schema is:

| Table | Main fields |
| --- | --- |
| `eval_cases` | case ID, suite version, category, fixture revision, rubric version, required capabilities |
| `eval_attempts` | ID, case ID, route (`direct`, `planned`, `review`), model ID, provider, Codex version, prompt version, settings JSON, seed, tool availability JSON, start/finish time, status, exit code, duration, token counts or NULL, artifact paths |
| `eval_scores` | attempt ID, verifier pass/fail, rubric scores JSON, reviewer ID or `deterministic`, notes, adjudication status |

Keep model identity and settings together for comparisons: model name and revision or quantization, LM Studio/provider version, temperature, context length, reasoning or effort setting if available, and any Codex tool or sandbox settings. Record `unknown` where a value cannot be obtained. Never treat missing token usage as zero. A suite or fixture revision change creates a new comparison group; old attempts remain queryable.

Generate a CLI report grouped by suite, case, route, model, and settings. Show pass rate with numerator and denominator, repeated-run spread, median time, median reported tokens, tool-use success, review precision/recall for seeded defects, and links to local artifacts. Include a compact per-case failure reason. Avoid a single opaque overall score; if a ranking is needed, require correctness first, then compare time and token use among similarly correct runs.

## Decision rules after the pilot

Define provisional gates before seeing results, then revise them with human review. For example:

- Allow **direct local implementation** for a task category only when end-to-end verification passes on at least 80% of repeated attempts, there are no serious instruction or scope violations, and human spot checks agree with the verifier.
- Prefer **online planning plus local implementation** when it materially raises verified success on the same issues and the added review time remains acceptable. The online model must inspect the integrated diff and tests before a human sees it.
- Use the local model as a **review assistant** only if it finds seeded high-impact defects consistently and its false positives are low enough to save reviewer time. Never treat an empty review as approval by itself.
- Keep categories that miss these gates with the online model or a human. A low-cost model that frequently needs repair may be slower overall; compare total attempts and review effort, not just inference time.

These thresholds are starting hypotheses, not a claim that the model is ready. Report results by task type so a strong file-editing result does not hide weak API research or review performance.

## Build order and completion criteria

### V1 Python pilot checklist

- [x] Add disposable Python fixtures for file creation, bug repair, and seeded review.
- [x] Keep implementation verifiers and the review answer key outside agent workspaces.
- [x] Record Codex duration, exit status, reported tokens, trace, response, diff, and verifier result per attempt.
- [x] Store attempts in separate `eval_*` SQLite tables and provide a per-case CLI report.
- [ ] Run each case at least three times for two real model/settings combinations and adjudicate the review case.

### V2 expansion checklist

- [x] Add a pinned `ghapi` v2 documentation lookup case with exact mocked GET parameters and web-tool trace observation.
- [ ] Add broader authoritative documentation lookup cases and explicit web capability detection.
- [ ] Compare direct whole-issue work with online planned subtasks using the same end-to-end verifier.
- [ ] Add blinded review adjudication and report review precision and recall.
- [ ] Use the repeated results and human spot checks to set guarded routing rules.

1. Implement fixture format, disposable runner, and deterministic verifier for file creation/editing and a seeded review case.
2. Add SQLite persistence and a small report command; confirm that failed and timed-out attempts produce complete records.
3. Add version-pinned package/API and web-lookup cases, with explicit capability detection.
4. Add the paired whole-issue/direct/planned experiment and blinded online adjudication.
5. Review the report card with a human, select task categories for a guarded LocalForge pilot, and keep the issue-publishing workflow separate until those categories earn trust.

The side quest is complete when another person can run a named suite against two model/settings combinations, reproduce the per-case artifacts, and read a report card that supports a concrete routing decision. No benchmark result alone authorizes automatic merging or removal of human review.
