import { useEffect, useState } from "react";

import { ExperimentPage } from "../features/experiments/ExperimentPage";
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
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>
          <img src="/favicon.svg" width={26} height={26} alt="" />
          ReplayForge <small>model-migration lab for coding agents</small>
        </a>
        <div className="spacer" />
      </header>
      <main>{match ? <ExperimentPage experimentId={match[1]} /> : <SetupPage />}</main>
    </div>
  );
}
