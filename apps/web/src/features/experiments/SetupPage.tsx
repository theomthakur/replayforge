import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { navigate } from "../../app/App";
import { api } from "../../api/client";
import type { ModelOption } from "../../api/types";

const optionKey = (o: ModelOption) => `${o.provider}|${o.model}`;

const AGENT_STAGES = [
  { mark: "01", name: "Mission controller", detail: "Locks the suite, repository digest, limits and release policy before dispatch." },
  { mark: "02", name: "Paired coding agents", detail: "Baseline and candidate agents independently inspect, edit and test fresh copies of the same repository." },
  { mark: "03", name: "Evidence pipeline", detail: "Sandbox tools and deterministic graders record what happened instead of trusting either agent's summary." },
  { mark: "04", name: "Investigator", detail: "Reconciles disagreements, classifies failures and links every finding to a trace step or grader." },
  { mark: "05", name: "Release guardian", detail: "Applies the stored rules and publishes the resulting pass, warn or block decision." },
] as const;

const CATEGORY_COPY: Record<string, { label: string; action: string; tools: string }> = {
  bug_fix: { label: "Bug repair", action: "Inspect the failure, edit production code, then rerun the focused tests.", tools: "read · search · patch · test" },
  tool_use: { label: "Tool discipline", action: "Choose the required repository tools and return the exact requested evidence.", tools: "read · list · search · run" },
  navigation: { label: "Repository navigation", action: "Locate the correct implementation or configuration without changing files.", tools: "list · search · read" },
  test_generation: { label: "Test generation", action: "Write meaningful tests within the permitted paths and prove that they pass.", tools: "read · patch · test" },
  refactor: { label: "Safe refactor", action: "Improve the implementation while preserving behavior and protected files.", tools: "read · search · patch · test" },
  recovery: { label: "Failure recovery", action: "Observe the first failure, diagnose its cause, repair it and verify recovery.", tools: "run · inspect · patch · rerun" },
};

