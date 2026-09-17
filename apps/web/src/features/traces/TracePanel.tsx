import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../api/client";
import type { ExperimentSnapshot, Lane } from "../../api/types";

export function TracePanel({ snapshot, taskId, lane, onLane }: {
  snapshot: ExperimentSnapshot; taskId: string | null; lane: Lane; onLane: (lane: Lane) => void;
}) {
  const run = snapshot.runs.find((r) => r.task_id === taskId && r.lane === lane);
  const pair = snapshot.pairs.find((p) => p.task_id === taskId);
  const trace = useQuery({ queryKey: ["trace", run?.id], queryFn: () => api.trace(run!.id), enabled: Boolean(run?.id) });
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section className="panel" aria-labelledby="trace-title">
      <header>
        <h2 id="trace-title">Trace inspector</h2>
        <div role="tablist" aria-label="Lane" className="row" style={{ gap: 6 }}>
          {(["baseline", "candidate"] as Lane[]).map((l) => (
            <button key={l} role="tab" aria-selected={lane === l} className={`btn`} style={lane === l ? { borderColor: `var(--${l})`, color: `var(--${l})` } : undefined} onClick={() => onLane(l)}>{l}</button>
          ))}
        </div>
      </header>
      <div className="body stack">
        {!taskId && <p className="hint">Select a case from the table or the Model Lab.</p>}
        {taskId && !run && <p className="hint">{taskId} has not finished on the {lane} lane yet.</p>}
        {pair?.investigation && (
          <div className="callout">
            <strong>Investigation hypothesis ({pair.investigation.method}, confidence {Math.round(pair.investigation.confidence * 100)}%):</strong>{" "}
            <span className="badge">{pair.investigation.category}</span> {pair.investigation.summary}
            <div className="hint mono">evidence: {pair.investigation.evidence_refs.join(", ")}</div>
            <div className="hint">An interpretation of the evidence, not a verified fact.</div>
          </div>
        )}
        {trace.data && (
          <>
            <div className="row" style={{ gap: 8, alignItems: "center" }}>
              <span className={`badge ${trace.data.passed ? "passed" : "failed"}`}>{trace.data.passed ? "pass" : "fail"}</span>
              <span className="mono hint">{trace.data.provider}:{trace.data.model}</span>
              <span className="hint">{(trace.data.latency_ms / 1000).toFixed(2)} s · {trace.data.steps.length} tool calls</span>
              <span className="hint">tokens {trace.data.input_tokens || "?"} in / {trace.data.output_tokens || "?"} out · cost {trace.data.provider_cost === null ? "unknown" : `$${trace.data.provider_cost.toFixed(5)}`}</span>
            </div>
            {trace.data.failure && <p className="error-text" style={{ margin: 0 }}>Failure ({trace.data.failure.kind}): {trace.data.failure.message}</p>}
            {trace.data.provider_response_ids.length > 0 && <p className="hint mono" style={{ margin: 0 }}>provider request ids: {trace.data.provider_response_ids.slice(0, 4).join(", ")}</p>}

            <div>
              <h3 style={{ margin: "0 0 6px", fontSize: 13 }}>Deterministic graders</h3>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {trace.data.grades.map((g) => <li key={g.grader}><span className={`badge ${g.passed ? "passed" : "failed"}`}>{g.passed ? "pass" : "fail"}</span> <strong>{g.grader}</strong> {g.reason}</li>)}
              </ul>
            </div>

            <div className="steps">
              {trace.data.steps.map((s) => (
                <div key={s.sequence} className={`step ${s.ok ? "" : "bad"}`} id={`step-${s.sequence}`}>
                  <header>
                    <span className="mono">step:{s.sequence} · <strong>{s.tool}</strong>{s.exit_code !== null ? ` · exit ${s.exit_code}` : ""}</span>
                    <span>{s.error_kind && <span className="badge failed">{s.error_kind}</span>}{" "}
                      <button className="btn" aria-expanded={open === s.sequence} onClick={() => setOpen(open === s.sequence ? null : s.sequence)}>{open === s.sequence ? "hide" : "details"}</button>
                    </span>
                  </header>
                  <pre>{JSON.stringify(s.arguments, null, 1).slice(0, 400)}</pre>
                  {open === s.sequence && <pre>{JSON.stringify(s.observation, null, 1)}</pre>}
                </div>
              ))}
            </div>
            {trace.data.finish_summary && <p className="hint">finish: {trace.data.finish_summary}</p>}
          </>
        )}
      </div>
    </section>
  );
}
