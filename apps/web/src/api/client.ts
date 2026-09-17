import type { ExperimentSnapshot, ModelCatalog, RunTrace } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : detail?.message ?? `Request failed (${response.status})`;
    const error = new Error(message) as Error & { status: number; detail: unknown };
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  return body as T;
}

export const api = {
  models: () => request<ModelCatalog>("/api/models"),
  suites: () => request<{ file: string; id?: string; name?: string; tasks?: number; digest?: string; error?: string }[]>("/api/suites/available"),
  createSuite: (path: string) => request<{ id: string; digest: string; name: string; case_count: number }>("/api/suites", { method: "POST", body: JSON.stringify({ path }) }),
  suite: (id: string) => request<{ id: string; definition: { tasks: { id: string; category: string; critical?: boolean; description: string }[] } }>(`/api/suites/${id}`),
  estimate: (body: unknown) => request<Record<string, number | boolean | string>>("/api/experiments/estimate", { method: "POST", body: JSON.stringify(body) }),
  createExperiment: (body: unknown, key: string) =>
    request<ExperimentSnapshot>("/api/experiments", { method: "POST", body: JSON.stringify(body), headers: { "Idempotency-Key": key } }),
  experiments: () => request<{ id: string; status: string; created_at: string; fixture_mode: boolean; outcome: string | null; baseline: { model: string }; candidate: { model: string } }[]>("/api/experiments"),
  experiment: (id: string) => request<ExperimentSnapshot>(`/api/experiments/${id}`),
  start: (id: string) => request<{ started: boolean }>(`/api/experiments/${id}/start`, { method: "POST" }),
  cancel: (id: string) => request<{ cancelled: boolean }>(`/api/experiments/${id}/cancel`, { method: "POST" }),
  trace: (runId: string) => request<RunTrace>(`/api/runs/${runId}/trace`),
  publish: (id: string, pullRequestUrl?: string) =>
    request<{ delivered: boolean; check_url: string }>(`/api/experiments/${id}/publish-github`, {
      method: "POST",
      body: JSON.stringify({ pull_request_url: pullRequestUrl || null }),
    }),
};
