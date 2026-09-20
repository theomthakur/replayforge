# ReplayForge system design

ReplayForge is a model-migration and reliability lab for coding agents. It replays the same
repository tasks on a baseline model and an NVIDIA open model, executes each case in a fresh
sandbox, grades the resulting work with deterministic checks, and applies a stored release policy.
The output is evidence a team can inspect and publish to a pull request—not a model's opinion of
its own work.

This document describes the implemented hackathon prototype. Items that still require credentials
or live-service verification remain explicit in `IMPLEMENTATION-STATUS.md`.

## 1. Design goals

1. Compare models on the coding-agent work a team actually depends on.
2. Keep prompts, tools, limits, repositories and graders identical across both lanes.
3. Make deterministic tests—not model prose—the source of correctness.
4. Persist every meaningful transition before it appears in the browser.
5. Separate measured, provider-reported, derived, estimated and unknown values.
6. Turn stored evidence into a reproducible pass, warn or block decision.
7. Fail closed when a model, fixture, path, tool call or external delivery is invalid.

## 2. System context

```text
Engineer
  | suite + models + release policy + optional pull request
  v
React command center  <---- REST snapshot + resumable SSE ---->  FastAPI control plane
                                                               | orchestration
                                                               | idempotency
                                                               | event persistence
                                                               v
                                                    +----------+----------+
                                                    |                     |
                                             Baseline provider     NVIDIA candidate
                                             current / fixture     Nebius Token Factory
                                                    |                     |
                                                    +----------+----------+
                                                               v
                                                  fresh sandbox per case
                                                               |
                                               bounded agent tool loop
                                                               |
                                                deterministic graders
                                                               |
                                      paired metrics + referenced investigation
                                                               |
                                              deterministic release policy
                                                               |
                                               stored report + GitHub check
```

The API is the only authority allowed to mutate experiment state. The browser requests operations
and renders stored facts. The accessible tables, notifications, workflow journey and 3D lab all
consume the same snapshot and event reducer.

## 3. Major components

| Component | Responsibility | Does not decide |
|---|---|---|
| React web app | Configure a run, show progress, inspect traces and publish a stored decision | Whether a case passed |
| FastAPI control plane | Validate requests, persist state, schedule lanes, resume and stream events | Whether model prose is correct |
| Provider adapters | Produce assistant messages and tool calls through a shared interface | Grader result or release outcome |
| Sandbox tools | Read, search, patch and run allowlisted commands in a disposable workspace | What the model should claim |
| Deterministic graders | Check commands, tests, files, protected paths, outputs and tool contracts | Release-policy thresholds |
| Investigator | Classify failures and disagreements with evidence references | Final pass, warn or block |
| Policy engine | Apply stored thresholds to stored metrics and critical-task results | How findings should be narrated |
| GitHub adapter | Upsert one check run for the experiment | A different decision from the stored one |

## 4. Experiment lifecycle

```text
created -> running -> investigating -> deciding -> completed
                    \                         \
                     +-> failed               +-> failed

created / running / investigating / deciding -> cancelled
```

The control plane commits an event before notifying SSE subscribers. On startup it finds experiments
left in an active state and resumes them. A unique key across experiment, task, repeat and lane stops a
resume from duplicating completed case runs.

### Case lifecycle

```text
queued -> provisioning -> reasoning <-> tool_execution -> grading -> passed | failed
```

One visible work packet in the 3D lab corresponds to one saved case on one lane. Its position comes
from this lifecycle; animation never advances experiment state.

## 5. Paired-run protocol

For every selected task ReplayForge:

1. Locks the suite definition and fixture into a digest.
2. Creates independent sandbox copies for baseline and candidate lanes.
3. Supplies the same task, system prompt, tool schemas and step limits.
4. Records provider messages, validated tool calls, observations, latency and usage.
5. Runs the task's configured deterministic graders.
6. Pairs lane outcomes by task and repeat rather than comparing aggregate anecdotes.
7. Computes pass rate, intervals, exact McNemar result, latency and cost per success.
8. Investigates disagreements and failures with references to saved steps and graders.
9. Applies the stored release policy and persists its violations and summary.

