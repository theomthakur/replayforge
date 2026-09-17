import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { navigate } from "../../app/App";
import { api } from "../../api/client";
import type { ModelOption } from "../../api/types";

const optionKey = (o: ModelOption) => `${o.provider}|${o.model}`;

function ModelSelect({ id, label, value, onChange, groups }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  groups: { label: string; options: ModelOption[] }[];
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {groups.filter((g) => g.options.length).map((group) => (
          <optgroup key={group.label} label={group.label}>
            {group.options.map((o) => (
              <option key={optionKey(o)} value={optionKey(o)}>{o.label ?? o.model}{o.nvidia ? " (NVIDIA)" : ""}</option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

export function SetupPage() {
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const suites = useQuery({ queryKey: ["suites"], queryFn: api.suites });
  const history = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const [suiteFile, setSuiteFile] = useState("demo-suite.yaml");
  const suiteRow = useQuery({ queryKey: ["suite", suiteFile], queryFn: () => api.createSuite(suiteFile) });
  const suiteDef = useQuery({ queryKey: ["suite-def", suiteRow.data?.id], queryFn: () => api.suite(suiteRow.data!.id), enabled: Boolean(suiteRow.data?.id) });
  const [baseline, setBaseline] = useState("fixture|fixture/reference");
  const [candidate, setCandidate] = useState("fixture|fixture/variant");
  const [selected, setSelected] = useState<string[]>([]);
  const [prUrl, setPrUrl] = useState("");
  const [policy, setPolicy] = useState({ max_pass_rate_drop: 0.02, critical_tasks_must_pass: true, max_p95_latency_ms: 15000, require_lower_cost_per_success: false, max_provider_error_rate: 0.02 });
  const [estimate, setEstimate] = useState<Record<string, number | boolean | string> | null>(null);
  const [confirmOver, setConfirmOver] = useState(false);

  const nebius = models.data?.nebius;
  const groups = useMemo(() => [
    { label: "NVIDIA models on Nebius Token Factory (live catalog)", options: (nebius?.models ?? []).filter((m) => m.nvidia) },
    { label: "Other Token Factory models", options: (nebius?.models ?? []).filter((m) => !m.nvidia) },
    { label: "Configured baseline", options: models.data?.baseline ?? [] },
    { label: "Fixture (scripted, not a model)", options: models.data?.fixture ?? [] },
  ], [models.data, nebius]);

  useEffect(() => {
    const firstNvidia = nebius?.models.find((m) => m.nvidia);
    if (firstNvidia) setCandidate(optionKey(firstNvidia));
  }, [nebius]);

  const tasks = suiteDef.data?.definition.tasks ?? [];
  const lane = (key: string) => { const [provider, ...rest] = key.split("|"); return { provider, model: rest.join("|") }; };
  const body = () => ({
    suite_id: suiteRow.data?.id, baseline: lane(baseline), candidate: lane(candidate), policy,
    task_ids: selected, pull_request_url: prUrl || null, confirm_budget: confirmOver,
  });
  const fixtureMode = baseline.startsWith("fixture|") || candidate.startsWith("fixture|");

  const runEstimate = useMutation({ mutationFn: () => api.estimate(body()), onSuccess: setEstimate });
  const launch = useMutation({
    mutationFn: async () => {
      const created = await api.createExperiment(body(), crypto.randomUUID());
      await api.start(created.id);
      return created;
    },
    onSuccess: (created) => navigate(`/experiments/${created.id}`),
  });

  const numberField = (key: keyof typeof policy, label: string, hint: string, step = 0.01) => (
    <div className="field">
      <label htmlFor={`p-${key}`}>{label}</label>
      <input id={`p-${key}`} type="number" step={step} min={0} value={Number(policy[key])}
        onChange={(e) => setPolicy({ ...policy, [key]: Number(e.target.value) })} />
      <span className="hint">{hint}</span>
    </div>
  );

  return (
    <div className="grid-setup">
      <section className="panel" aria-labelledby="setup-title">
        <header><h2 id="setup-title">New migration experiment</h2></header>
        <div className="body">
          <div className="field">
            <label htmlFor="suite">Cassette suite</label>
            <select id="suite" value={suiteFile} onChange={(e) => setSuiteFile(e.target.value)}>
              {(suites.data ?? []).map((s) => <option key={s.file} value={s.file} disabled={Boolean(s.error)}>{s.name ?? s.file} {s.tasks ? `(${s.tasks} tasks)` : ""}</option>)}
            </select>
            {suiteRow.data && <span className="hint mono">digest {suiteRow.data.digest.slice(0, 23)}…</span>}
          </div>

          <div className="row">
            <ModelSelect id="baseline" label="Baseline (current model)" value={baseline} onChange={setBaseline} groups={groups} />
            <ModelSelect id="candidate" label="Candidate (NVIDIA open model)" value={candidate} onChange={setCandidate} groups={groups} />
          </div>
          {nebius && !nebius.configured && <p className="callout">Nebius Token Factory is not configured on the server ({nebius.reason}). Live NVIDIA models appear here once the key is set.</p>}
          {nebius?.error && <p className="callout error-text">Model catalog error: {nebius.error}</p>}
          {fixtureMode && <p className="callout fixture">Fixture mode: a scripted provider replays reference solutions. Results are labelled and are not model results.</p>}

          <fieldset className="field" style={{ border: 0, padding: 0 }}>
            <legend className="label">Tasks ({selected.length || tasks.length} of {tasks.length})</legend>
            <div className="task-list">
              {tasks.map((t) => (
                <label key={t.id}>
                  <input type="checkbox" checked={selected.length === 0 || selected.includes(t.id)}
                    onChange={(e) => {
                      const all = selected.length === 0 ? tasks.map((x) => x.id) : selected;
                      const next = e.target.checked ? [...all, t.id] : all.filter((x) => x !== t.id);
                      setSelected(next.length === tasks.length ? [] : next);
                    }} />
                  <span><strong>{t.id}</strong>{t.critical ? <> <span className="badge warn">critical</span></> : null}<br /><span className="hint">{t.category}</span></span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="field">
            <label htmlFor="pr">GitHub pull request (optional)</label>
            <input id="pr" placeholder="https://github.com/owner/repo/pull/1" value={prUrl} onChange={(e) => setPrUrl(e.target.value)} />
          </div>
        </div>
      </section>

      <div className="stack">
        <section className="panel" aria-labelledby="policy-title">
          <header><h2 id="policy-title">Migration policy</h2></header>
          <div className="body">
            {numberField("max_pass_rate_drop", "Max pass-rate drop", "Block if the candidate falls further than this (0.02 = 2 points).")}
            {numberField("max_p95_latency_ms", "Max p95 latency (ms)", "Warn above this.", 500)}
            {numberField("max_provider_error_rate", "Max provider error rate", "Block: comparison unreliable above this.")}
            <label className="field" style={{ display: "flex", gap: 8 }}>
              <input type="checkbox" checked={policy.critical_tasks_must_pass} onChange={(e) => setPolicy({ ...policy, critical_tasks_must_pass: e.target.checked })} />
              Critical tasks must pass (block)
            </label>
            <label className="field" style={{ display: "flex", gap: 8 }}>
              <input type="checkbox" checked={policy.require_lower_cost_per_success} onChange={(e) => setPolicy({ ...policy, require_lower_cost_per_success: e.target.checked })} />
              Require lower cost per success (warn)
            </label>
          </div>
        </section>

        <section className="panel" aria-labelledby="budget-title">
          <header><h2 id="budget-title">Budget</h2></header>
          <div className="body">
            <button className="btn" onClick={() => runEstimate.mutate()} disabled={!suiteRow.data || runEstimate.isPending}>Estimate requests</button>
            {estimate && (
              <div style={{ marginTop: 10 }}>
                <p><strong>{String(estimate.cases)}</strong> cases × 2 lanes, up to <strong>{String(estimate.max_provider_calls)}</strong> provider calls (limit {String(estimate.limit_provider_calls)}).</p>
                <p className="hint">{String(estimate.note)}</p>
                {!estimate.within_budget && (
                  <label style={{ display: "flex", gap: 8 }}>
                    <input type="checkbox" checked={confirmOver} onChange={(e) => setConfirmOver(e.target.checked)} />
                    I confirm running above the configured budget
                  </label>
                )}
                <p style={{ marginTop: 12 }}>
                  <button className="btn primary" onClick={() => launch.mutate()} disabled={launch.isPending || (!estimate.within_budget && !confirmOver)}>
                    {launch.isPending ? "Starting…" : "Start experiment"}
                  </button>
                </p>
              </div>
            )}
            {launch.error && <p className="error-text">{(launch.error as Error).message}</p>}
          </div>
        </section>

        <section className="panel" aria-labelledby="history-title">
          <header><h2 id="history-title">Previous experiments</h2></header>
          <div className="body">
            {(history.data ?? []).length === 0 && <p className="hint">None yet.</p>}
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
              {(history.data ?? []).map((e) => (
                <li key={e.id}>
                  <a href={`/experiments/${e.id}`} onClick={(ev) => { ev.preventDefault(); navigate(`/experiments/${e.id}`); }}>
                    {new Date(e.created_at).toLocaleString()}
                  </a>{" "}
                  <span className={`badge ${e.outcome ?? ""}`}>{e.outcome ?? e.status}</span>{" "}
                  {e.fixture_mode && <span className="badge fixture">fixture</span>}{" "}
                  <span className="hint mono">{e.candidate.model}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
