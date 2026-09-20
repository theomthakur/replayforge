# ReplayForge

**A model-migration and reliability lab for coding agents.**

ReplayForge replays the same coding-agent workloads against a team's current model and an NVIDIA open
model on Nebius Token Factory, executes both agents' work in isolated sandboxes, grades the results with
deterministic tests, investigates regressions, and turns a stored policy into a pass, warn or block
decision that can be published to a GitHub pull request.

> Built for the Nebius x NVIDIA Global AI Hackathon 2026, Coding and Agentic Engineering track.
> ReplayForge is an evaluation prototype, not a secure production code-execution platform.

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
   and p95 with visible n, and cost per success only when usage and a dated price exist. Unknown stays
   unknown, never zero.
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
commit `c50b962`) for its trace schema, provider interface, statistics and pricing. Everything in this
repository is new hackathon work. See [docs/HACKATHON-DISCLOSURE.md](docs/HACKATHON-DISCLOSURE.md).

## Quick start (no credentials needed)

Requires Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 18+, and `benchtrace` checked out two
directories above this repository (`../../benchtrace`).

```bash
make install
make test            # engine + API tests, fixture providers only
make web-test
make fixture-run     # 20 paired cases through the CLI, writes data/runs/fixture/report.md
make api             # terminal 1: http://127.0.0.1:8000
make web             # terminal 2: http://localhost:5173
```

The **fixture provider** replays scripted reference solutions. It is not a model. Any experiment that
uses it is labelled "fixture mode" in the CLI, API, report, UI and GitHub check.

## Live run on Nebius Token Factory

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
packages/engine/     cassettes, sandbox + tools, providers (Nebius, fixture), agent loop,
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
