# Local fixture verification - 13 November 2026

A fresh temporary checkout of commit `0a101c2` plus this workspace's uncommitted changes was checked on 13 November. It is not a clean committed release.

- The developer-specific editable dependency was replaced with public benchtrace Git revision `7588dcaea1496c5725f0895f9a7a9df3bd1d300e`; `uv sync --python 3.12 --all-packages --locked` succeeded without a sibling checkout.
- Fresh-checkout backend: 69 tests passed. Fresh-checkout frontend: `npm ci`, TypeScript check, 13 tests and production build passed. The build warned about a large 3D chunk.
- The scripted 20-case paired fixture suite completed with the expected BLOCK for seeded regressions. It is not live-model quality evidence.
- An interactive browser check was attempted but did not complete in this environment. No live Nebius, GitHub check or public deployment was verified.
- The existing uncommitted `docs/SUBMISSION-READINESS.md` change predates this work and was preserved.

## Sponsor-independent local-model smoke: three tasks

On 13 November, local Ollama HTTP endpoint on loopback, `qwen2.5:3b` baseline (model digest prefix 357c53fb659c5076) and `llama3.2:latest` candidate (a80c4f17acd55265), with temperature 0, seed 7, max 2,048 output tokens per call, concurrency 1. Identical three synthetic tasks, separate disposable workspaces, deterministic graders; one repetition per model/task. Runtime: local Apple M4; no hosted inference or provider charges recorded. Full run traces are stored locally under ignored `evidence/local-smoke-20261113/`.

| Task | Baseline | Candidate |
|---|---|---|
| tool-read-tax-rate | pass | fail (invalid_response) |
| tool-count-test-files | fail | fail (budget_exhausted) |
| nav-free-shipping | fail | fail (budget_exhausted) |

Paired result n=3: baseline 1/3, candidate 0/3, one baseline-only pass; McNemar p=1.0; policy BLOCK. A policy block on this toy sample is a configured gate, not a statistically supported conclusion about general model quality. The investigation heuristic labeled malformed arguments; the trace showed invalid line-range types and later no proper finish. It is a hypothesis, not independently adjudicated root cause. Pricing unknown is displayed as unknown in summary metrics; raw benchtrace cost fields can contain a numeric zero placeholder when metadata `pricing_known` is false and must not be interpreted as free measured compute. Latency percentiles are intentionally withheld for fewer than five samples; individual wall times and calls are recorded in traces.

Paired run ID: `7641381abb6248b0b27716b02f661878`; suite digest `sha256:1a0ef7c5addb9a9b77928a05d522acd5e7f7d7a375479d0608df400713dad8b7`. The source was dirty during this experiment: it included local adapter and clean-install work, so the HEAD commit alone does not reproduce the run. Repeat after committing an agreed revision for durable reproducibility. No live Nebius or GitHub check was performed.

## Completion status

The local fixture workflow and a small real local-model comparison were exercised; production hosting, hardened sandbox, an authenticated public API, and real GitHub check remain unverified/out of scope. Backend API integration tests exercise persisted fixture results and trace retrieval; interactive browser testing was attempted but could not complete headlessly in this environment. UI component tests and production build passed. Dependencies show six npm audit findings (two moderate, two high, two critical) across development dependencies; `npm audit --omit=dev` returned zero production findings on this check. Review and update dev dependencies in a separate compatibility-tested change.
