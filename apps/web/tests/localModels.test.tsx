import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api } from "../src/api/client";
import { SetupPage } from "../src/features/experiments/SetupPage";

it("allows selecting configured local models independently for both lanes", async () => {
  vi.spyOn(api, "models").mockResolvedValue({
    fixture: [{ provider: "fixture", model: "fixture/reference" }, { provider: "fixture", model: "fixture/variant" }],
    baseline: [], local: [{ provider: "local", model: "qwen:3b", label: "Local: qwen:3b" }, { provider: "local", model: "llama:3b", label: "Local: llama:3b" }],
    nebius: { configured: false, models: [] },
  });
  vi.spyOn(api, "suites").mockResolvedValue([]);
  vi.spyOn(api, "experiments").mockResolvedValue([]);
  vi.spyOn(api, "createSuite").mockResolvedValue({ id: "s", digest: "abc", name: "test", case_count: 0 });
  vi.spyOn(api, "suite").mockResolvedValue({ id: "s", definition: { suite: { name: "test", description: "" }, tasks: [] } });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><SetupPage /></QueryClientProvider>);
  fireEvent.click(screen.getByText("Advanced controls"));
  await waitFor(() => expect(screen.getAllByRole("option", { name: "Local: qwen:3b" })).toHaveLength(2));
  const baseline = screen.getByLabelText("Baseline (current model)") as HTMLSelectElement;
  const candidate = screen.getByLabelText("Candidate model") as HTMLSelectElement;
  fireEvent.change(baseline, { target: { value: "local|qwen:3b" } });
  fireEvent.change(candidate, { target: { value: "local|llama:3b" } });
  expect(baseline.value).toBe("local|qwen:3b");
  expect(candidate.value).toBe("local|llama:3b");
});
