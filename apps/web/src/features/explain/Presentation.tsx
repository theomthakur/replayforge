import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

type Slide = { label: string; eyebrow: string; title: ReactNode; body: ReactNode };

const Card = ({ number, title, children }: { number: string; title: string; children: ReactNode }) => (
  <section className="pitch-card"><span>{number}</span><h3>{title}</h3><p>{children}</p></section>
);

const SLIDES: Slide[] = [
  {
    label: "Opening", eyebrow: "CODING AGENT EVALUATION · PAIRED WORKLOADS",
    title: <>Your coding agent passed yesterday.<br /><span>Will it survive a model migration?</span></>,
    body: <><p className="pitch-lede">ReplayForge runs the same repository work on a baseline and a candidate model, then tests the code—not the explanation—before the migration reaches production.</p><div className="pitch-metrics"><div><b>20</b><span>versioned coding cases</span></div><div><b>2</b><span>isolated model lanes</span></div><div><b>1</b><span>enforceable release gate</span></div></div></>,
  },
  {
    label: "Problem", eyebrow: "01 · THE RELIABILITY GAP", title: "Static benchmarks miss the failures that break real coding agents",
    body: <div className="pitch-columns"><Card number="01" title="Tool behavior">A model can write good prose and still choose the wrong file, malformed arguments, or an unsafe command.</Card><Card number="02" title="Repository outcomes">Plausible patches still fail tests, touch protected paths, or stop recovering after an error.</Card><Card number="03" title="Migration economics">A cheaper token price means little if longer trajectories reduce successful work.</Card></div>,
  },
  {
    label: "Workflow", eyebrow: "02 · THE EXPERIMENT", title: "One workload. Two lanes. Evidence at every step.",
    body: <ol className="pitch-flow"><li><b>Lock</b><span>Version the task suite, repository fixture, limits and policy.</span></li><li><b>Replay</b><span>Give both models identical prompts, tools and fresh sandboxes.</span></li><li><b>Grade</b><span>Run deterministic tests and tool-contract checks.</span></li><li><b>Investigate</b><span>Classify disagreements with trace and grader references.</span></li><li><b>Gate</b><span>Publish pass, warn or block to the pull request.</span></li></ol>,
  },
  {
    label: "Model Lab", eyebrow: "03 · THE OPERATIONS FLOOR", title: "The 3D room is not theatre. It is the event log made visible.",
    body: <div className="pitch-floor"><div className="floor-map"><span className="zone baseline-zone">Baseline lane</span><span className="zone test-zone">Deterministic test bench</span><span className="zone candidate-zone">Candidate lane</span><span className="zone investigate-zone">Investigation</span><span className="zone gate-zone">Release gate</span></div><div className="pitch-copy"><p>Every work packet represents one saved case on one lane. It moves only when the backend commits an event.</p><p>Click a packet to open the exact trace. Hide 3D and the same evidence remains available in the cases table.</p></div></div>,
  },
  {
    label: "Trust", eyebrow: "04 · TRUST BOUNDARIES", title: "The model can propose work. It cannot grade or approve itself.",
    body: <div className="trust-stack"><div><b>Sandbox</b><span>Fresh workspace, allowlisted tools, scrubbed environment, time and output limits.</span></div><div><b>Deterministic graders</b><span>Tests, files, protected paths, output and tool contracts decide correctness.</span></div><div><b>Measured metrics</b><span>Unknown usage or price stays unknown. Every number carries its measurement kind and sample count.</span></div><div><b>Stored policy</b><span>Critical-task, pass-rate and provider-error rules own the final decision.</span></div></div>,
  },
  {
    label: "Architecture", eyebrow: "05 · SYSTEM DESIGN", title: "A resumable control plane turns model behavior into release evidence",
    body: <div className="mini-architecture"><div>React command center<small>REST snapshot · resumable SSE · 3D lab</small></div><i>→</i><div className="core">FastAPI control plane<small>orchestration · persistence · idempotency</small></div><i>→</i><div>Paired agent runners<small>baseline · configured candidate</small></div><span>↓</span><div>Fresh sandboxes<small>bounded tools · deterministic graders</small></div><span>↓</span><div className="gate">GitHub release gate<small>stored report · pass / warn / block</small></div></div>,
  },
  {
    label: "Proof", eyebrow: "06 · WHAT EXISTS TODAY", title: "A working reliability lab, with the limits stated plainly",
    body: <><ul className="proof-list"><li><b>✓</b>60 backend and engine tests, plus 11 web tests</li><li><b>✓</b>20-case paired fixture run with seeded regressions</li><li><b>✓</b>Optional Nebius catalog discovery and NVIDIA-model validation</li><li><b>✓</b>Persistent events, resume, cancellation and GitHub check upsert</li><li><b>△</b>Live model run and real GitHub PR require local credentials</li></ul><p className="pitch-foot">github.com/theomthakur/replayforge</p></>,
  },
  {
    label: "Close", eyebrow: "REPLAYFORGE", title: <>Change the model.<br /><span>Keep the reliability contract.</span></>,
    body: <><p className="pitch-lede">Open models should win migrations on the work that matters: your repository, your tools, your tests and your release policy.</p><div className="pitch-links"><a href="/">Open the lab</a><a href="/system-design">Inspect the system design</a></div></>,
  },
];

