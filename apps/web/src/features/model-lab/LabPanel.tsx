import { lazy, Suspense, useState } from "react";

import type { Lane, TaskSummary } from "../../api/types";
import { hasWebGL } from "../../three/webgl";
import type { LabState } from "../experiments/labState";

const ModelLab = lazy(() => import("../../three/ModelLab"));

function TwoDimensionalFloor({ state }: { state: LabState }) {
  const cases = Object.values(state.cases);
  const active = (lane: Lane) => cases.filter((item) => item.lane === lane && !["queued", "passed", "failed"].includes(item.stage)).length;
  const done = cases.filter((item) => ["passed", "failed"].includes(item.stage)).length;
  const stations = [
    { name: "Baseline agent", detail: `${active("baseline")} active work packets`, tone: "baseline" },
    { name: "NVIDIA agent", detail: `${active("candidate")} active work packets`, tone: "candidate" },
    { name: "Evidence pipeline", detail: `${done}/${cases.length} lane executions stored`, tone: "evidence" },
    { name: "Investigator", detail: `${state.investigating.length} cases under review`, tone: "investigator" },
    { name: "Release guardian", detail: state.decision ? `${state.decision.toUpperCase()} recorded` : "waiting for paired evidence", tone: "guardian" },
  ];
  return <div className="fallback-floor">
    <div className="fallback-floor-heading"><span className="eyebrow">Accessible operations map</span><h3>Live state without the 3D scene</h3><p>This is the same persisted workflow, presented as a compact control-room map.</p></div>
    <div className="fallback-stations">{stations.map((station, index) => <article className={station.tone} key={station.name}><span>{String(index + 1).padStart(2, "0")}</span><i /><div><strong>{station.name}</strong><small>{station.detail}</small></div></article>)}</div>
  </div>;
}

export function LabPanel(props: { tasks: TaskSummary[]; state: LabState; selectedTask: string | null; selectedLane: Lane; onSelect: (id: string, lane: Lane) => void }) {
  const [supported] = useState(hasWebGL);
  const [enabled, setEnabled] = useState(supported);
  return (
    <section className="panel" aria-labelledby="lab-title">
      <header>
        <h2 id="lab-title">Reliability operations floor</h2>
        <button className="btn" onClick={() => setEnabled(!enabled)} disabled={!supported} aria-pressed={enabled}>
          {enabled ? "Hide 3D" : "Show 3D"}
        </button>
      </header>
      <div className="lab-canvas" aria-describedby="lab-desc">
        <p id="lab-desc" className="visually-hidden">
          A 3D operations floor driven by the same persisted state shown in the cases table. Each work packet is one case on one lane and moves only when the backend records an event. Every detail is also available in the table and trace inspector.
        </p>
        {!supported && <TwoDimensionalFloor state={props.state} />}
        {supported && enabled && props.state.status === "unknown" && <p className="body hint">Waiting for persisted state…</p>}
        {supported && enabled && props.state.status !== "unknown" && (
          <Suspense fallback={<p className="body hint">Loading the lab…</p>}>
            <ModelLab {...props} />
          </Suspense>
        )}
        {supported && !enabled && <TwoDimensionalFloor state={props.state} />}
        <div className="lab-legend" aria-hidden="true">
          <span className="badge">avatars visualize software roles</span>
          <span className="badge baseline">baseline lane</span>
          <span className="badge candidate">candidate lane</span>
          <span className="badge">grey: queued</span>
          <span className="badge passed">pass</span>
          <span className="badge failed">fail</span>
          <span className="badge warn">amber marker: critical</span>
        </div>
      </div>
    </section>
  );
}
