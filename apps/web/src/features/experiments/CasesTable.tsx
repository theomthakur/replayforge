import type { ExperimentSnapshot, Lane } from "../../api/types";
import { OUTCOME_LABEL } from "./format";
import { caseKey, type CaseStage, type LabState } from "./labState";

const STAGE_TEXT: Record<CaseStage, string> = {
  queued: "queued", provisioning: "sandbox", reasoning: "thinking", tool_execution: "tool", grading: "grading", passed: "pass", failed: "fail",
};

function Stage({ state, taskId, lane }: { state: LabState; taskId: string; lane: Lane }) {
  const c = state.cases[caseKey(taskId, lane)];
  if (!c) return <span className="badge">—</span>;
  const cls = c.stage === "passed" ? "passed" : c.stage === "failed" ? "failed" : "";
  return (
    <span className={`badge ${cls}`} title={c.failureMode ?? undefined}>
      {STAGE_TEXT[c.stage]}{c.stage === "tool_execution" && c.tool ? `: ${c.tool}` : ""}{c.failureMode ? ` (${c.failureMode})` : ""}
    </span>
  );
}

export function CasesTable({ snapshot, state, selected, onSelect }: {
  snapshot: ExperimentSnapshot; state: LabState; selected: string | null; onSelect: (taskId: string) => void;
}) {
  return (
    <section className="panel" aria-labelledby="cases-title">
      <header><h2 id="cases-title">Cases</h2><span className="hint">{snapshot.tasks.length} tasks · select one to inspect</span></header>
      <div className="cases-wrap">
        <table className="cases">
          <thead>
            <tr><th scope="col">Task</th><th scope="col">Baseline</th><th scope="col">Candidate</th><th scope="col">Pair</th><th scope="col">Finding (hypothesis)</th></tr>
          </thead>
          <tbody>
            {snapshot.tasks.map((task) => {
              const finding = state.findings[task.id];
              const outcome = state.pairOutcomes[task.id];
              return (
                <tr key={task.id} className={selected === task.id ? "selected" : ""} aria-selected={selected === task.id}>
                  <td>
                    <button className="rowbtn" onClick={() => onSelect(task.id)} aria-label={`Inspect ${task.id}`}>{task.id}</button>
                    {task.critical && <> <span className="badge warn">critical</span></>}
                    <div className="hint">{task.category}</div>
                  </td>
                  <td><Stage state={state} taskId={task.id} lane="baseline" /></td>
                  <td><Stage state={state} taskId={task.id} lane="candidate" /></td>
                  <td>{outcome ? <span className={`badge ${outcome === "candidate_regressed" ? "failed" : outcome === "both_pass" ? "passed" : ""}`}>{OUTCOME_LABEL[outcome]}</span> : <span className="hint">…</span>}</td>
                  <td>{state.investigating.includes(task.id) ? <span className="hint">investigating…</span> : finding ? <><span className="badge">{finding.category}</span> <span className="hint">{finding.method}</span></> : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
