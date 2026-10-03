# Local Python evaluation suite

Run from the LocalForge repository root after `poetry install`. Set
`WORKSPACE_ROOT` to a local directory for evaluation data, or configure
`workspace_root` in `config.ini`. The fallback is `../workspaces`.

```powershell
poetry run python -m localforge.eval run --suite v1 --mode lm-studio --model your/model --repeat 3 --timeout 600
poetry run python -m localforge.eval report
```

Use `--case create_module`, `--case fix_total`, `--case ghapi_web_get`, or
`--case review_discount` to run one case. `--mode codex` uses the standard Codex CLI. Each attempt starts
from a fresh fixture commit. The timeout applies to Codex; implementation
verification has a separate 30-second limit. A failing attempt makes the run
command exit with status 1, but its record is retained.

The runner writes to `WORKSPACE_ROOT/localforge.sqlite3` in separate `eval_*`
tables. Full prompts, Codex JSONL traces, responses, diffs, changed-file lists,
verification output, and metadata are kept under `WORKSPACE_ROOT/run-logs/eval/`.
The report prints verified pass counts, elapsed-time median and range, median
reported tokens, failure reasons, and artifact paths. Missing token usage is
shown as `unknown`. Compare results only for the same case revision, timeout,
model and inference settings. The CLI cannot discover LM Studio temperature,
context size, quantization or seed; record them separately before comparing
runs. `metadata.json` marks unknown values explicitly.

The `ghapi_web_get` case pins ghapi 2.1.4 and asks Codex to consult the
[official ghapi API reference](https://ghapi.fast.ai/fullapi.html) online. Its
hidden verifier checks an awaited `issues.get` call with exact `owner`, `repo`,
and `issue_number` arguments using a fake API, so it never calls GitHub. The
runner requests live Codex web search for this case and reports how many
attempts have a completed web-search tool event and cite the official ghapi
site in the final response. A final-message claim or URL alone does not count
as observed search. A correct implementation can pass
verification even if web search is unobserved; inspect that separate metric to
judge the web-search skill. To run a paired case with the Codex web tool
disabled, use `--web-access disabled`. Inference providers may not expose this
tool despite the live request; an unobserved trace alone cannot tell whether
the tool was unavailable or the model chose not to use it.

The review case has a human answer key at `v1/review_discount/answer_key.md`.
Read the saved response and diff, then judge defect detection and false positives
against that key. The report leaves these attempts at `needs_review` and does
not count them as verified success; record manual findings alongside the local
artifacts. Visible tests run by Codex are logged
as behavior, while independent verifier results determine implementation passes.
The verifiers are outside each disposable workspace. No live GitHub issue is
used, and the evaluation runner does not change issue labels or publish code.