function Toggle({ checked, onChange, title, detail }: { checked: boolean; onChange: (checked: boolean) => void; title: string; detail: string }) {
  return <label className="policy-toggle">
    <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    <span className="toggle-track" aria-hidden="true"><i /></span>
    <span><strong>{title}</strong><small>{detail}</small></span>
  </label>;
}

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
  const [suiteFile, setSuiteFile] = useState("portfolio-optimization.yaml");
  const suiteRow = useQuery({ queryKey: ["suite", suiteFile], queryFn: () => api.createSuite(suiteFile) });
  const suiteDef = useQuery({ queryKey: ["suite-def", suiteRow.data?.id], queryFn: () => api.suite(suiteRow.data!.id), enabled: Boolean(suiteRow.data?.id) });
  const [baseline, setBaseline] = useState("fixture|fixture/reference");
  const [candidate, setCandidate] = useState("fixture|fixture/variant");
  const [selected, setSelected] = useState<string[] | null>(null);
  const [prUrl, setPrUrl] = useState("");
  const [policy, setPolicy] = useState({ max_pass_rate_drop: 0.02, critical_tasks_must_pass: true, max_p95_latency_ms: 15000, require_lower_cost_per_success: false, max_provider_error_rate: 0.02 });
  const [estimate, setEstimate] = useState<Record<string, number | boolean | string> | null>(null);
  const [confirmOver, setConfirmOver] = useState(false);
  const [brief, setBrief] = useState("Compare the candidate on release-critical bug fixes and block any regression.");
  const [controllerReply, setControllerReply] = useState("Give me one goal. I will plan the workload, enforce the budget, dispatch both coding agents, investigate the evidence and produce the release decision.");
  const [reviewOpen, setReviewOpen] = useState(false);

  const nebius = models.data?.nebius;
  const groups = useMemo(() => [
    { label: "NVIDIA models on Nebius Token Factory (live catalog)", options: (nebius?.models ?? []).filter((m) => m.nvidia) },
    { label: "Other Token Factory models", options: (nebius?.models ?? []).filter((m) => !m.nvidia) },
    { label: "Configured local models", options: models.data?.local ?? [] },
    { label: "Configured baseline", options: models.data?.baseline ?? [] },
    { label: "Fixture (scripted, not a model)", options: models.data?.fixture ?? [] },
  ], [models.data, nebius]);

  useEffect(() => {
    const firstNvidia = nebius?.models.find((m) => m.nvidia);
    if (firstNvidia) setCandidate(optionKey(firstNvidia));
  }, [nebius]);

  const tasks = suiteDef.data?.definition.tasks ?? [];
  const sourceRepository = suiteDef.data?.definition.suite.source_repository_url;
  const sourceRevision = suiteDef.data?.definition.suite.source_revision;
  const lane = (key: string) => { const [provider, ...rest] = key.split("|"); return { provider, model: rest.join("|") }; };
  const selectedTaskIds = selected ?? tasks.map((task) => task.id);
  const body = () => ({
    suite_id: suiteRow.data?.id, baseline: lane(baseline), candidate: lane(candidate), policy,
    task_ids: selected ?? [], pull_request_url: prUrl || null, confirm_budget: confirmOver,
  });
  const autopilotBody = () => ({
    suite_id: suiteRow.data?.id,
    brief,
    baseline: lane(baseline),
    candidate: lane(candidate),
    pull_request_url: prUrl || null,
  });
  const fixtureMode = baseline.startsWith("fixture|") || candidate.startsWith("fixture|");

  const briefController = () => {
    const text = brief.toLowerCase();
    const categories = new Set<string>();
    if (/bug|repair|fix|production/.test(text)) categories.add("bug_fix");
    if (/tool|command/.test(text)) categories.add("tool_use");
    if (/find|locate|navigation|repository/.test(text)) categories.add("navigation");
    if (/test|coverage/.test(text)) categories.add("test_generation");
    if (/refactor|maintain/.test(text)) categories.add("refactor");
    if (/recover|failure|resilien/.test(text)) categories.add("recovery");
    const criticalOnly = /critical|release|production/.test(text);
    const matches = tasks.filter((task) => (!criticalOnly || task.critical) && (categories.size === 0 || categories.has(task.category))).map((task) => task.id);
    const planned = /all|full|every|entire/.test(text) ? tasks.map((task) => task.id) : matches.length ? matches : tasks.filter((task) => task.critical).map((task) => task.id);
    setSelected(planned.length === tasks.length ? null : planned);
    setPolicy({
      ...policy,
      max_pass_rate_drop: /strict|no regression|zero regression/.test(text) ? 0 : policy.max_pass_rate_drop,
      critical_tasks_must_pass: !/allow critical/.test(text),
      require_lower_cost_per_success: /cost|cheaper|efficien/.test(text),
    });
    setEstimate(null);
    setReviewOpen(true);
    setControllerReply(`Prepared ${planned.length} paired task${planned.length === 1 ? "" : "s"}${criticalOnly ? " focused on release-critical behavior" : ""}. ${/strict|no regression|zero regression/.test(text) ? "Pass-rate regression tolerance is zero." : "Existing numeric limits are preserved."} Review the brief below, then calculate the run envelope.`);
  };

  const runEstimate = useMutation({ mutationFn: () => api.estimate(body()), onSuccess: setEstimate });
  const launch = useMutation({
    mutationFn: async () => {
      const created = await api.createExperiment(body(), crypto.randomUUID());
      await api.start(created.id);
      return created;
    },
    onSuccess: (created) => navigate(`/experiments/${created.id}`),
  });
  const autopilot = useMutation({
    mutationFn: () => api.autopilot(autopilotBody(), crypto.randomUUID()),
    onSuccess: ({ experiment }) => navigate(`/experiments/${experiment.id}`),
    onError: (error) => {
      setReviewOpen(true);
      setControllerReply(`Autopilot paused safely: ${(error as Error).message}. Open advanced controls to resolve it.`);
    },
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
    <div className="setup-shell">
      <section className="setup-intro">
        <div>
          <span className="eyebrow">Coding-agent reliability operations</span>
          <h1>Prove a model migration<br />before it reaches production.</h1>
        </div>
        <p>Replay identical repository work on two models, test every change in isolation, investigate behavioral regressions, and turn the evidence into an enforceable release decision.</p>
        <div className="setup-capabilities" aria-label="Workflow summary">
          <span>01 · Replay</span><span>02 · Execute</span><span>03 · Grade</span><span>04 · Investigate</span><span>05 · Gate</span>
        </div>
      </section>

      <section className="operation-guide" aria-labelledby="operation-guide-title">
        <div className="operation-guide-heading"><span className="eyebrow">What happens after launch</span><h2 id="operation-guide-title">One goal starts the complete agent mission</h2><p>The mission controller plans from signed tasks. Coding agents execute in parallel; evidence, investigation, policy and reporting continue without another prompt.</p></div>
        <ol>{AGENT_STAGES.map((stage) => <li key={stage.name}><span>{stage.mark}</span><div><strong>{stage.name}</strong><small>{stage.detail}</small></div></li>)}</ol>
      </section>

      <section className="mission-chat" aria-labelledby="mission-chat-title">
        <div className="mission-chat-copy"><span className="eyebrow">Autonomous control plane</span><h2 id="mission-chat-title">Give the mission controller one goal</h2><p>Choose the codebase and state the outcome. ReplayForge handles planning through the final downloadable decision; human approval returns only for an unsafe budget or external publication.</p><div className="mission-suggestions">{["Critical changes, zero regression", "Full reliability sweep", "Tool-use and recovery behavior", "Prioritize lower cost"].map((suggestion) => <button type="button" key={suggestion} onClick={() => setBrief(suggestion)}>{suggestion}</button>)}</div></div>
        <div className="mission-console">
          <div className="controller-message"><img src="/favicon.svg" alt="" /><span><strong>Mission controller</strong><small>{controllerReply}</small></span></div>
          <label htmlFor="autopilot-suite">Repository workload</label>
          <select id="autopilot-suite" value={suiteFile} onChange={(event) => { setSuiteFile(event.target.value); setSelected(null); setEstimate(null); }}>
            {(suites.data ?? []).map((suite) => <option key={suite.file} value={suite.file} disabled={Boolean(suite.error)}>{suite.name ?? suite.file}</option>)}
          </select>
          {sourceRepository && <div className="repository-provenance"><span>Commit-pinned source</span><a href={sourceRepository} target="_blank" rel="noreferrer">{sourceRepository.replace("https://github.com/", "")}</a>{sourceRevision && <code>{sourceRevision.slice(0, 8)}</code>}</div>}
          <label htmlFor="mission-brief">Your migration brief</label>
          <textarea id="mission-brief" value={brief} onChange={(event) => setBrief(event.target.value)} rows={3} />
          <button className="btn primary autopilot-launch" type="button" onClick={() => autopilot.mutate()} disabled={!brief.trim() || !suiteRow.data || autopilot.isPending}>
            {autopilot.isPending ? "Mission controller is dispatching…" : "Run autonomous audit"}
          </button>
          <button className="text-action" type="button" onClick={briefController}>Preview plan or change advanced controls</button>
          <div className="autopilot-scope"><span>Plans signed tasks</span><span>Runs both agents</span><span>Grades evidence</span><span>Investigates drift</span><span>Applies policy</span><span>Builds report</span></div>
          <small className="controller-boundary">The controller cannot invent tasks, weaken graders, exceed the provider-call budget, or publish externally without configured authority.</small>
          {autopilot.error && <p className="error-text">{(autopilot.error as Error).message}</p>}
        </div>
      </section>

      <details className="mission-review" open={reviewOpen} onToggle={(event) => setReviewOpen(event.currentTarget.open)}>
      <summary><span><b>Advanced controls</b><small>Optional manual task, model, policy and budget configuration</small></span><span><strong>{selectedTaskIds.length}</strong> available tasks</span></summary>
      <div className="grid-setup">
      <section className="panel" aria-labelledby="setup-title">
        <header><h2 id="setup-title">Configure the agent mission</h2><span className="eyebrow">Workload and lanes</span></header>
        <div className="body">
          <div className="section-instruction"><span>1</span><div><strong>Choose the repository workload</strong><small>The suite digest freezes the tasks and fixture so both agents receive the same work.</small></div></div>
          <div className="field">
            <label htmlFor="suite">Versioned workload</label>
            <select id="suite" value={suiteFile} onChange={(e) => setSuiteFile(e.target.value)}>
              {(suites.data ?? []).map((s) => <option key={s.file} value={s.file} disabled={Boolean(s.error)}>{s.name ?? s.file} {s.tasks ? `(${s.tasks} tasks)` : ""}</option>)}
            </select>
            {suiteRow.data && <span className="hint mono">digest {suiteRow.data.digest.slice(0, 23)}…</span>}
            {sourceRepository && <div className="repository-provenance"><span>Real repository snapshot</span><a href={sourceRepository} target="_blank" rel="noreferrer">{sourceRepository.replace("https://github.com/", "")}</a>{sourceRevision && <code>{sourceRevision.slice(0, 8)}</code>}</div>}
          </div>

          <div className="section-instruction"><span>2</span><div><strong>Assign the two coding-agent lanes</strong><small>Each agent gets an independent sandbox, identical tools and the same step limits.</small></div></div>
          <div className="row">
            <ModelSelect id="baseline" label="Baseline (current model)" value={baseline} onChange={setBaseline} groups={groups} />
            <ModelSelect id="candidate" label="Candidate model" value={candidate} onChange={setCandidate} groups={groups} />
          </div>
          {nebius && !nebius.configured && <p className="callout">Nebius Token Factory is not configured on the server ({nebius.reason}). Live NVIDIA models appear here once the key is set.</p>}
          {nebius?.error && <p className="callout error-text">Model catalog error: {nebius.error}</p>}
          {fixtureMode && <p className="callout fixture">Fixture mode: a scripted provider replays reference solutions. Results are labelled and are not model results.</p>}

          <fieldset className="field task-fieldset">
            <legend className="visually-hidden">Agent tasks</legend>
            <div className="task-section-head">
              <div className="section-instruction"><span>3</span><div><strong>Select the agent tasks</strong><small>Each card describes the mission and the evidence used to judge it.</small></div></div>
              <div className="task-selection-summary"><strong>{selectedTaskIds.length}</strong><span>of {tasks.length} selected</span><button type="button" onClick={() => setSelected(null)} disabled={selected === null}>Select all</button></div>
            </div>
            <div className="task-list">
              {tasks.map((task) => {
                const copy = CATEGORY_COPY[task.category] ?? { label: task.category.split("_").join(" "), action: "Complete the repository task and produce verifiable evidence.", tools: "bounded repository tools" };
                const checked = selected === null || selected.includes(task.id);
                return <label key={task.id} className={`mission-task ${checked ? "selected" : ""}`}>
                  <input type="checkbox" checked={checked} onChange={(event) => {
                    const current = selected ?? tasks.map((item) => item.id);
                    const next = event.target.checked ? [...current, task.id] : current.filter((id) => id !== task.id);
                    setSelected(next.length === tasks.length ? null : next);
                  }} />
                  <span className="task-check" aria-hidden="true">{checked ? "✓" : ""}</span>
                  <span className="task-content">
                    <span className="task-meta"><span>{copy.label}</span>{task.critical && <span className="badge warn">release critical</span>}</span>
                    <strong>{task.description}</strong>
                    <small><b>Agent mission</b>{copy.action}</small>
                    <span className="task-tools">Tools · {copy.tools}</span>
                  </span>
                </label>;
              })}
            </div>
            {selectedTaskIds.length === 0 && <p className="error-text task-selection-error">Select at least one task before calculating the run.</p>}
          </fieldset>

          <div className="section-instruction"><span>4</span><div><strong>Choose the external handoff</strong><small>Optional: publish the stored decision to one GitHub pull-request check after the run.</small></div></div>
          <div className="field">
            <label htmlFor="pr">GitHub pull request (optional)</label>
            <input id="pr" placeholder="https://github.com/owner/repo/pull/1" value={prUrl} onChange={(e) => setPrUrl(e.target.value)} />
          </div>
        </div>
      </section>

      <div className="stack">
        <section className="panel" aria-labelledby="policy-title">
          <header><h2 id="policy-title">Release guardrails</h2><span className="eyebrow">Deterministic authority</span></header>
          <div className="body policy-body">
            <p className="panel-explainer">The agents cannot rewrite these rules. ReplayForge evaluates them after all paired evidence is stored.</p>
            <div className="policy-numbers">
              {numberField("max_pass_rate_drop", "Allowed pass-rate drop", "0.02 means two percentage points before BLOCK.")}
              {numberField("max_p95_latency_ms", "Maximum p95 latency", "Milliseconds before a WARN.", 500)}
              {numberField("max_provider_error_rate", "Provider error ceiling", "Unreliable comparisons BLOCK above this ratio.")}
            </div>
            <div className="policy-toggles">
              <Toggle checked={policy.critical_tasks_must_pass} onChange={(checked) => setPolicy({ ...policy, critical_tasks_must_pass: checked })} title="Critical tasks must pass" detail="BLOCK when the candidate fails any release-critical task." />
              <Toggle checked={policy.require_lower_cost_per_success} onChange={(checked) => setPolicy({ ...policy, require_lower_cost_per_success: checked })} title="Require lower cost per success" detail="WARN when the candidate does not improve measured cost efficiency." />
            </div>
          </div>
        </section>

        <section className="panel" aria-labelledby="budget-title">
          <header><h2 id="budget-title">Mission preflight</h2><span className="eyebrow">Review before launch</span></header>
          <div className="body">
            <p className="panel-explainer">Calculate the maximum provider calls before either coding agent starts. No credits are spent by this estimate.</p>
            <button className="btn" onClick={() => runEstimate.mutate()} disabled={!suiteRow.data || runEstimate.isPending || selectedTaskIds.length === 0}>Calculate run envelope</button>
            {estimate && (
              <div style={{ marginTop: 10 }}>
                <p><strong>{String(estimate.cases)}</strong> cases × 2 lanes, up to <strong>{String(estimate.max_provider_calls)}</strong> provider calls (limit {String(estimate.limit_provider_calls)}).</p>
                <p className="hint">{String(estimate.note)}</p>
                {!estimate.within_budget && (
                  <Toggle checked={confirmOver} onChange={setConfirmOver} title="Approve the larger run envelope" detail="I understand this mission can exceed the configured provider-call budget." />
                )}
                <p style={{ marginTop: 12 }}>
                  <button className="btn primary" onClick={() => launch.mutate()} disabled={launch.isPending || (!estimate.within_budget && !confirmOver)}>
                    {launch.isPending ? "Starting…" : "Launch autonomous evaluation"}
                  </button>
                  <span className="autonomy-note">After launch, ReplayForge runs both lanes, grades evidence, investigates differences, applies policy and generates the report without another approval.</span>
                </p>
              </div>
            )}
            {launch.error && <p className="error-text">{(launch.error as Error).message}</p>}
          </div>
        </section>

        <section className="panel" aria-labelledby="history-title">
          <header><h2 id="history-title">Previous missions</h2><span className="eyebrow">Persisted evidence</span></header>
          <div className="body history-body">
            {(history.data ?? []).length === 0 && <p className="hint">None yet.</p>}
            <ul className="experiment-history">
              {(history.data ?? []).map((e) => (
                <li key={e.id}>
                  <a href={`/experiments/${e.id}`} onClick={(event) => { event.preventDefault(); navigate(`/experiments/${e.id}`); }}>
                    <span className="history-top"><span className={`badge ${e.outcome ?? ""}`}>{e.outcome ?? e.status}</span>{e.fixture_mode ? <span className="badge fixture">simulation</span> : <span className="badge pass">live</span>}<time>{new Date(e.created_at).toLocaleString()}</time></span>
                    <span className="history-lanes"><span><small>Baseline</small><b>{e.baseline.model}</b></span><i>→</i><span><small>Candidate</small><b>{e.candidate.model}</b></span></span>
                    <span className="history-open">Open evidence and traces <b>→</b></span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
      </div>
      </details>
    </div>
  );
}
