# ReplayForge

**A model-migration and reliability lab for coding agents.**

ReplayForge replays the same coding-agent workloads against a baseline and candidate model, executes both agents' work in separate local workspaces, grades the results with
deterministic tests, investigates regressions, and turns a stored policy into a pass, warn or block
decision that can be published to a GitHub pull request.

The default UI is goal-driven: choose a commit-pinned repository workload, state the migration goal,
and start one autonomous audit. The mission controller selects only signed cassette tasks, derives the
bounded policy, validates the provider-call budget, dispatches both coding agents, investigates drift,
applies the release gate, and generates the report. Manual configuration remains available as an
advanced path; exceeding the budget or publishing externally still requires explicit authority.

> Built for the Nebius x NVIDIA Global AI Hackathon 2026, Coding and Agentic Engineering track.
> ReplayForge is an evaluation prototype, not a secure production code-execution platform.

## Current status

ReplayForge runs locally without sponsor credentials. The scripted 20-case fixture suite and a small
three-task comparison of two local models have been exercised; the latter is a smoke test, not evidence
for a model ranking. Live Nebius inference, real GitHub checks and an interactive browser walkthrough have
not been verified. The local API has no authentication and the process-level sandbox is not a security
boundary for untrusted code; do not expose it publicly. See the [verification notes](docs/LOCAL-FIXTURE-VERIFICATION-2026-11-13.md)
for the test results and limitations.

## The question it answers

> Can we move this coding agent to an open model without introducing tool-use regressions, lowering task
> success, or spending more per successful result?

Token prices and static benchmarks miss what actually breaks in agents: malformed tool arguments, wrong
files, plausible code that fails tests, weaker recovery after an error, and longer trajectories that erase
a cheaper price. ReplayForge measures all of it on the same versioned tasks.

## How it works

1. **Cassette suite.** Versioned coding tasks over a repository fixture, each with deterministic graders
   (command exit, test counts, protected paths, file checks, tool-call contracts, output checks). The suite
   and fixture are hashed into an immutable digest.

The bundled workload picker includes the 20-case synthetic reliability suite plus three small,
commit-pinned snapshots of public repositories owned by the project author: portfolio optimization,
Medicare claims analytics, and equity-alpha research. The UI links each snapshot to its source repository
and exact Git revision; only the files needed for deterministic evaluation are copied into the fixture.
2. **Paired runs.** Every task runs on both lanes with identical prompts, tools and limits, each in a fresh
   sandbox copy of the fixture.
3. **Tests outrank opinions.** Graders decide correctness. No model grades itself.
4. **Investigation.** Failures and disagreements are classified into a fixed taxonomy with references to
   the exact trace steps and graders. Findings are labelled hypotheses.
5. **Honest metrics.** Pass rate with intervals and an exact McNemar test (from benchtrace), latency p50
   and p95 with visible n, and cost per success only when usage and a dated price exist. Unknown pricing remains unknown in summary metrics; raw traces may contain a zero placeholder when
   `pricing_known` is false.
6. **Deterministic policy.** Pass-rate drop, critical tasks, provider error rate (block); p95 latency and
   cost per success (warn).
7. **Release gate.** One GitHub check run per experiment, updated rather than duplicated on retry.
8. **Reliability operations floor.** A persistent workflow journey, accessible evidence views and a
   realistic 3D operations room are all driven by the same stored event log.

The app also includes a judge-ready **Presentation** route and an interactive **System design** route.
The detailed engineering design lives in [docs/SYSTEM-DESIGN.md](docs/SYSTEM-DESIGN.md). The rules-based
submission checklist and credit plan live in
[docs/SUBMISSION-READINESS.md](docs/SUBMISSION-READINESS.md).

## Built on benchtrace

ReplayForge imports [benchtrace](https://github.com/theomthakur/benchtrace) (Apache-2.0, pre-existing,
commit `7588dca`) for its trace schema, provider interface, statistics and pricing. Everything in this
repository is new hackathon work. See [docs/HACKATHON-DISCLOSURE.md](docs/HACKATHON-DISCLOSURE.md).

