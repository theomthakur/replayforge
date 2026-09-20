# Demo script (three minutes)

Audience: the person recording the submission video.

Rules: every number on screen comes from a saved experiment. A fixture run is labelled fixture and is never
presented as a model result. If a live call fails while recording, show the real error, then open the
previous real run, labelled as a previous run.

1. **0:00 to 0:20, problem.** Benchmarks show how a model answers prompts, not whether our coding agent
   still picks the right tools and passes its tests after a migration.
2. **0:20 to 0:40, setup.** Choose **Portfolio optimization · real repository** and point out the linked
   GitHub repository, pinned commit, suite digest, baseline model, live NVIDIA model from the Token Factory
   catalog, migration policy and budget estimate.
3. **0:40 to 1:25, parallel run.** Start. Work packets enter the signed baseline and NVIDIA lanes in the
   Model Lab only as events arrive.
   Open one live trace: tool calls and sandbox output.
4. **1:25 to 2:05, evidence.** Comparison wall, one disagreement, the failing deterministic grader, the
   investigator's category with step references, labelled as a hypothesis.
5. **2:05 to 2:35, decision.** Pass rate, p95, cost per success (or "unknown" if no price is configured),
   the policy decision, the published GitHub check.
6. **2:35 to 3:00, why Nebius and NVIDIA.** The recorded model ID and provider request IDs: a team tests an
   open NVIDIA model on its own workloads instead of trusting a leaderboard.

The header includes **Presentation** and **System design** routes for judge questions after the timed demo.
