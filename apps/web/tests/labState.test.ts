import { applyEvent, caseKey, emptyState, hydrate } from "../src/features/experiments/labState";
import type { ExperimentSnapshot, ReplayEvent } from "../src/api/types";

let seq = 0;
const ev = (type: string, payload: Record<string, unknown> = {}): ReplayEvent => ({
  schema_version: "1.0", event_id: `e${++seq}`, seq, experiment_id: "x", type, actor_type: "system", actor_id: null, occurred_at: null, payload,
});

describe("lab state reducer", () => {
  beforeEach(() => { seq = 0; });

  it("walks a case through its lifecycle only on events", () => {
    let s = emptyState();
    s = applyEvent(s, ev("experiment.started"));
    s = applyEvent(s, ev("case.queued", { task_id: "t", lane: "candidate", critical: true }));
    expect(s.cases[caseKey("t", "candidate")].stage).toBe("queued");
    s = applyEvent(s, ev("tool.started", { task_id: "t", lane: "candidate", tool: "read_file" }));
    expect(s.cases[caseKey("t", "candidate")]).toMatchObject({ stage: "tool_execution", tool: "read_file" });
    s = applyEvent(s, ev("tool.failed", { task_id: "t", lane: "candidate", error_kind: "malformed_arguments" }));
    s = applyEvent(s, ev("case.failed", { task_id: "t", lane: "candidate", passed: false, failure_mode: null }));
    expect(s.cases[caseKey("t", "candidate")]).toMatchObject({ stage: "failed", toolFailures: 1, toolCalls: 1 });
  });

  it("ignores events at or before the cursor", () => {
    let s = applyEvent(emptyState(), ev("experiment.started"));
    const again = applyEvent(s, { ...ev("experiment.failed", { error: "x" }), seq: 1 });
    expect(again.status).toBe("running");
  });

  it("raises a critical-regression notification that links to the case", () => {
    let s = emptyState();
    s = applyEvent(s, ev("case.queued", { task_id: "pay", lane: "candidate", critical: true }));
    s = applyEvent(s, ev("pair.comparable", { task_id: "pay", outcome: "candidate_regressed" }));
    s = applyEvent(s, ev("investigation.completed", { task_id: "pay", category: "malformed_arguments", summary: "bad args" }));
    expect(s.notifications[0]).toMatchObject({ title: "Critical regression found", taskId: "pay", lane: "candidate" });
  });

  it("renders failed, cancelled and github failure states explicitly", () => {
    let s = applyEvent(emptyState(), ev("github.delivery.failed", { error: "401" }));
    expect(s.githubStatus).toBe("failed");
    s = applyEvent(s, ev("experiment.cancelled"));
    expect(s.status).toBe("cancelled");
  });

  it("hydrates from a snapshot", () => {
    const snapshot = {
      status: "completed", last_event_seq: 40,
      tasks: [{ id: "a", category: "bug_fix", critical: false, description: "" }],
      runs: [{ id: "r", task_id: "a", lane: "baseline", status: "completed", passed: true, provider: "f", model: "m", latency_ms: 5, input_tokens: 0, output_tokens: 0, provider_cost: null, failure_mode: null }],
      pairs: [], decision: { outcome: "pass", violations: [], summary: "", policy_version: "p", delivery_status: "not_requested", delivery_error: null, github_check_url: null },
    } as unknown as ExperimentSnapshot;
    const s = hydrate(snapshot);
    expect(s.cases[caseKey("a", "baseline")].stage).toBe("passed");
    expect(s.cases[caseKey("a", "candidate")].stage).toBe("queued");
    expect(s.decision).toBe("pass");
    expect(s.lastSeq).toBe(40);
  });
});