## Quick start (no credentials needed)

Requires Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 18+ and Git. The lockfile pins
`benchtrace` to a public Git revision; no sibling checkout is needed. Installation requires network access.

```bash
make install          # installs the pinned benchtrace dependency and web packages
make test            # engine + API tests, fixture providers only
make web-test
make fixture-run     # 20 paired cases; writes a new data/runs/fixture-*/report.md
make api             # terminal 1: http://127.0.0.1:8000
make web             # terminal 2: http://localhost:5173
```

The **fixture provider** replays scripted reference solutions; it makes no model calls and cannot
demonstrate live-model quality. Any experiment that
uses it is labelled "fixture mode" in the CLI, API, report, UI and GitHub check.

Local fixture verification and current limitations: [verification notes](docs/LOCAL-FIXTURE-VERIFICATION-2026-11-13.md).

## Optional local model comparison (no sponsor)

The `local` provider uses an OpenAI-compatible chat-completions server on an HTTP loopback address. Start an appropriate local runtime yourself and install tool-capable models before use. The project does not start, download, or verify models automatically. Set model names exposed in the local UI, then start the local API and web app:

```bash
export REPLAYFORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export REPLAYFORGE_LOCAL_MODELS=qwen2.5:3b,llama3.2:latest
make api
# In a second terminal: make web
```

The names above are examples, not an assurance those models support this task or are installed. Both lanes are selectable in advanced setup. Local endpoint responses must support OpenAI-style tool calls and the model's template must support the supplied tools. The server reports provider errors when they do not. Usage/cost can remain unknown. Only use trusted fixtures: the default local process sandbox is not a hardened security boundary, and the local API has no authentication.

The CLI can use the same endpoint without `REPLAYFORGE_LOCAL_MODELS`:

```bash
.venv/bin/replayforge run --suite fixtures/suites/demo-suite.yaml \
  --baseline local:MODEL_A --candidate local:MODEL_B \
  --out data/runs/my-first-local-comparison
```

Each run requires a **new output directory** so old traces cannot be mixed with a new summary. An interrupted run leaves its traces in place for inspection; choose another path for a retry. Run outcome `BLOCK` is a policy decision, not necessarily a command failure. The adapter has mock-protocol tests and a small real local-model smoke run; see the verification notes. Three cases are too few to establish model ranking.

## Optional Nebius Token Factory integration (not verified live)

```bash
cp .env.example .env    # set NEBIUS_TOKEN_FACTORY_API_KEY; never commit .env
set -a; source .env; set +a
.venv/bin/replayforge models                  # live catalog, NVIDIA entries marked
.venv/bin/replayforge validate-model <model-id>
make live-smoke                              # five paired cases, evidence written to evidence/
```

No model identifier is hardcoded. Candidates come from the account's live `/models` response.
For this hackathon build, the **candidate** side of a live Nebius experiment is intentionally restricted
to NVIDIA models returned by that catalog. Reverse migrations to non-NVIDIA candidates are outside the
submission scope; the baseline lane remains provider-configurable.

## Repository map

```text
packages/engine/     cassettes, sandbox + tools, providers (local, Nebius, fixture), agent loop,
                     graders, metrics, policy, investigation, report, CLI
apps/api/            FastAPI control plane: persistence, orchestration, SSE, GitHub gate
apps/web/            React + TypeScript app, accessible views and the 3D Model Lab
fixtures/            synthetic suite, commit-pinned public-repository snapshots, reference solutions
scripts/             live Nebius smoke test
docs/                system design, submission readiness, security, demo, disclosure, implementation status
```

## Status

See [docs/IMPLEMENTATION-STATUS.md](docs/IMPLEMENTATION-STATUS.md) for exactly what is verified and what
still needs credentials or a live service.
