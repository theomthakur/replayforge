import { useEffect, useState } from "react";

import { ExperimentPage } from "../features/experiments/ExperimentPage";
import { Presentation } from "../features/explain/Presentation";
import { SystemDesign } from "../features/explain/SystemDesign";
import { SetupPage } from "../features/experiments/SetupPage";

export function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return path;
}

export function App() {
  const path = usePath();
  const match = path.match(/^\/experiments\/([a-f0-9]{32})$/);
  const page = path === "/presentation"
    ? <Presentation />
    : path === "/system-design"
      ? <SystemDesign />
      : match
        ? <ExperimentPage experimentId={match[1]} />
        : <SetupPage />;
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>
          <img src="/favicon.svg" width={38} height={38} alt="" />
          <span><b>ReplayForge</b><small>Model migration lab for coding agents</small></span>
        </a>
        <div className="spacer" />
        <nav className="topnav" aria-label="Product">
          <a href="/" aria-current={path === "/" ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate("/"); }}>Lab</a>
          <a href="/system-design" aria-current={path === "/system-design" ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate("/system-design"); }}>System design</a>
          <a href="/presentation" aria-current={path === "/presentation" ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate("/presentation"); }}>Presentation</a>
        </nav>
        <span className="topbar-context">Coding-agent evaluation</span>
      </header>
      <main>{page}</main>
    </div>
  );
}
