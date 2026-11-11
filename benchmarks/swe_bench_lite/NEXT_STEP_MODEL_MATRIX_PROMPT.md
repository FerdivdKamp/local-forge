# Next implementation prompt: LM Studio model/settings matrix

Implement a small, opt-in model manager and settings matrix for
`localforge.swe_bench`. This is the **next task**, not functionality already
present in the pilot runner. Read the project README and AGENTS.MD first.

Context: `benchmarks/swe_bench_lite/five.json` pins five Python tasks. The
runner currently accepts one `--model` per run, assumes it is already loaded
in LM Studio, uses one hard-coded Codex reasoning/web setting, and does not
record the actual LM Studio load configuration. `lms ls` currently reports ten
downloaded LLM entries plus one embedding model; `qwen3.8-27b@q2_k_xl` is
loaded. Rediscover models at runtime; this snapshot may change.

An initial [inventory and VRAM plan](MODEL_MATRIX.md) plus a bounded
[`model_matrix.json`](model_matrix.json) draft now exist. Reuse and validate
them rather than starting a new matrix from scratch. The draft is **not yet
consumed by the runner** and its estimates are not measured peak VRAM.

Requirements:

1. Validate the versioned JSON matrix and expand its **model × context**
   candidates into a bounded list of runnable profiles. Context length is an
   explicit profile dimension: the draft includes 8K, 16K, 32K, 64K, and 128K
   estimates, but only `candidate_context_lengths` should expand by default.
   Null means unsupported model context or unresolved variant; a numeric
   estimate alone does not make a profile runnable. Each expanded profile names
   an exact downloaded LLM model key/weight quantization, a stable API
   identifier, requested context length, GPU offload, flash
   attention, KV-cache location/quantization *where supported*, inference
   parameters *where supported*, Codex reasoning effort, timeout, and the
   manifest to run. Allow multiple profiles for the same model to compare
   settings. Never infer weight or KV quantization from a display name alone;
   record unknown when LM Studio does not expose them. Reject unsupported
   settings explicitly instead of silently ignoring them. Do not add a YAML
   dependency just for this; check `pyproject.toml` before adding dependencies.
2. Discover installed versus loaded models (`lms ls`/`lms ps` or LM Studio's
   local API). Refuse non-downloaded models and embedding-only models. Never
   download models automatically. Verify the local server is reachable before
   starting a run. Use LM Studio's current supported load interface, such as
   `lms load` or `POST /api/v1/models/load`, and use `echo_load_config`/model
   inspection to record the **actual** settings. Check the installed version's
   capabilities rather than assuming every load knob, especially KV-cache
   quantization, has an API field.
3. Run one profile at a time across the **same pinned five** instances. Use a
   unique run ID per profile and attempt; save model ID, model file/quant,
   requested settings, observed load settings, LM Studio/Codex versions,
   dataset and manifest hashes, start/end times, per-case outcomes, token counts
   when reported, and the official harness verdict separately from agent exit
   status. Give profiles the same timeout and prompt unless the matrix
   deliberately varies them. Keep a clear 5-case denominator.
4. Resource safety: estimate or preflight memory when available, avoid loading
   several large models together, and stop cleanly on out-of-memory or load
   failure. Do not unload an already-running user model by default. Only unload
   instances this tool loaded, and only when an explicit management flag is
   enabled; preserve or restore the initial loaded-model state. No GitHub
   issue/branch/PR side effects. Keep benchmark data and traces local. Treat
   the LM Studio context-specific GPU estimate as already including its assumed
   KV/context cost; add a separate *uncertainty/growth* reserve, not a duplicate
   full KV allocation. On this 15.92 GiB GPU, plan for 2 GiB desktop/other GPU
   use and 1.5 GiB extra KV/runtime growth (so any full-offload context estimate
   must stay at or below 12.42 GiB). The draft requires a further 0.50 GiB
   clearance, making 11.92 GiB its candidate cutoff. Recheck **live free VRAM** and re-estimate before
   loading; the current loaded model leaves only about 2.74 GiB free. Never
   treat an estimated fit as permission to unload it, silently spill to CPU, or
   claim a controlled KV quantization. Record actual placement and peak VRAM.
5. Provide `--dry-run` to print the exact matrix expansion and intended model
   lifecycle without loading anything. Make runs resumable without overwriting
   completed artifacts or reusing a harness cache ID for changed predictions.
   Bound profile count and require an explicit confirmation flag before
   starting all profiles. Add tests with fake LM Studio responses/processes;
   unit tests must not load models, download data, call GitHub, or start Docker.
6. Update the benchmark README with a small example matrix, commands for one
   profile and for the full matrix, and a comparison report that distinguishes
   resolved/graded/infra errors and reports runtime/tokens as unknown when
   unavailable. Do not claim a five-case result is an official Lite score.

Keep the implementation focused: a small profile loader, a model lifecycle
adapter, and orchestration around the existing SWE-bench runner. Before
running real models, first verify Docker and the official SWE-bench gold
smoke test on one of the five selected IDs. On Windows, prefer a WSL/Linux
harness and confirm the gold patch resolves before trusting model scores.

Relevant current LM Studio references:
[CLI](https://lmstudio.ai/docs/cli),
[load model API](https://lmstudio.ai/docs/developer/rest/load),
[list models API](https://lmstudio.ai/docs/developer/rest/list).
