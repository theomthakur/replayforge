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

const TABS = ["Overview", "Cases", "Trace", "Timeline", "Lab"] as const;
type Tab = (typeof TABS)[number];

export function ExperimentPage({ experimentId }: { experimentId: string }) {
  const { snapshot, state, events, connected } = useExperiment(experimentId);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [lane, setLane] = useState<Lane>("candidate");
  const [tab, setTab] = useState<Tab>("Overview");
  const [prUrl, setPrUrl] = useState("");
  const queryClient = useQueryClient();
  const cancel = useMutation({ mutationFn: () => api.cancel(experimentId) });
  const publish = useMutation({
    mutationFn: () => api.publish(experimentId, prUrl || undefined),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["experiment", experimentId] }),
  });

  if (snapshot.isLoading) return <p>Loading experiment…</p>;
  if (snapshot.error || !snapshot.data) return <p className="error-text">Could not load this experiment: {(snapshot.error as Error)?.message}</p>;
  const data = snapshot.data;
  const select = (taskId: string, l?: Lane) => { setSelectedTask(taskId); if (l) setLane(l); setTab("Trace"); };
  const running = ["running", "investigating", "deciding"].includes(state.status);
  const firstRegression = data.pairs.find((p) => p.outcome === "candidate_regressed")?.task_id;

  return (
    <div className="stack">
      <div className="row" style={{ alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22 }}>{data.suite?.name ?? "Experiment"}</h1>
          <div className="row hint" style={{ gap: 8, alignItems: "center" }}>
            <span className={`badge ${state.status === "failed" ? "failed" : state.status === "completed" ? "passed" : ""}`}>{state.status}</span>
            {data.fixture_mode && <span className="badge fixture">fixture mode · not model results</span>}
            <span className="mono">{data.suite?.digest.slice(0, 23)}…</span>
            <span>started {data.started_at ? new Date(data.started_at).toLocaleTimeString() : "—"}</span>
          </div>
        </div>
        <div className="row" style={{ gap: 8, alignItems: "center" }}>
          <NotificationCenter notifications={state.notifications} onOpen={select} />
          <a className="btn" href={`/api/experiments/${experimentId}/report.md`} target="_blank" rel="noreferrer" aria-disabled={!data.decision}>Report</a>
          {running && <button className="btn danger" onClick={() => cancel.mutate()} disabled={cancel.isPending}>Cancel</button>}
        </div>
      </div>
      {data.error && <p className="callout error-text">Experiment error: {data.error}</p>}

      <nav className="tabs" role="tablist" aria-label="Sections">
        {TABS.map((t) => <button key={t} role="tab" className="btn" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}
      </nav>

      <div className="lab-layout">
        <div className="stack">
          <div data-tab-panel hidden={tab !== "Lab" && window.innerWidth <= 760}>
            <LabPanel tasks={data.tasks} state={state} selectedTask={selectedTask} selectedLane={lane} onSelect={select} />
          </div>
          <div data-tab-panel hidden={tab !== "Cases" && window.innerWidth <= 760}>
            <CasesTable snapshot={data} state={state} selected={selectedTask} onSelect={(id) => select(id)} />
          </div>
        </div>
        <div className="stack">
          <div data-tab-panel hidden={tab !== "Overview" && window.innerWidth <= 760}>
            <ComparisonWall snapshot={data} state={state} />
            {data.decision && (
              <section className="panel" aria-labelledby="gh-title" style={{ marginTop: 16 }}>
                <header><h2 id="gh-title">GitHub release gate</h2><span className={`badge ${state.githubStatus === "delivered" ? "passed" : state.githubStatus === "failed" ? "failed" : ""}`}>{state.githubStatus}</span></header>
                <div className="body row" style={{ alignItems: "flex-end" }}>
                  <div className="field" style={{ flex: "1 1 260px", marginBottom: 0 }}>
                    <label htmlFor="gh-pr">Pull request URL</label>
                    <input id="gh-pr" placeholder={data.pull_request_url ?? "https://github.com/owner/repo/pull/1"} value={prUrl} onChange={(e) => setPrUrl(e.target.value)} />
                  </div>
                  <button className="btn primary" onClick={() => publish.mutate()} disabled={publish.isPending}>Publish check</button>
                  {state.githubUrl && <a href={state.githubUrl} target="_blank" rel="noreferrer">Open check</a>}
                  {(publish.error || data.decision.delivery_error) && <p className="error-text" style={{ flexBasis: "100%", margin: 0 }}>{(publish.error as Error)?.message ?? data.decision.delivery_error}</p>}
                </div>
              </section>
            )}
          </div>
          <div data-tab-panel hidden={tab !== "Trace" && window.innerWidth <= 760}>
            <TracePanel snapshot={data} taskId={selectedTask ?? firstRegression ?? null} lane={lane} onLane={setLane} />
          </div>
        </div>
      </div>
      <div data-tab-panel hidden={tab !== "Timeline" && window.innerWidth <= 760}>
        <Timeline events={events} connected={connected} />
      </div>
    </div>
  );
}
