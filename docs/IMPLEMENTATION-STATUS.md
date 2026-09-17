# Implementation status

Audience: Om and anyone continuing the build. Updated 17 September 2026.

Legend: ✅ built and verified · 🟡 built, not yet exercised against the real service · ⛔ blocked on an
account or credential · ⬜ not started.

## Phases

| Phase | State | Evidence |
|---|---|---|
| 0 Repository and disclosure | ✅ | Repo, dated disclosure, `.env.example`, lockfiles, CI workflow written |
| 1 Live Nebius/NVIDIA access | ⛔ | Provider, catalog discovery, NVIDIA filter and validation are built and unit-tested with mocked HTTP. `scripts/live_smoke.py` is ready. **Needs `NEBIUS_TOKEN_FACTORY_API_KEY`.** No live call has been made. |
| 2 Five-case vertical slice | ✅ (fixture) · ⛔ (live) | CLI runs paired cases end to end with the fixture provider |
| 3 Persistence and orchestration | ✅ | Idempotent creation, persisted events, SSE resume, cancel, resume without duplicate runs (API tests) |
| 4 Grading, metrics, policy | ✅ | Full grader set, benchtrace McNemar and Wilson intervals, measurement labels, pass/warn/block, 20-case suite |
| 5 Investigation | ✅ rule-based · 🟡 model-based | Rule investigator classifies real fixture regressions with step references. Model investigator (strict JSON, validated references, rule fallback) is written but not wired to a live model. |
| 6 API and accessible web app | ✅ | Setup, budget confirmation, live experiment, cases table, trace inspector, timeline, notifications. Verified in headless Chrome against a live local API. |
| 7 3D Model Lab | 🟡 | Scene bound to the event reducer, lazy-loaded, reduced-motion and no-WebGL fallbacks. **Not visually confirmed:** headless Chrome could not capture the WebGL canvas. Check in a normal browser. |
| 8 GitHub release gate | 🟡 | Check-run upsert, HMAC webhooks and dedupe tested with mocks. **Needs `GITHUB_TOKEN` and a demo PR.** |
| 9 Deployment and submission | ⬜ | Hosting, final live 20-case run, video, Devpost |

## Test counts (17 Sep)

- Engine: 40 · API: 12 · Web: 9 (reducer, components, live page hydration)
- 20-case fixture experiment: about 21 s via CLI; through the API and SSE it completed with 40 persisted
  runs and 579 events.

## Also not yet done

- Docker sandbox backend exercised (daemon was not running)
- Alembic migrations (tables created from models)
- GitHub App / OAuth sign-in (a fine-grained token is used instead)
- Hosted deployment, PostgreSQL
- Playwright end-to-end suite (headless Chrome screenshots used for now)

## Next actions for Om

1. Create a Nebius Token Factory project key; put it in `.env` locally. Never paste it into chat or git.
2. Run `make live-smoke`. It records the catalog, validates the first NVIDIA model and runs five paired cases.
3. Create a small public demo repository with one PR and a fine-grained token with `checks:write`.
4. Open `http://localhost:5173` in a normal browser to confirm the 3D lab renders.
