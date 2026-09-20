import type { ExperimentSnapshot, ExperimentStatus, Lane, ReplayEvent } from "../../api/types";

export type CaseStage = "queued" | "provisioning" | "reasoning" | "tool_execution" | "grading" | "passed" | "failed";

export interface CaseState {
  taskId: string;
  lane: Lane;
  stage: CaseStage;
  tool: string | null;
  toolCalls: number;
  toolFailures: number;
  failureMode: string | null;
  latencyMs: number | null;
}

export interface Notification {
  id: string;
  severity: "info" | "success" | "warning" | "error";
  title: string;
  detail: string;
  taskId?: string;
  lane?: Lane;
  seq: number;
}

export interface LabState {
  status: ExperimentStatus | "unknown";
  cases: Record<string, CaseState>;
  critical: Record<string, boolean>;
  pairOutcomes: Record<string, string>;
  investigating: string[];
  findings: Record<string, { category: string; summary: string; method: string }>;
  decision: "pass" | "warn" | "block" | null;
  githubStatus: "idle" | "delivering" | "delivered" | "failed";
  githubUrl: string | null;
  notifications: Notification[];
  lastSeq: number;
}

export const caseKey = (taskId: string, lane: Lane) => `${taskId}:${lane}`;

export function emptyState(): LabState {
  return {
    status: "unknown",
    cases: {},
    critical: {},
    pairOutcomes: {},
    investigating: [],
    findings: {},
    decision: null,
    githubStatus: "idle",
    githubUrl: null,
    notifications: [],
    lastSeq: 0,
  };
}

function blankCase(taskId: string, lane: Lane): CaseState {
  return { taskId, lane, stage: "queued", tool: null, toolCalls: 0, toolFailures: 0, failureMode: null, latencyMs: null };
}

/** Build state from a persisted snapshot. Live events then apply on top from last_event_seq. */
export function hydrate(snapshot: ExperimentSnapshot): LabState {
  const state = emptyState();
  state.status = snapshot.status;
  state.lastSeq = snapshot.last_event_seq;
  for (const task of snapshot.tasks) {
    state.critical[task.id] = task.critical;
    for (const lane of ["baseline", "candidate"] as Lane[]) {
      state.cases[caseKey(task.id, lane)] = blankCase(task.id, lane);
    }
  }
  for (const run of snapshot.runs) {
    state.cases[caseKey(run.task_id, run.lane)] = {
      ...blankCase(run.task_id, run.lane),
      stage: run.passed ? "passed" : "failed",
      failureMode: run.failure_mode,
      latencyMs: run.latency_ms,
    };
  }
  for (const pair of snapshot.pairs) {
    state.pairOutcomes[pair.task_id] = pair.outcome;
    if (pair.investigation) {
      state.findings[pair.task_id] = { category: pair.investigation.category, summary: pair.investigation.summary, method: pair.investigation.method };
    }
  }
  if (snapshot.decision) {
    state.decision = snapshot.decision.outcome;
    state.githubStatus = snapshot.decision.delivery_status === "delivered" ? "delivered" : snapshot.decision.delivery_status === "failed" ? "failed" : "idle";
    state.githubUrl = snapshot.decision.github_check_url;
  }
  return state;
}

const str = (value: unknown): string | undefined => (typeof value === "string" ? value : undefined);

function withCase(state: LabState, event: ReplayEvent, update: (current: CaseState) => CaseState): LabState {
  const taskId = str(event.payload.task_id);
  const lane = str(event.payload.lane) as Lane | undefined;
  if (!taskId || (lane !== "baseline" && lane !== "candidate")) return state;
  const key = caseKey(taskId, lane);
  const current = state.cases[key] ?? blankCase(taskId, lane);
  return { ...state, cases: { ...state.cases, [key]: update(current) } };
}

function notify(state: LabState, event: ReplayEvent, note: Omit<Notification, "id" | "seq">): LabState {
  if (state.notifications.some((n) => n.id === event.event_id)) return state;
  return { ...state, notifications: [{ ...note, id: event.event_id, seq: event.seq }, ...state.notifications].slice(0, 50) };
}

