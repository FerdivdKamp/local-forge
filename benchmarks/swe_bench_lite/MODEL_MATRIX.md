# Local LM Studio model matrix (draft, 2026-10-17)

This is a planning snapshot for the [five pinned Python cases](five.json), not
a benchmark result or an implemented model loader. Nothing here loads or
unloads a model. Re-inventory and re-estimate before a real run.

## VRAM policy

The RTX 5070 Ti reports **16,303 MiB = 15.92 GiB** VRAM. At inventory time,
`qwen3.8-27b@q2_k_xl` was loaded at an 80,128-token context, leaving only
**2,801 MiB free**. The table below assumes a *single-model* GPU; it is not
permission to unload that model or add another large one beside it.

Reserve **2.00 GiB** for desktop/other GPU use and **1.50 GiB** for estimator
error, transient allocations, and extra KV growth. That leaves **12.42 GiB**
for a context-specific LM Studio GPU estimate. A prospective profile needs
another **0.50 GiB clearance** within that ceiling, so its estimate must be
**at most 11.92 GiB** to appear in `candidate_context_lengths`. Estimates from
11.92 to 12.42 GiB have insufficient margin; estimates above 12.42 GiB are
over budget. The estimator already accounts for its assumed context/KV cost;
the 1.50 GiB is an *additional safety reserve*, not a second full KV charge.

All numbers below come from `lms load --estimate-only MODEL --context-length
CONTEXT --gpu max --yes`. They are **predicted GiB**, not measured peak VRAM.
The estimator does not establish actual KV location/quantization, flash
attention, or eventual CPU spill. Check live free VRAM and observed load
configuration before any run. A null estimate in JSON means model-context
limit or unresolved variant selection, not zero memory.

| Downloaded LLM (loadable key) | Weight quant | 8K | 16K | 32K | 64K | 128K | Candidate contexts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `qwen2.5-coder-1.5b-instruct` | Q8_0 | 1.78 | 1.97 | 2.35 | — | — | 8–32K |
| `deepseek/deepseek-r1-0528-qwen3-8b` | Q4_K_M selected | 5.60 | 6.36 | 7.89 | 10.94 | 17.04 | 8–64K |
| `prism-ml/bonsai-27b` | Q1_0 | 5.27 | 5.66 | 6.44 | 7.99 | 11.11 | 8–128K |
| `google/gemma-4-12b` | Q4_K_M | 8.50 | 9.74 | 12.23 | 17.20 | 27.15 | 8–16K |
| `qwen3.8-27b@iq2_xxs` | IQ2_XXS | 8.98 | 9.53 | 10.62 | 12.79 | 17.14 | 8–32K |
| `qwen3.6-14b-a3b-vibeforged-v2` | Q4_K_M | 9.25 | 9.52 | 10.05 | 11.11 | 13.23 | 8–64K |
| `qwen3.8-27b-gsq-rco` | IQ2_S | 11.13 | 11.76 | 13.03 | 15.56 | 20.62 | 8–16K |
| `unsloth/qwen3-coder-30b-a3b-instruct` | Q2_K_XL | 11.73 | 12.14 | 12.97 | 14.61 | 17.90 | 8K only |
| `qwen3.8-27b@q2_k_xl` | Q2_K_XL | 11.74 | 12.39 | 13.71 | 16.34 | 21.61 | 8K only |
| `qwen/qwen3-coder-30b` | Q3_K_L | 14.41 | 14.82 | 15.65 | 17.29 | 20.58 | none at full GPU offload |
| DeepSeek R1 Qwen3 8B Q8_0 variant | Q8_0 | ? | ? | ? | ? | ? | unresolved variant |

A dash means above the model's advertised context limit. A question mark means
the local CLI could not select the variant unambiguously. Numeric estimates
may still be disallowed by the VRAM policy. The 1.5B and DeepSeek Q4 models
do not advertise tool-use training in the local inventory; a memory fit is not
a capability claim. Bonsai's Q1_0 weights are unusually low precision.

There are ten downloaded LLM groups, eleven weight variants, and one embedding
model, which is excluded. The DeepSeek group key selects Q4_K_M. Although
`lms ls --llm --variants --json` lists a Q8_0 variant, this installation's
estimate-only CLI rejected both its variant key and indexed identifier. Do not
mistake the Q4 group-key estimate for Q8. Several single-variant suffixed keys
were also rejected; the table uses their loadable group keys.

## Using the JSON draft

[model_matrix.json](model_matrix.json) is **not yet consumed by the runner**.
It lists model weight quantization and advertised maximum context, then maps
8K, 16K, 32K, 64K, and 128K to predicted VRAM. Context length is a profile
dimension: combine a model's `id_prefix` with each value in
`candidate_context_lengths` to form one prospective profile. The five-case
manifest, GPU offload, parallelism, timeout, and reasoning setting remain fixed.
Do not expand null, over-budget, or insufficient-margin contexts.

For example, the currently loaded Q2_K_XL model's 16K estimate is **12.39
GiB**, only **0.03 GiB** under the 12.42 GiB ceiling; it fails the 0.50 GiB
clearance rule. Its current 80,128-token load is a different configuration and
does not validate an 8K or 16K estimate. Keep KV location/quantization and
flash attention as unknown until confirmed by the installed LM Studio
interface. Never unload a pre-existing model without user approval. Re-run
estimate-only preflight, inspect actual load configuration and VRAM use, and
record any CPU spill. Run the [gold harness smoke test](WINDOWS_WSL_GRADING.md)
before interpreting five-case scores.

LM Studio [documents the CLI estimator](https://lmstudio.ai/docs/cli/local-models/load)
and its [load API](https://lmstudio.ai/docs/developer/rest/load) exposes
`flash_attention`, `offload_kv_cache_to_gpu`, and `echo_load_config`. The
documented API does not expose a KV-quantization field; check the installed
version before requiring one.
