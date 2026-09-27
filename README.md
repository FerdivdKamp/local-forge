# LocalForge

LocalForge is a lightweight local agent orchestrator that turns GitHub issues into coding tasks for a local AI coding agent.

The first version is intentionally simple:

1. Poll GitHub for issues marked as ready for AI work.
2. Create a local workspace for the target repository.
3. Pass the issue to Codex.
4. Use a locally hosted model through LM Studio.
5. Capture the result.
6. Leave publishing changes back to GitHub as a later step.

The long-term goal is to use GitHub as the product-owner interface while local coding agents perform implementation work.

---

## Run LocalForge

Run commands from the LocalForge repository root. Install the project's Python
dependencies once:

```powershell
poetry install
```

Create a local `config.ini` from `config.example.ini` and configure at least the
GitHub token, owner, repository, labels, and workspace root. Keep `config.ini`
local; it contains credentials. For a workspace directory beside this repository:

```ini
workspace_root = ../workspaces
```

First use a dry run to list one eligible issue without changing GitHub or the
local filesystem:

```powershell
poetry run python -m localforge.main
```

To process the first `ai-ready` issue, move it to `ai-working`, and prepare its
local Git worktree, run:

```powershell
poetry run python -m localforge.main --apply
```

The worktree is created under `WORKSPACE_ROOT/issues/<issue-number>-<slug>` and
its branch is named `ai/<issue-number>-<slug>`. V1 currently stops after
preparing the workspace; Codex subprocess execution is the next implementation
step.

### Run unit tests

Run the full test suite with:

```powershell
poetry run python -m unittest discover -s tests -v
```

Run only the Codex prompt and command-construction tests with:

```powershell
poetry run python -m unittest tests.test_codex_runner -v
```

Stop the suite at its first failing test with `-f`:

```powershell
poetry run python -m unittest discover -s tests -v -f
```

`unittest` does not automatically open a debugger for an assertion failure. To
inspect one interactively, add a temporary `breakpoint()` at the relevant test
or code location, then rerun the test command. Python will open its built-in
debugger at that point.

---

## Architecture

```text
GitHub
  │
  │ poll issues
  ▼
LocalForge
  │
  ├── GitHub client
  ├── workspace manager
  ├── Codex runner
  └── logging
          │
          ▼
        Codex
          │
          ▼
      LM Studio
          │
          ▼
      Local LLM
```

GitHub contains the backlog and project state.

LocalForge owns the workflow.

Codex acts as the coding agent.

LM Studio provides local model inference.

---

## Initial workflow

A GitHub issue is created and labelled:

```text
ai-ready
```

LocalForge periodically checks for matching issues.

For each issue it:

```text
ai-ready
   │
   ▼
LocalForge detects issue
   │
   ▼
mark as ai-working
   │
   ▼
prepare local repository workspace
   │
   ▼
invoke Codex
   │
   ▼
Codex reads repository and AGENTS.md
   │
   ▼
Codex implements issue
   │
   ▼
Codex runs relevant tests
   │
   ▼
LocalForge records result
```

Initially, LocalForge will **not automatically push changes or create pull requests**.

This allows the local agent workflow to be tested safely before GitHub write operations are introduced.

---

# Design principles

## Local-first

Model inference should remain local through LM Studio.

External services such as GitHub may still receive repository, issue and pull-request data as expected.

## Least privilege

LocalForge owns infrastructure credentials such as the GitHub token.

Codex should not receive these secrets.

When starting Codex, LocalForge should provide a sanitized environment containing only the variables required by the coding process.

## Human review

Agents should not push directly to the main branch.

The eventual workflow will be:

```text
AI branch
   ↓
Pull Request
   ↓
CI
   ↓
Human review
   ↓
Merge
```

## Deterministic orchestration

The LLM performs coding work.

LocalForge controls the workflow.

For example, the LLM should not decide whether it should push to GitHub, change issue state, or merge a pull request.

---

# Technology

Initial implementation:

- Python
- GitHub REST API
- Git
- Codex CLI
- LM Studio
- Local coding model

Possible later additions:

- FastAPI
- SQLite or PostgreSQL
- Prometheus
- Grafana
- GitHub webhooks
- GitHub App authentication
- Docker
- Multiple concurrent agents

---

# Repository structure

Initial target structure:

```text
local-forge/
├── localforge/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── github_client.py
│   ├── workspace.py
│   └── codex_runner.py
│
├── tests/
│
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

The structure should remain small until additional complexity is actually needed.

---

# Configuration

Configuration should come from environment variables.

Example:

```text
GITHUB_TOKEN=...
GITHUB_OWNER=...
GITHUB_REPOSITORY=...
POLL_INTERVAL_SECONDS=30
WORKSPACE_ROOT=../workspaces
AI_READY_LABEL=ai-ready
AI_WORKING_LABEL=ai-working
CODEX_MODE=codex
CODEX_MODEL=unsloth/qwen3-coder-30b-a3b-instruct
```

Secrets must never be committed to the repository.

The GitHub token should initially be a fine-grained Personal Access Token scoped only to the repository used by LocalForge.

---

# Codex isolation

Codex should operate only inside the checked-out project workspace.

LocalForge should launch Codex with a sanitized environment.

For example, the Codex process should not inherit:

```text
GITHUB_TOKEN
database credentials
API keys
service credentials
LocalForge secrets
```

Codex should receive only the environment variables required to build and test the project.

## Codex model selection

`CODEX_MODE` controls the coding-agent command. Use `codex` for the standard
Codex CLI, or `lm-studio` for a local model through LM Studio. The latter builds:

```text
codex --oss -m unsloth/qwen3-coder-30b-a3b-instruct
```

Set `CODEX_MODEL` to select a different local model. LM Studio must be running
and configured before LocalForge starts that command. This setting applies only
to the coding agent; a future model that plans or splits GitHub issues should
have separate configuration.

---

# Issue format

Issues should contain enough information to act as a small development task.

Example:

```markdown
# Add health endpoint

Add a health endpoint to the service.

## Acceptance criteria

- `GET /health` returns HTTP 200
- response contains the application version
- relevant tests are added
- README is updated if required
```

The label:

```text
ai-ready
```

means that LocalForge may process the issue.

---

# Status labels

Planned initial labels:

```text
ai-ready
ai-working
ai-blocked
human-review
```

Meaning:

### `ai-ready`

The issue may be picked up by LocalForge.

### `ai-working`

A LocalForge run currently owns the issue.

### `ai-blocked`

The agent could not complete the task successfully or requires human input.

### `human-review`

Implementation has completed and is ready for human review.

---

# V1 decisions while developing

## GitHub PAT
### V1 requirements
*PAT Permissions*
Metadata       Read-only
Issues         Read and write
Contents       Read-only
Pull requests  Read-only 

### V1 actual permissions
*PAT Permissions*
Metadata       Read-only
Issues         Read and write
Contents       Read and write
Pull requests  Read and write
*basically because I don't want to tweak the settings too often for a hobby project (and years of GCP experience with poorly orchestrated permission schemes has wasted loads of time in that)*

## GitHub Api client

I've looked at https://docs.github.com/en/rest/using-the-rest-api/libraries-for-the-rest-api?apiVersion=2026-03-10#python

Chosen: ghapi  https://github.com/AnswerDotAI/ghapi

Reason: I'm familiar with FastAi project, like their documentation set up nd undertandable way of writing. Explicitly mentioning async, OpenAPI spec and the always up to date blurb sounds like I will not need to refactor the entire thing in three months time.



### 


# Roadmap

## V1 — Local prototype

Goal: prove that a GitHub issue can reliably trigger local coding work.

### TODO

- [x] Create Python project structure
- [x] Add configuration loader
- [x] Create GitHub PAT token
- [x] Read GitHub token from environment
- [x] Connect to GitHub API
- [x] Retrieve open issues
- [x] Filter issues using the `ai-ready` label
- [x] Prevent the same issue from being processed more than once
- [x] Add `ai-working` state
- [x] Clone or update target repository
- [x] Create isolated workspace per issue
- [x] Create branch such as `ai/123-short-description`
- [x] Build Codex prompt from issue title and description
- [ ] Start Codex as a subprocess
- [ ] Use LM Studio as the Codex model provider
- [ ] Sanitize environment passed to Codex
- [ ] Capture Codex stdout/stderr
- [ ] Capture Codex exit status
- [ ] Record execution duration
- [ ] Store basic run logs
- [ ] Handle failed Codex runs
- [ ] Mark failed issues as `ai-blocked`
- [ ] Add unit tests for orchestration logic
- [ ] Add `.env.example`
- [ ] Add `.gitignore`
- [ ] Document local setup

### V1 safety boundary

V1 should **not** automatically:

- push branches
- create pull requests
- merge code
- react to PR comments
- expose an HTTP API

The resulting workspace is reviewed manually.

---

## V2 — GitHub development workflow

Goal: make LocalForge behave like a developer receiving work from a product owner.

### TODO

- [ ] Push successful agent branches to GitHub
- [ ] Create pull requests automatically
- [ ] Link PRs to their originating issue
- [ ] Comment on issues with run results
- [ ] Add `human-review` label
- [ ] Remove `ai-working` after completion
- [ ] Record branch and PR identifiers
- [ ] Detect failed CI
- [ ] Allow retrying an issue
- [ ] Handle PR review comments
- [ ] Allow reviewer feedback to trigger another Codex run
- [ ] Update the existing PR branch
- [ ] Prevent duplicate PR creation
- [ ] Add structured JSON logging
- [ ] Persist run state in SQLite
- [ ] Track model used for each run
- [ ] Track token usage where available
- [ ] Track files changed
- [ ] Track tests executed and test result
- [ ] Add basic concurrency protection

Expected workflow:

```text
Product Owner creates issue
        ↓