Fixture providers are deterministic rehearsals, not models. The CLI, API, report, UI and GitHub check
all label fixture mode.

## 6. Trust boundaries

### Model boundary

The model can select schema-validated tools inside a bounded loop. It cannot change the task, fixture,
grader, metric, policy or final decision. An unknown fixture profile or invalid live model is rejected
before execution.

### Execution boundary

Each case receives a new workspace. Local execution resolves paths against the workspace, rejects
escapes and unsafe patch headers, scrubs inherited environment variables, kills timed-out process
groups, and limits CPU, file size and captured output. A networkless, read-only-root Docker backend is
implemented but still needs a live daemon exercise.

### Evidence boundary

Deterministic graders own correctness. Rule-based investigation is the default. Optional model-assisted
investigation must return validated structured output and valid evidence references; otherwise the
system falls back to rules. Investigation remains a hypothesis, not a grader.

### Release boundary

The policy engine consumes stored metrics and critical-task results. GitHub publishing can only deliver
that decision. Retries update the existing check identified by the experiment rather than creating a
new authority record.

## 7. Persistence model

SQLite is the local authoritative store. The SQLAlchemy models are compatible with a later PostgreSQL
deployment.

- `suites`: immutable definition and fixture digest;
- `experiments`: models, policy, status, source revision, timestamps and external handoff;
- `case_runs`: one lane execution with trace, grading and usage data;
- `events`: append-only, ordered state transitions used for SSE replay;
- `investigations`: taxonomy, narrative and evidence references;
- `decisions`: outcome, policy version, violations, report and delivery state;
- `idempotency_keys` and webhook deliveries: duplicate-request protection.

Database schema migrations are not yet implemented; local tables are created from the models. Delete an
older prototype database before a demo if its schema predates the current source.

## 8. Failure behavior

| Failure | Behavior |
|---|---|
| Unknown fixture profile | Reject with the valid profile list at CLI, provider and API boundaries |
| Candidate is not an NVIDIA catalog model | Reject a live hackathon run before spending tokens |
| Malformed tool arguments | Record a failed observation; the bounded agent may recover |
| Path escape, symlink patch or unsafe command | Reject without modifying the workspace |
| Provider timeout or non-success response | Store the failure; never translate it into a passed case |
| Usage or dated price unavailable | Cost is `unknown`, not zero |
| SSE disconnect | Reload the snapshot and resume after the last event ID |
| Process restart | Resume active experiments and skip stored runs |
| GitHub delivery failure | Preserve the decision, expose delivery failure and allow an idempotent retry |

## 9. Non-functional requirements

- **Integrity:** deterministic graders and policy own correctness and release authority.
- **Reproducibility:** suite digest, source revision and dirty-tree state travel with reports.
- **Auditability:** traces, graders, measurement labels, policy violations and ordered events are stored.
- **Recoverability:** active experiments resume without duplicating completed work.
- **Security:** credentials stay server-side; model tools run within explicit boundaries.
- **Cost control:** the preflight estimates provider calls and requires confirmation above the budget.
- **Accessibility:** every 3D state has a table, text label or evidence view equivalent.
- **Performance:** the 3D bundle is lazy; UI hydration begins from a compact snapshot and streams deltas.

## 10. Deployment shape

The hackathon build runs the API, worker orchestration and SQLite in one process for clarity. A production
shape would split API and workers, move state to PostgreSQL, store large traces in object storage, use a
queue for lane work, and deploy the sandbox on isolated compute rather than beside the control plane.
Those components are intentionally not claimed as implemented.

## 11. Verification

```bash
make test                 # engine and API tests
make web-test             # component and reducer tests
make fixture-run          # complete 20-case paired rehearsal
make api                  # terminal 1
make web                  # terminal 2
make live-smoke           # requires a Nebius Token Factory API key
```

The repository also provides `ruff`, TypeScript, production-build and CI checks. Current counts and
unverified external integrations are maintained in `IMPLEMENTATION-STATUS.md`.
