import type { ExperimentSnapshot, Metric } from "../../api/types";
import { formatValue, KIND_LABEL, metric } from "./format";
import type { LabState } from "./labState";

const METRICS = [
  { label: "Pass rate", name: "pass_rate", better: "higher" },
  { label: "p95 latency", name: "latency_p95_ms", better: "lower" },
  { label: "Cost / success", name: "cost_per_success_usd", better: "lower" },
] as const;

function delta(baseline?: Metric, candidate?: Metric, better = "higher") {
  if (baseline?.value == null || candidate?.value == null) return { text: "not comparable", tone: "unknown" };
  const change = candidate.value - baseline.value;
  const improved = better === "higher" ? change > 0 : change < 0;
  const same = Math.abs(change) < 0.000001;
  const sign = change > 0 ? "+" : "";
  return { text: `${sign}${change.toFixed(Math.abs(change) < 1 ? 3 : 1)} ${candidate.unit}`, tone: same ? "same" : improved ? "better" : "worse" };
}

export function ComparisonWall({ snapshot, state }: { snapshot: ExperimentSnapshot; state: LabState }) {
  const outcome = state.decision ?? snapshot.decision?.outcome ?? null;
  return (
    <section className="panel comparison-wall" aria-labelledby="wall-title">
      <header><div><h2 id="wall-title">Model comparison</h2><small>Same tasks, independent sandboxes, paired evidence</small></div><span className={`comparison-decision ${outcome ?? "pending"}`}>{outcome?.toUpperCase() ?? "EVALUATING"}</span></header>
      <div className="comparison-lanes">
        <div><i className="baseline" /><span><small>Current baseline</small><strong>{snapshot.baseline.model}</strong></span></div>
        <b>versus</b>
        <div><i className="candidate" /><span><small>NVIDIA candidate</small><strong>{snapshot.candidate.model}</strong></span></div>
      </div>
      <div className="comparison-table" role="table" aria-label="Paired model metrics">
        <div className="comparison-row comparison-head" role="row"><span>Measure</span><span>Baseline</span><span>Candidate</span><span>Change</span></div>
        {METRICS.map((item) => {
          const baseline = metric(snapshot.metrics, "baseline", item.name);
          const candidate = metric(snapshot.metrics, "candidate", item.name);
          const change = delta(baseline, candidate, item.better);
          return <div className="comparison-row" role="row" key={item.name}>
            <span><strong>{item.label}</strong><small>{candidate ? `${KIND_LABEL[candidate.measurement_kind]} · n=${candidate.sample_count}` : "waiting for evidence"}</small></span>
            <span>{formatValue(baseline)}</span><span>{formatValue(candidate)}</span><span className={`metric-delta ${change.tone}`}>{change.text}</span>
          </div>;
        })}
      </div>
      <div className="comparison-conclusion">
        <span className="eyebrow">Release interpretation</span>
        <p>{snapshot.decision?.summary ?? "The release guardian will summarize the paired evidence after grading and investigation finish."}</p>
        {snapshot.decision?.violations.length ? <ul>{snapshot.decision.violations.map((violation) => <li key={violation.rule}><span className={`badge ${violation.severity}`}>{violation.severity}</span><span>{violation.message}</span></li>)}</ul> : null}
        {snapshot.comparison && <small>Paired n={snapshot.comparison.n} · exact McNemar p={snapshot.comparison.mcnemar_p_value.toPrecision(3)} · {snapshot.comparison.conclusion}</small>}
      </div>
    </section>
  );
}
