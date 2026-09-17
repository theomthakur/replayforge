import { lazy, Suspense, useState } from "react";

import type { Lane, TaskSummary } from "../../api/types";
import { hasWebGL } from "../../three/webgl";
import type { LabState } from "../experiments/labState";

const ModelLab = lazy(() => import("../../three/ModelLab"));

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
        {!supported && <p className="body callout">WebGL is not available in this browser. Use the cases table and trace inspector; they show the same data.</p>}
        {supported && enabled && props.state.status === "unknown" && <p className="body hint">Waiting for persisted state…</p>}
        {supported && enabled && props.state.status !== "unknown" && (
          <Suspense fallback={<p className="body hint">Loading the lab…</p>}>
            <ModelLab {...props} />
          </Suspense>
        )}
        {supported && !enabled && <p className="body hint">3D view hidden. The cases table shows the same state.</p>}
        <div className="lab-legend" aria-hidden="true">
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
