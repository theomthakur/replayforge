import type { ReplayEvent } from "../../api/types";

function detail(event: ReplayEvent): string {
  const p = event.payload;
  const parts = [p.task_id, p.lane, p.tool, p.outcome, p.category, p.error_kind, p.failure_mode, p.error].filter((x) => typeof x === "string" && x);
  if (typeof p.passed === "boolean") parts.push(p.passed ? "pass" : "fail");
  return parts.join(" · ");
}

export function Timeline({ events, connected }: { events: ReplayEvent[]; connected: boolean }) {
  const shown = events.filter((e) => e.type !== "agent.thinking").slice(-300).reverse();
  return (
    <section className="panel" aria-labelledby="timeline-title">
      <header>
        <h2 id="timeline-title">Timeline (persisted events)</h2>
        <span className="hint"><span className="dot" style={{ background: connected ? "var(--ok)" : "var(--waiting)" }} /> {connected ? "live" : "reconnecting / idle"} · {events.length} events</span>
      </header>
      <div className="timeline" role="log" aria-live="off">
        <ol>
          {shown.map((e) => (
            <li key={e.seq}>
              <span className="t">#{e.seq}</span>
              <span className="type">{e.type}</span>
              <span className="detail">{detail(e)}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