/** Pure reducer: every visual change in the lab must come from one of these persisted events. */
export function applyEvent(state: LabState, event: ReplayEvent): LabState {
  if (event.seq <= state.lastSeq) return state;
  let next: LabState = { ...state, lastSeq: event.seq };
  const payload = event.payload;
  switch (event.type) {
    case "experiment.started":
    case "experiment.resumed":
      next.status = "running";
      next = notify(next, event, { severity: "info", title: event.type === "experiment.resumed" ? "Mission resumed" : "Autonomous mission started", detail: "Both coding-agent lanes are now running under the stored limits." });
      break;
    case "case.queued": {
      const taskId = str(payload.task_id);
      if (taskId) next.critical = { ...next.critical, [taskId]: Boolean(payload.critical) };
      next = withCase(next, event, (c) => (c.stage === "passed" || c.stage === "failed" ? c : { ...c, stage: "queued" }));
      break;
    }
    case "case.started":
      next = withCase(next, event, (c) => ({ ...c, stage: "provisioning" }));
      break;
    case "agent.thinking":
      next = withCase(next, event, (c) => ({ ...c, stage: "reasoning", tool: null }));
      break;
    case "tool.started":
      next = withCase(next, event, (c) => ({ ...c, stage: "tool_execution", tool: str(payload.tool) ?? null }));
      break;
    case "tool.completed":
      next = withCase(next, event, (c) => ({ ...c, toolCalls: c.toolCalls + 1 }));
      break;
    case "tool.failed":
      next = withCase(next, event, (c) => ({ ...c, toolCalls: c.toolCalls + 1, toolFailures: c.toolFailures + 1 }));
      break;
    case "case.grading":
      next = withCase(next, event, (c) => ({ ...c, stage: "grading", tool: null }));
      break;
    case "case.completed":
    case "case.failed":
      next = withCase(next, event, (c) => ({
        ...c,
        stage: payload.passed ? "passed" : "failed",
        tool: null,
        failureMode: str(payload.failure_mode) ?? null,
        latencyMs: typeof payload.latency_ms === "number" ? payload.latency_ms : c.latencyMs,
      }));
      if (payload.failure_mode === "provider_error") {
        next = notify(next, event, { severity: "error", title: "Provider call failed", detail: `${payload.lane} lane on ${payload.task_id}`, taskId: str(payload.task_id), lane: payload.lane as Lane });
      }
      break;
    case "pair.comparable": {
      const taskId = str(payload.task_id);
      if (taskId) next.pairOutcomes = { ...next.pairOutcomes, [taskId]: String(payload.outcome) };
      if (next.status === "running") next.status = "investigating";
      break;
    }
    case "investigation.started": {
      const taskId = str(payload.task_id);
      if (taskId && !next.investigating.includes(taskId)) next.investigating = [...next.investigating, taskId];
      if (taskId) next = notify(next, event, { severity: "warning", title: "Regression investigation started", detail: `${taskId}: reconciling paired evidence`, taskId, lane: "candidate" });
      break;
    }
    case "investigation.completed": {
      const taskId = str(payload.task_id);
      if (taskId) {
        next.investigating = next.investigating.filter((t) => t !== taskId);
        next.findings = { ...next.findings, [taskId]: { category: String(payload.category), summary: String(payload.summary ?? ""), method: String(payload.method ?? "rule") } };
        if (next.critical[taskId] && next.pairOutcomes[taskId] === "candidate_regressed") {
          next = notify(next, event, { severity: "error", title: "Critical regression found", detail: `${taskId}: ${payload.category}`, taskId, lane: "candidate" });
        }
      }
      break;
    }
    case "policy.evaluated":
      next.status = "deciding";
      next.decision = payload.outcome as LabState["decision"];
      next = notify(next, event, { severity: payload.outcome === "pass" ? "success" : "warning", title: "Release policy evaluated", detail: `${String(payload.outcome).toUpperCase()} is now backed by stored evidence.` });
      break;
    case "experiment.completed":
      next.status = "completed";
      next = notify(next, event, { severity: payload.outcome === "block" ? "warning" : "success", title: "Experiment complete", detail: `Decision: ${String(payload.outcome).toUpperCase()}` });
      break;
    case "experiment.failed":
      next.status = "failed";
      next = notify(next, event, { severity: "error", title: "Experiment failed", detail: String(payload.error ?? "") });
      break;
    case "experiment.cancelled":
      next.status = "cancelled";
      next = notify(next, event, { severity: "warning", title: "Experiment cancelled", detail: "Completed evidence remains available for inspection." });
      break;
    case "github.delivery.started":
      next.githubStatus = "delivering";
      break;
    case "github.delivery.completed":
      next.githubStatus = "delivered";
      next.githubUrl = str(payload.check_url) ?? null;
      next = notify(next, event, { severity: "success", title: "GitHub check published", detail: next.githubUrl ?? "" });
      break;
    case "github.delivery.failed":
      next.githubStatus = "failed";
      next = notify(next, event, { severity: "error", title: "GitHub publication failed", detail: String(payload.error ?? "") });
      break;
    default:
      break;
  }
  return next;
}
