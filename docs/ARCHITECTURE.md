# Architecture

Audience: engineers extending ReplayForge or judging its implementation.

```text
Web UI (React)  <-- REST snapshot + SSE (persisted events) --  FastAPI control plane
                                                                  |
                                              experiment orchestrator (asyncio, per-lane semaphores)
                                                  |                                   |
                                        baseline provider                    Nebius Token Factory
                                        (benchtrace / fixture)               (OpenAI-compatible)
                                                  |                                   |
                                                  +------ fresh sandbox per case -----+
                                                                  |
                                                     deterministic coding graders
                                                                  |
                                   rule investigator (+ optional validated model investigator)
                                                                  |
                                          metrics with measurement labels (benchtrace stats)
                                                                  |
                                               deterministic migration policy
                                                                  |
                                                     GitHub check run (release gate)
```

## Engine (`packages/engine`)

| Module | Responsibility |
|---|---|
| `cassettes` | Pydantic schema, safety checks (command allowlist, path containment, secret patterns), suite digest over definition and fixture bytes |
| `sandbox.local` | Disposable fixture copy, symlink-safe path resolution, scrubbed environment, process-group kill on timeout, CPU and file-size limits, output truncation |
| `sandbox.docker` | Same contract in a network-less, read-only, unprivileged container (written, not yet exercised) |
| `sandbox.tools` | JSON-Schema-validated tools; malformed arguments become recorded observations, not crashes |
| `providers.nebius` | benchtrace `OpenAICompatibleProvider` subclass, live catalog, NVIDIA filtering, validation completion |
| `providers.fixture` | Scripted, deterministic provider for tests and offline demos |
| `orchestration.agent` | Canonical system prompt, bounded tool loop, benchtrace `TraceRecord` output |
| `grading.coding` | command, test_count, forbidden_paths, file_exists/absent, file_regex, output_regex, tool_contract |
| `costing` | Lane metrics labelled measured, provider_reported, derived or estimated |
| `policy` | pass / warn / block rules; LLM text can never change the outcome |
| `investigation` | Taxonomy classification with evidence references |

## Control plane (`apps/api`)

- **Persistence:** SQLAlchemy on SQLite locally (PostgreSQL-compatible models). The database is
  authoritative. `case_runs` is unique per (experiment, task, case, repeat, lane).
- **Events:** each state change is committed to the append-only `events` table before subscribers are
  signalled. SSE resumes from `Last-Event-ID` or `?after=`.
- **Resume:** on startup, experiments left `running`, `investigating` or `deciding` resume and skip case
  runs that already exist.
- **Idempotency:** `Idempotency-Key` on experiment creation.
- **GitHub:** check run keyed by `external_id=replayforge-<experiment>`; retries update the same check.
  Webhooks are HMAC-verified and deduplicated by delivery ID.

## Web (`apps/web`)

A pure reducer (`labState.ts`) turns persisted events into case state. The table, trace inspector,
notifications and 3D lab all read that state, so the 3D view never shows activity the backend did not
record. The 3D bundle loads lazily and is optional.

Not yet built from the plan: Alembic migrations (tables are created from models), GitHub OAuth/App
installation, Nebius Serverless Jobs, Redis/queue workers, object storage for large traces.
