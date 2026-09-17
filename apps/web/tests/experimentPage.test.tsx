import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";

import { ExperimentPage } from "../src/features/experiments/ExperimentPage";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners: Record<string, ((m: { data: string }) => void)[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { FakeEventSource.instances.push(this); }
  addEventListener(type: string, fn: (m: { data: string }) => void) { (this.listeners[type] ??= []).push(fn); }
  emit(data: unknown) { for (const fn of this.listeners.replayforge ?? []) fn({ data: JSON.stringify(data) }); }
  close() {}
}

const snapshot = {
  id: "a".repeat(32), status: "running", fixture_mode: true, error: null, created_at: "", started_at: null, completed_at: null,
  suite: { id: "s", name: "Suite", digest: "sha256:abcdefabcdefabcdefabcdef" }, baseline: { provider: "fixture", model: "b" }, candidate: { provider: "fixture", model: "c" },
  policy: {}, budget: {}, pull_request_url: null,
  tasks: [{ id: "pay", category: "bug_fix", critical: true, description: "" }],
  runs: [{ id: "1", task_id: "pay", lane: "baseline", status: "completed", passed: true, provider: "f", model: "m", latency_ms: 1, input_tokens: 0, output_tokens: 0, provider_cost: null, failure_mode: null }],
  pairs: [], metrics: [], comparison: null, decision: null, last_event_seq: 7,
};

describe("ExperimentPage live state", () => {
  beforeEach(() => {
    (globalThis as unknown as { EventSource: unknown }).EventSource = FakeEventSource;
    globalThis.fetch = vi.fn(async (url: string) => ({
      ok: true, status: 200,
      text: async () => JSON.stringify(String(url).includes("event-log") ? [] : snapshot),
      json: async () => (String(url).includes("event-log") ? [] : snapshot),
    })) as unknown as typeof fetch;
  });

  it("hydrates from the snapshot and then applies streamed events", async () => {
    render(<QueryClientProvider client={new QueryClient()}><ExperimentPage experimentId={"a".repeat(32)} /></QueryClientProvider>);
    await waitFor(() => expect(screen.getAllByText("running").length).toBeGreaterThan(0));
    expect(screen.getAllByText("pass").length).toBeGreaterThan(0);
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));
    const source = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    expect(source.url).toContain("after=7");
    act(() => source.emit({ schema_version: "1.0", event_id: "e8", seq: 8, experiment_id: "x", type: "tool.started", actor_type: "agent", actor_id: null, occurred_at: null, payload: { task_id: "pay", lane: "candidate", tool: "read_file" } }));
    await waitFor(() => expect(screen.getByText("tool: read_file")).toBeInTheDocument());
  });
});
