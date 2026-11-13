# Implementation status

> 13 November 2026 update: the local fixture flow and a three-case real local-model smoke run were verified. See [local verification](LOCAL-FIXTURE-VERIFICATION-2026-11-13.md) for evidence and current limitations. Historical status below describes the September hackathon milestone, not the current local-provider work.

Audience: Om and anyone continuing the build. Updated 19 September 2026.

Legend: ✅ built and verified · 🟡 built, not yet exercised against the real service · ⛔ blocked on an
account or credential · ⬜ not started.

## Phases

| Phase | State | Evidence |
|---|---|---|
| 0 Repository and disclosure | ✅ | Repo, dated disclosure, `.env.example`, lockfiles, CI workflow written |
| 1 Live Nebius/NVIDIA access | ⛔ | Provider, catalog discovery, NVIDIA filter and validation are built and unit-tested with mocked HTTP. `scripts/live_smoke.py` is ready. **Needs `NEBIUS_TOKEN_FACTORY_API_KEY`.** No live call has been made. |
| 2 Five-case vertical slice | ✅ (fixture) · ⛔ (live) | CLI runs paired cases end to end with the fixture provider |
| 3 Persistence and orchestration | ✅ | Idempotent creation, persisted events, SSE resume, cancel, resume without duplicate runs (API tests) |
| 4 Grading, metrics, policy | ✅ | Full grader set, benchtrace McNemar and Wilson intervals, measurement labels, pass/warn/block, 20-case synthetic suite plus three commit-pinned public-repository workloads |
| 5 Investigation | ✅ rule-based · 🟡 model-based | Rule investigator classifies real fixture regressions with step references. Model investigator (strict JSON, validated references, rule fallback) is written but not wired to a live model. |
| 6 API and accessible web app | ✅ | Light evaluation-lab UI, setup, budget confirmation, persistent six-stage journey, evidence tabs, cases, traces, timeline, notifications, in-product presentation and system-design explainer. Component-tested against live event updates. |
| 7 3D Model Lab | 🟡 | Light operations room with physical zone signs, desks, workers, monitors, servers, test and policy stations, event-driven work packets, lazy loading, reduced-motion and no-WebGL fallbacks. **Still needs a final visual check in a normal browser.** |
| 8 GitHub release gate | 🟡 | Check-run upsert, HMAC webhooks and dedupe tested with mocks. **Needs `GITHUB_TOKEN` and a demo PR.** |
| 9 Deployment and submission | ⬜ | Rules checklist written. Still needs public repository, hosting, final live NVIDIA run, real GitHub check, video and Devpost entry. |

## Test counts (19 Sep)

- Engine: 47 · API: 13 · Web: 11 (reducer, components, live page hydration, presentation and system design)
- 20-case fixture experiment: about 21 s via CLI; through the API and SSE it completed with 40 persisted
  runs and 579 events.

## Also not yet done

- Docker sandbox backend exercised (daemon was not running; host UID/GID write mapping is implemented)
- Alembic migrations (tables created from models)
- GitHub App / OAuth sign-in (a fine-grained token is used instead)
- Hosted deployment, PostgreSQL
- Playwright end-to-end suite (headless Chrome screenshots used for now)

## Next actions for Om

1. Claim both Token Factory credit offers, create a project key and put it in `.env` locally. Never paste it
   into chat or git.
2. Run `make live-smoke`. It records the catalog, validates the first NVIDIA model and runs five paired cases.
3. Make ReplayForge public, verify its license while signed out, and deploy a free judge-accessible build.
4. Create a small public demo repository with one PR and a fine-grained token with `checks:write`.
5. Open `http://localhost:5173` in a normal browser to confirm the 3D lab renders.
