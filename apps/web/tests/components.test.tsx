import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import type { ExperimentSnapshot } from "../src/api/types";
import { CasesTable } from "../src/features/experiments/CasesTable";
import { ComparisonWall } from "../src/features/experiments/ComparisonWall";
import { hydrate } from "../src/features/experiments/labState";
import { NotificationCenter } from "../src/features/notifications/NotificationCenter";

const snapshot = {
  id: "e", status: "completed", fixture_mode: true, error: null, created_at: "", started_at: null, completed_at: null,
  suite: { id: "s", name: "Suite", digest: "sha256:abc" },
  baseline: { provider: "fixture", model: "fixture/reference" }, candidate: { provider: "nebius", model: "nvidia/x" },
  policy: {}, budget: {}, pull_request_url: null,
  tasks: [{ id: "pay", category: "bug_fix", critical: true, description: "" }, { id: "nav", category: "navigation", critical: false, description: "" }],
  runs: [
    { id: "1", task_id: "pay", lane: "baseline", status: "completed", passed: true, provider: "f", model: "m", latency_ms: 1, input_tokens: 0, output_tokens: 0, provider_cost: null, failure_mode: null },
    { id: "2", task_id: "pay", lane: "candidate", status: "failed", passed: false, provider: "f", model: "m", latency_ms: 1, input_tokens: 0, output_tokens: 0, provider_cost: null, failure_mode: "invalid_response" },
  ],
  pairs: [{ id: "p", task_id: "pay", critical: true, outcome: "candidate_regressed", baseline_run_id: "1", candidate_run_id: "2",
            trajectory_delta: { baseline_tools: [], candidate_tools: [], step_delta: 0 },
            investigation: { category: "malformed_arguments", confidence: 0.8, summary: "bad args", evidence_refs: ["step:1"], method: "rule" } }],
  metrics: [
    { lane: "baseline", name: "pass_rate", value: 1, unit: "ratio", measurement_kind: "measured", sample_count: 2, source: "" },
    { lane: "candidate", name: "pass_rate", value: 0.5, unit: "ratio", measurement_kind: "measured", sample_count: 2, source: "" },
    { lane: "candidate", name: "cost_per_success_usd", value: null, unit: "usd", measurement_kind: "estimated", sample_count: 1, source: "" },
  ],
  comparison: null,
  decision: { outcome: "block", violations: [{ rule: "critical_tasks_must_pass", severity: "block", message: "critical tasks failing on candidate: pay" }], summary: "BLOCK", policy_version: "rf-policy-1", delivery_status: "not_requested", delivery_error: null, github_check_url: null },
  last_event_seq: 10,
} as unknown as ExperimentSnapshot;

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);

describe("accessible views", () => {
  it("shows unknown cost explicitly instead of zero", () => {
    wrap(<ComparisonWall snapshot={snapshot} state={hydrate(snapshot)} />);
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.queryByText("$0.0000")).not.toBeInTheDocument();
    expect(screen.getAllByText("BLOCK").length).toBeGreaterThan(0);
    expect(screen.getByText(/critical tasks failing/)).toBeInTheDocument();
  });

  it("selects a case from the keyboard-accessible table", () => {
    const onSelect = vi.fn();
    wrap(<CasesTable snapshot={snapshot} state={hydrate(snapshot)} selected={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "Inspect pay" }));
    expect(onSelect).toHaveBeenCalledWith("pay");
    expect(screen.getByText("regressed")).toBeInTheDocument();
    expect(screen.getByText("malformed_arguments")).toBeInTheDocument();
  });

  it("notification links select the related case and lane", () => {
    const onOpen = vi.fn();
    wrap(<NotificationCenter notifications={[{ id: "n", seq: 1, severity: "error", title: "Critical regression found", detail: "pay", taskId: "pay", lane: "candidate" }]} onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(screen.getByRole("button", { name: /Critical regression found/ }));
    expect(onOpen).toHaveBeenCalledWith("pay", "candidate");
  });
});
