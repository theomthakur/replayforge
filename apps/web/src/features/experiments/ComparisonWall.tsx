import type { ExperimentSnapshot } from "../../api/types";
import { formatValue, KIND_LABEL, metric } from "./format";
import type { LabState } from "./labState";

function Stat({ label, name, snapshot }: { label: string; name: string; snapshot: ExperimentSnapshot }) {
  const b = metric(snapshot.metrics, "baseline", name);
  const c = metric(snapshot.metrics, "candidate", name);
  return (
    <div className="stat">
      <div className="k">{label}</div>
      <div className="v" style={{ color: "var(--candidate)" }}>{formatValue(c)}</div>
      <div className="sub"><span style={{ color: "var(--baseline)" }}>baseline {formatValue(b)}</span></div>
      <div className="sub">{c ? `${KIND_LABEL[c.measurement_kind]} · n=${c.sample_count}` : "waiting for results"}</div>
    </div>
  );
}

export function ComparisonWall({ snapshot, state }: { snapshot: ExperimentSnapshot; state: LabState }) {
  const outcome = state.decision ?? snapshot.decision?.outcome ?? null;
  return (
    <section className="panel" aria-labelledby="wall-title">
      <header>
        <h2 id="wall-title">Comparison wall</h2>
        <div className="lanes-line">
          <span className="badge baseline">baseline · {snapshot.baseline.model}</span>
          <span className="badge candidate">candidate · {snapshot.candidate.model}</span>
        </div>
      </header>
      <div className="body stack">
        <div className="wall">
          <Stat label="Pass rate" name="pass_rate" snapshot={snapshot} />
          <Stat label="p95 latency" name="latency_p95_ms" snapshot={snapshot} />
          <Stat label="Cost / success" name="cost_per_success_usd" snapshot={snapshot} />
          <div className="stat" aria-live="polite">
            <div className="k">Release decision</div>
            <div className="v">{outcome ? <span className={`badge ${outcome}`} style={{ fontSize: 16 }}>{outcome.toUpperCase()}</span> : <small>pending</small>}</div>
            <div className="sub">{snapshot.decision?.policy_version ?? "deterministic policy"}</div>
          </div>
        </div>
        {snapshot.decision && (
          <div>
            <p style={{ margin: "0 0 6px" }}>{snapshot.decision.summary}</p>
            {snapshot.decision.violations.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {snapshot.decision.violations.map((v) => <li key={v.rule}><span className={`badge ${v.severity}`}>{v.severity}</span> {v.message}</li>)}
              </ul>
            )}
          </div>
        )}
        {snapshot.comparison && (
          <p className="hint" style={{ margin: 0 }}>
            Paired n={snapshot.comparison.n}, exact McNemar p={snapshot.comparison.mcnemar_p_value.toPrecision(3)}. {snapshot.comparison.conclusion}
          </p>
        )}
      </div>
    </section>
  );
}
