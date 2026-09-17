import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../api/client";
import type { Lane } from "../../api/types";
import { LabPanel } from "../model-lab/LabPanel";
import { NotificationCenter } from "../notifications/NotificationCenter";
import { Timeline } from "../timeline/Timeline";
import { TracePanel } from "../traces/TracePanel";
import { CasesTable } from "./CasesTable";
import { ComparisonWall } from "./ComparisonWall";
import { useExperiment } from "./useExperiment";

const TABS = ["Cases", "Trace", "Timeline", "Release"] as const;
type Tab = (typeof TABS)[number];
type JourneyState = "done" | "active" | "waiting" | "attention";

function Journey({ status, completedRuns, totalRuns, pairCount, investigating, decision, githubStatus }: {
  status: string; completedRuns: number; totalRuns: number; pairCount: number;
  investigating: number; decision: string | null; githubStatus: string;
}) {
  const failed = status === "failed" || status === "cancelled";
  const runningDone = totalRuns > 0 && completedRuns >= totalRuns;
  const steps: { label: string; detail: string; state: JourneyState }[] = [
    { label: "Experiment ready", detail: "Suite and policy locked", state: "done" },
    { label: "Paired agents", detail: `${completedRuns}/${totalRuns} runs`, state: failed ? "attention" : runningDone ? "done" : status === "running" ? "active" : "waiting" },
    { label: "Deterministic tests", detail: `${pairCount} pairs compared`, state: decision ? "done" : runningDone ? "active" : "waiting" },
    { label: "Investigation", detail: investigating ? `${investigating} under review` : pairCount ? "Evidence reconciled" : "Waiting for evidence", state: decision ? "done" : investigating ? "active" : pairCount ? "done" : "waiting" },
    { label: "Release decision", detail: decision ? decision.toUpperCase() : "Policy pending", state: decision ? (decision === "block" ? "attention" : "done") : status === "deciding" ? "active" : "waiting" },
    { label: "GitHub check", detail: githubStatus === "delivered" ? "Published" : githubStatus === "delivering" ? "Publishing" : "Optional handoff", state: githubStatus === "delivered" ? "done" : githubStatus === "delivering" ? "active" : githubStatus === "failed" ? "attention" : "waiting" },
  ];
  return (
    <section className="journey" aria-label="Experiment journey">
      <div className="journey-heading"><span className="eyebrow">Live workflow</span><strong>From replay to release evidence</strong></div>
      <ol>{steps.map((step, index) => (
        <li key={step.label} className={step.state}>
          <span className="journey-index">{step.state === "done" ? "✓" : index + 1}</span>
          <span><strong>{step.label}</strong><small>{step.detail}</small></span>
        </li>
      ))}</ol>
    </section>
  );
}

function OperationsBrief({ baseline, candidate, completedRuns, totalRuns, state }: {
  baseline: string; candidate: string; completedRuns: number; totalRuns: number;
  state: ReturnType<typeof useExperiment>["state"];
}) {
  const active = Object.values(state.cases).filter((item) => !["queued", "passed", "failed"].includes(item.stage));
  return (
    <section className="panel operations-brief" aria-labelledby="brief-title">
      <header><h2 id="brief-title">Operations brief</h2><span className="live-indicator"><i /> persisted state</span></header>
      <div className="body">
        <div className="lane-card baseline-card"><span>Baseline lane</span><strong>{baseline}</strong></div>
        <div className="lane-card candidate-card"><span>NVIDIA candidate</span><strong>{candidate}</strong></div>
        <div className="run-progress" aria-label={`${completedRuns} of ${totalRuns} runs complete`}>
          <div><span>Run completion</span><strong>{completedRuns}/{totalRuns}</strong></div>
          <progress value={completedRuns} max={Math.max(totalRuns, 1)} />
        </div>
        <div className="active-work">
          <span className="eyebrow">Now on the floor</span>
          {active.length ? active.slice(0, 4).map((item) => (
            <div className="active-item" key={`${item.taskId}-${item.lane}`}>
              <i className={item.lane} />
              <span><strong>{item.taskId}</strong><small>{item.lane} · {item.tool ?? item.stage.replace("_", " ")}</small></span>
            </div>
          )) : <p className="quiet">No active workers. The saved result remains fully inspectable.</p>}
        </div>
      </div>
    </section>
  );
}

