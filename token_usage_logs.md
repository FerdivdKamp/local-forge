Investigate Codex token telemetry for LocalForge
Goal
Add support in LocalForge for collecting and visualizing Codex token usage per task/agent/session.
Codex currently exposes useful token telemetry in its agent/task UI, but the information is fragmented and appears to be scoped to individual tasks rather than aggregated across a multi-agent run.
Findings
In the Codex agent command center, selecting a task shows usage such as:
Tokens: 92.3K in • 1.15K out

This appears to represent token usage for the selected Codex task/agent, not the total across all tasks in the agent command center.
Earlier Codex output showed more detail:
Token usage so far:
total=25,881
input=24,728
(+ 67,584 cached)
output=1,153
(reasoning 227)

The likely interpretation is:
input_tokens             = 92,312
cached_input_tokens      = 67,584
non_cached_input_tokens  = 24,728

output_tokens            = 1,153
reasoning_tokens         = 227

Important: cached input is a subset of total input, not additional to it.
So:
92,312 total input
├── 67,584 cached
└── 24,728 newly processed

1,153 output
└── 227 reasoning

Why this is useful for LocalForge
LocalForge could collect this telemetry and provide a view that Codex itself currently does not make especially convenient: aggregate usage across a root task and all of its subagents.
Potential hierarchy:
LocalForge run
└── Codex root session
    ├── main agent
    ├── subagent: task_01
    ├── subagent: task_02
    └── subagent: task_03

Store metrics per task/agent and aggregate upwards.
Example record:
{
  "repository": "garden_trauma",
  "task": "Clarify player hitbox setup",
  "model": "gpt-6-sol",
  "input_tokens": 92312,
  "cached_input_tokens": 67584,
  "output_tokens": 1153,
  "reasoning_tokens": 227
}

Useful derived metrics
LocalForge/Grafana could expose:
- total tokens per repository
- total tokens per LocalForge run
- tokens per Codex task
- tokens per subagent
- tokens per model
- tokens per day
- input vs output usage
- cached vs non-cached input
- cache hit ratio
- aggregate usage of a parent task plus all subagents
For example:
cache_hit_ratio =
cached_input_tokens / input_tokens

Data source to investigate
Codex appears to persist session/task data locally under:
~/.codex/sessions

On Windows this will normally correspond to something below:
%USERPROFILE%\.codex\sessions

Rather than scraping the terminal UI, LocalForge should investigate whether the session/event files contain structured token telemetry.
Proposed implementation
V1 — inspect and parse local Codex session data
- Inspect a few real files from .codex/sessions
- Determine:
  - file format
  - task/session identifiers
  - parent-child agent relationships
  - model name
  - token counters
  - timestamps
  - repository/project path
- Build a small parser that converts Codex records into LocalForge's internal telemetry model
V2 — persist telemetry
Store normalized records such as:
codex_session_id
codex_task_id
parent_task_id
repository
model
started_at
updated_at
input_tokens
cached_input_tokens
output_tokens
reasoning_tokens

Ensure repeated polling/updating does not double-count cumulative counters.
V3 — dashboard
Add Grafana panels for:
Tokens over time
Tokens by model
Tokens by repository
Tokens by agent
Cached vs non-cached input
Multi-agent run total

A useful multi-agent overview could look like:
Run: implement tower configuration system

main agent          42K input    3.1K output
task_01             18K input    1.2K output
task_02             31K input    2.0K output
task_03             12K input    0.8K output
------------------------------------------------
total               103K input   7.1K output

Caveats
The Codex counters should initially be treated as usage telemetry, not necessarily authoritative billing data.
The implementation should also verify whether values are:
- cumulative per session
- cumulative per task
- reported per turn
- duplicated between parent and child sessions
We should avoid summing values until those semantics are confirmed.
Acceptance criteria
- [ ] Inspect real Codex session files from .codex/sessions
- [ ] Document the relevant event/schema format
- [ ] Extract model and token usage
- [ ] Distinguish total input from cached input
- [ ] Extract output and reasoning token counts where available
- [ ] Identify task/session IDs
- [ ] Identify parent-child relationships for agents if available
- [ ] Associate a session/task with a repository where possible
- [ ] Normalize telemetry into LocalForge records
- [ ] Avoid double-counting cumulative counters
- [ ] Produce an aggregate total across a multi-agent run
- [ ] Expose the data for Grafana/dashboard use
Follow-up
Before designing the final database schema, inspect several actual Codex session files from different cases:
1. a normal single-agent conversation
2. a task that spawned multiple agents
3. a completed task
4. a stopped/interrupted task
That should tell us whether LocalForge can reliably reconstruct both the task hierarchy and its token usage.