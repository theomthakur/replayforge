export type Lane = "baseline" | "candidate";
export type ExperimentStatus = "draft" | "ready" | "running" | "investigating" | "deciding" | "completed" | "cancelled" | "failed";

export interface LaneConfig {
  provider: string;
  model: string;
  temperature?: number | null;
  seed?: number | null;
  max_tokens?: number | null;
}

export interface TaskSummary {
  id: string;
  category: string;
  critical: boolean;
  description: string;
}

export interface RunSummary {
  id: string;
  task_id: string;
  lane: Lane;
  status: string;
  passed: boolean;
  provider: string;
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  provider_cost: number | null;
  failure_mode: string | null;
}

export interface Investigation {
  category: string;
  confidence: number;
  summary: string;
  evidence_refs: string[];
  method: string;
}

export interface Pair {
  id: string;
  task_id: string;
  critical: boolean;
  outcome: "both_pass" | "both_fail" | "candidate_regressed" | "candidate_improved";
  baseline_run_id: string;
  candidate_run_id: string;
  trajectory_delta: { baseline_tools: string[]; candidate_tools: string[]; step_delta: number };
  investigation: Investigation | null;
}

export interface Metric {
  lane: Lane;
  name: string;
  value: number | null;
  unit: string;
  measurement_kind: "measured" | "provider_reported" | "derived" | "estimated";
  sample_count: number;
  source: string;
  detail?: Record<string, unknown> | null;
}

export interface Violation {
  rule: string;
  severity: "warn" | "block";
  message: string;
}

export interface Decision {
  outcome: "pass" | "warn" | "block";
  violations: Violation[];
  summary: string;
  policy_version: string;
  delivery_status: string;
  delivery_error: string | null;
  github_check_url: string | null;
}

export interface ExperimentSnapshot {
  id: string;
  status: ExperimentStatus;
  fixture_mode: boolean;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  suite: { id: string; name: string; digest: string } | null;
  baseline: LaneConfig;
  candidate: LaneConfig;
  policy: Record<string, unknown>;
  budget: Record<string, unknown>;
  git_sha: string | null;
  pull_request_url: string | null;
  tasks: TaskSummary[];
  runs: RunSummary[];
  pairs: Pair[];
  metrics: Metric[];
  comparison: {
    n: number;
    baseline_pass_rate: number;
    candidate_pass_rate: number;
    difference: number;
    difference_interval: [number, number];
    mcnemar_p_value: number;
    conclusion: string;
  } | null;
  decision: Decision | null;
  last_event_seq: number;
}

export interface ReplayEvent {
  schema_version: string;
  event_id: string;
  seq: number;
  experiment_id: string;
  type: string;
  actor_type: string;
  actor_id: string | null;
  occurred_at: string | null;
  payload: Record<string, unknown>;
}

export interface TraceStep {
  sequence: number;
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  error_kind: string | null;
  exit_code: number | null;
  duration_ms: number;
  observation: Record<string, unknown>;
}

export interface RunTrace {
  id: string;
  task_id: string;
  lane: Lane;
  provider: string;
  model: string;
  status: string;
  passed: boolean;
  failure: { kind: string; message: string } | null;
  finish_summary: string | null;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  provider_cost: number | null;
  provider_response_ids: string[];
  steps: TraceStep[];
  grades: { grader: string; version: string; passed: boolean; reason: string; evidence: Record<string, unknown> }[];
}

export interface ModelOption {
  provider: string;
  model: string;
  label?: string;
  owned_by?: string | null;
  nvidia?: boolean;
}

export interface ModelCatalog {
  fixture: ModelOption[];
  baseline: ModelOption[];
  nebius: { configured: boolean; reason?: string; error?: string; fetched_at?: string; models: ModelOption[] };
}