label: ai-ready
        ↓
LocalForge
        ↓
Codex implements task
        ↓
Pull Request
        ↓
Human review
        ↓
review feedback
        ↓
LocalForge + Codex update PR
        ↓
Human merge
```

---

## V3 — Agent platform

Goal: evolve LocalForge from a polling script into a small local agent platform.

### API

- [ ] Add FastAPI
- [ ] `GET /health`
- [ ] `GET /runs`
- [ ] `GET /runs/{id}`
- [ ] `POST /issues/{id}/run`
- [ ] `POST /runs/{id}/cancel`
- [ ] expose agent status
- [ ] expose LM Studio connectivity status
- [ ] expose GitHub connectivity status

### GitHub integration

- [ ] Replace polling with GitHub webhooks where appropriate
- [ ] Support GitHub App authentication
- [ ] Support installation-scoped credentials
- [ ] Handle issue events
- [ ] Handle PR events
- [ ] Handle review comments
- [ ] Handle CI completion events

### Observability

- [ ] Prometheus metrics
- [ ] Grafana dashboard
- [ ] token usage
- [ ] prompt tokens
- [ ] completion tokens
- [ ] model
- [ ] runtime
- [ ] issue
- [ ] repository
- [ ] success/failure
- [ ] tests passed/failed
- [ ] number of files changed
- [ ] number of Codex/tool calls

### Agent capabilities

- [ ] Multiple local models
- [ ] Select model based on task
- [ ] Multiple concurrent workers
- [ ] Configurable repository rules
- [ ] Repository-specific prompts
- [ ] Repository-specific `AGENTS.md`
- [ ] Documentation lookup tools
- [ ] Controlled web-search capability
- [ ] Allowlisted external documentation sources
- [ ] Agent timeout limits
- [ ] Maximum token limits
- [ ] Maximum iteration limits

### Security

- [ ] Run agents using restricted OS permissions
- [ ] Improve workspace isolation
- [ ] Restrict inherited environment variables
- [ ] Restrict filesystem access
- [ ] Restrict network access
- [ ] Configurable domain allowlist
- [ ] audit agent commands
- [ ] audit external requests
- [ ] credential rotation
- [ ] investigate containerized execution

---

# Possible V4 ideas

Not yet planned for implementation.

Potential directions include:

- GitLab support
- multiple repositories
- multiple agent workers
- task queues
- scheduled development tasks
- specialised reviewer agents
- architecture-review agents
- automated issue refinement
- automatic acceptance-criteria checking
- dependency update agents
- documentation agents
- security-review agents
- GitHub Projects integration
- agent dashboards
- model benchmarking
- agent performance comparison
- remote worker machines
- container or Kubernetes workers

LocalForge should remain provider-independent where practical so GitHub, GitLab, Codex and LM Studio can eventually be replaced without redesigning the entire orchestration layer.

---

# Non-goals

LocalForge is not intended to:

- replace GitHub
- replace Codex
- implement its own LLM inference server
- automatically merge code without human oversight
- give an LLM unrestricted access to infrastructure credentials
- become a large workflow platform before the basic use case works

The initial objective is deliberately narrow:

> Turn a well-defined GitHub issue into a locally generated code change using Codex and an LM Studio model.