export function Presentation() {
  const [index, setIndex] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const shell = useRef<HTMLDivElement>(null);
  const go = useCallback((next: number) => setIndex(Math.max(0, Math.min(SLIDES.length - 1, next))), []);
  const toggle = useCallback(() => document.fullscreenElement ? void document.exitFullscreen() : void shell.current?.requestFullscreen(), []);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.target instanceof Element && event.target.closest("input, textarea, select")) return;
      if (["ArrowRight", "PageDown", " "].includes(event.key)) { event.preventDefault(); setIndex((value) => Math.min(SLIDES.length - 1, value + 1)); }
      if (["ArrowLeft", "PageUp"].includes(event.key)) { event.preventDefault(); setIndex((value) => Math.max(0, value - 1)); }
      if (event.key === "Home") go(0);
      if (event.key === "End") go(SLIDES.length - 1);
      if (event.key.toLowerCase() === "f") toggle();
    };
    const full = () => setFullscreen(Boolean(document.fullscreenElement));
    window.addEventListener("keydown", key); document.addEventListener("fullscreenchange", full);
    return () => { window.removeEventListener("keydown", key); document.removeEventListener("fullscreenchange", full); };
  }, [go, toggle]);
  const slide = SLIDES[index];
  return <div className={`pitch-shell ${fullscreen ? "fullscreen" : ""}`} ref={shell}>
    <div className="pitch-toolbar"><span>{String(index + 1).padStart(2, "0")} / {String(SLIDES.length).padStart(2, "0")} · {slide.label}</span><button onClick={toggle}>{fullscreen ? "Exit fullscreen" : "Present fullscreen (F)"}</button></div>
    <article className={`pitch-slide ${index === 0 || index === SLIDES.length - 1 ? "hero" : ""}`} aria-live="polite" aria-roledescription="slide" aria-label={`${index + 1} of ${SLIDES.length}: ${slide.label}`}>
      <p className="pitch-eyebrow">{slide.eyebrow}</p><h2>{slide.title}</h2><div className="pitch-body">{slide.body}</div>
    </article>
    <div className="pitch-controls"><button onClick={() => go(index - 1)} disabled={index === 0}>← Previous</button><div>{SLIDES.map((item, slideIndex) => <button key={item.label} aria-label={`Open ${item.label} slide`} className={index === slideIndex ? "active" : ""} onClick={() => go(slideIndex)} />)}</div><button onClick={() => go(index + 1)} disabled={index === SLIDES.length - 1}>Next →</button></div>
  </div>;
}