export function ExperimentPage({ experimentId }: { experimentId: string }) {
  const { snapshot, state, events, connected } = useExperiment(experimentId);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [lane, setLane] = useState<Lane>("candidate");
  const [tab, setTab] = useState<Tab>("Cases");
  const [prUrl, setPrUrl] = useState("");
  const queryClient = useQueryClient();
  const cancel = useMutation({ mutationFn: () => api.cancel(experimentId) });
  const publish = useMutation({ mutationFn: () => api.publish(experimentId, prUrl || undefined), onSettled: () => queryClient.invalidateQueries({ queryKey: ["experiment", experimentId] }) });

  if (snapshot.isLoading) return <div className="loading-state"><span /> Loading the reliability floor…</div>;
  if (snapshot.error || !snapshot.data) return <p className="error-text">Could not load this experiment: {(snapshot.error as Error)?.message}</p>;
  const data = snapshot.data;
  const select = (taskId: string, selectedLane?: Lane) => { setSelectedTask(taskId); if (selectedLane) setLane(selectedLane); setTab("Trace"); };
  const running = ["running", "investigating", "deciding"].includes(state.status);
  const firstRegression = data.pairs.find((pair) => pair.outcome === "candidate_regressed")?.task_id;
  const totalRuns = data.tasks.length * 2;
  const completedRuns = Object.values(state.cases).filter((item) => item.stage === "passed" || item.stage === "failed").length;
  const statusLabel = state.status === "completed" && state.decision ? state.decision : state.status;
  const duration = data.started_at
    ? `${Math.max(0, Math.round(((data.completed_at ? new Date(data.completed_at).getTime() : Date.now()) - new Date(data.started_at).getTime()) / 1000))}s elapsed`
    : "not started";

  return (
    <div className="experiment-shell">
      <header className="experiment-hero">
        <div>
          <span className="eyebrow">Reliability operation · {data.fixture_mode ? "simulation" : "live models"}</span>
          <h1>{data.suite?.name ?? "Migration experiment"}</h1>
          <div className="experiment-meta">
            <span className={`status-pill ${statusLabel}`}>{statusLabel}</span><span>{duration}</span><span>{data.tasks.length} paired cases</span>{data.git_sha && <span className="mono">source {data.git_sha.slice(0, 8)}</span>}<span className="mono">suite {data.suite?.digest.slice(7, 17)}…</span>
          </div>
        </div>
        <div className="hero-actions">
          <NotificationCenter notifications={state.notifications} onOpen={select} />
          <a className={`btn ${data.decision ? "" : "disabled"}`} href={data.decision ? `/api/experiments/${experimentId}/report.md` : undefined} target="_blank" rel="noreferrer">Export report</a>
          {running && <button className="btn danger" onClick={() => cancel.mutate()} disabled={cancel.isPending}>Stop run</button>}
        </div>
      </header>

      {data.fixture_mode && <div className="simulation-banner"><strong>Simulation mode</strong><span>Scripted fixture providers are driving this saved rehearsal. These are not model results.</span></div>}
      {data.error && <p className="callout error-text">Experiment error: {data.error}</p>}

      <Journey status={state.status} completedRuns={completedRuns} totalRuns={totalRuns} pairCount={data.pairs.length} investigating={state.investigating.length} decision={state.decision} githubStatus={state.githubStatus} />

      <div className="command-grid">
        <LabPanel tasks={data.tasks} state={state} selectedTask={selectedTask} selectedLane={lane} onSelect={select} />
        <div className="stack">
          <OperationsBrief baseline={data.baseline.model} candidate={data.candidate.model} completedRuns={completedRuns} totalRuns={totalRuns} state={state} />
          <ComparisonWall snapshot={data} state={state} />
        </div>
      </div>

      <section className="details-deck">
        <nav className="tabs" role="tablist" aria-label="Experiment evidence">
          {TABS.map((item) => <button key={item} role="tab" className="tab-button" aria-selected={tab === item} onClick={() => setTab(item)}>{item}</button>)}
        </nav>
        <div className="tab-content">
          {tab === "Cases" && <CasesTable snapshot={data} state={state} selected={selectedTask} onSelect={(id) => select(id)} />}
          {tab === "Trace" && <TracePanel snapshot={data} taskId={selectedTask ?? firstRegression ?? data.tasks[0]?.id ?? null} lane={lane} onLane={setLane} />}
          {tab === "Timeline" && <Timeline events={events} connected={connected} />}
          {tab === "Release" && (
            <section className="release-panel" aria-labelledby="release-title">
              <div><span className="eyebrow">Final handoff</span><h2 id="release-title">Publish the stored decision to GitHub</h2><p>The check uses saved metrics, policy violations, and report evidence. Retrying updates the existing check.</p></div>
              <div className="release-form">
                <label htmlFor="gh-pr">Pull request URL</label>
                <input id="gh-pr" placeholder={data.pull_request_url ?? "https://github.com/owner/repo/pull/1"} value={prUrl} onChange={(event) => setPrUrl(event.target.value)} />
                <button className="btn primary" onClick={() => publish.mutate()} disabled={publish.isPending || !data.decision}>{publish.isPending ? "Publishing…" : "Publish release check"}</button>
                <span className={`status-pill ${state.githubStatus}`}>{state.githubStatus}</span>
                {state.githubUrl && <a href={state.githubUrl} target="_blank" rel="noreferrer">Open published check</a>}
                {(publish.error || data.decision?.delivery_error) && <p className="error-text">{(publish.error as Error)?.message ?? data.decision?.delivery_error}</p>}
              </div>
            </section>
          )}
        </div>
      </section>
    </div>
  );
}
