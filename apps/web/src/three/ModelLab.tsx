import { Html, OrbitControls, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import type { Group, Mesh } from "three";

import type { Lane, TaskSummary } from "../api/types";
import { caseKey, type CaseStage, type LabState } from "../features/experiments/labState";

const COLORS = {
  baseline: "#5ee7ff",
  candidate: "#76d34f",
  waiting: "#6b7890",
  warn: "#f5b83d",
  fail: "#ff6b5e",
  ok: "#6ff2c4",
  floor: "#0b1322",
};

/** x position along a rail for each persisted stage: queue -> runner -> test chamber -> result. */
const STAGE_X: Record<CaseStage, number> = {
  queued: -6.2, provisioning: -3.4, reasoning: -2.2, tool_execution: -1.0, grading: 1.4, passed: 3.6, failed: 3.6,
};

function capsuleColor(stage: CaseStage, lane: Lane): string {
  if (stage === "passed") return COLORS.ok;
  if (stage === "failed") return COLORS.fail;
  if (stage === "queued") return COLORS.waiting;
  return COLORS[lane];
}

function Capsule({ task, lane, index, count, state, selected, reducedMotion, onSelect }: {
  task: TaskSummary; lane: Lane; index: number; count: number; state: LabState; selected: boolean; reducedMotion: boolean; onSelect: (id: string, lane: Lane) => void;
}) {
  const ref = useRef<Mesh>(null);
  const c = state.cases[caseKey(task.id, lane)];
  const stage: CaseStage = c?.stage ?? "queued";
  const laneZ = lane === "baseline" ? -1.8 : 1.8;
  const spread = (index - (count - 1) / 2) * 0.34;
  const target: [number, number, number] = [STAGE_X[stage] + (stage === "queued" || stage === "passed" || stage === "failed" ? 0 : spread * 0.4), 0.35, laneZ + (stage === "queued" || stage === "passed" || stage === "failed" ? spread * 0.42 : spread * 0.22)];
  const active = stage === "reasoning" || stage === "tool_execution" || stage === "grading" || stage === "provisioning";

  useFrame((_, delta) => {
    const mesh = ref.current;
    if (!mesh) return;
    if (reducedMotion) {
      mesh.position.set(...target);
    } else {
      const k = Math.min(1, delta * 4);
      mesh.position.x += (target[0] - mesh.position.x) * k;
      mesh.position.y += (target[1] + (active ? Math.sin(performance.now() / 260 + index) * 0.08 : 0) - mesh.position.y) * k;
      mesh.position.z += (target[2] - mesh.position.z) * k;
    }
  });

  return (
    <mesh
      ref={ref}
      position={target}
      onClick={(e) => { e.stopPropagation(); onSelect(task.id, lane); }}
      onPointerOver={() => { document.body.style.cursor = "pointer"; }}
      onPointerOut={() => { document.body.style.cursor = "default"; }}
      scale={selected ? 1.5 : 1}
    >
      <capsuleGeometry args={[0.1, task.critical ? 0.3 : 0.18, 4, 10]} />
      <meshStandardMaterial color={capsuleColor(stage, lane)} emissive={capsuleColor(stage, lane)} emissiveIntensity={selected ? 0.9 : active ? 0.55 : 0.2} />
    </mesh>
  );
}

function Station({ position, color, label, sub, size = [1.4, 0.5, 1.2] as [number, number, number] }: {
  position: [number, number, number]; color: string; label: string; sub?: string; size?: [number, number, number];
}) {
  return (
    <group position={position}>
      <RoundedBox args={size} radius={0.08} smoothness={3} position={[0, size[1] / 2, 0]}>
        <meshStandardMaterial color="#132036" emissive={color} emissiveIntensity={0.12} metalness={0.3} roughness={0.6} />
      </RoundedBox>
      <Html center position={[0, size[1] + 0.45, 0]} distanceFactor={11} style={{ pointerEvents: "none" }}>
        <div style={{ font: "600 12px Archivo, sans-serif", color, whiteSpace: "nowrap", textAlign: "center", textShadow: "0 1px 4px #000" }}>
          {label}{sub ? <div style={{ color: "#9aa8bd", fontWeight: 500, fontSize: 11 }}>{sub}</div> : null}
        </div>
      </Html>
    </group>
  );
}

function Rail({ z, color }: { z: number; color: string }) {
  return (
    <mesh position={[-1.3, 0.02, z]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[11.5, 1.1]} />
      <meshStandardMaterial color={color} transparent opacity={0.08} />
    </mesh>
  );
}

function Scene({ tasks, state, selectedTask, selectedLane, reducedMotion, onSelect }: {
  tasks: TaskSummary[]; state: LabState; selectedTask: string | null; selectedLane: Lane; reducedMotion: boolean; onSelect: (id: string, lane: Lane) => void;
}) {
  const gate = useRef<Group>(null);
  const counts = useMemo(() => {
    const tally = { baseline: { pass: 0, fail: 0, active: 0 }, candidate: { pass: 0, fail: 0, active: 0 } };
    for (const c of Object.values(state.cases)) {
      if (c.stage === "passed") tally[c.lane].pass += 1;
      else if (c.stage === "failed") tally[c.lane].fail += 1;
      else if (c.stage !== "queued") tally[c.lane].active += 1;
    }
    return tally;
  }, [state.cases]);
  const decisionColor = state.decision === "pass" ? COLORS.ok : state.decision === "warn" ? COLORS.warn : state.decision === "block" ? COLORS.fail : COLORS.waiting;

  useFrame((_, delta) => {
    if (gate.current && !reducedMotion && state.status !== "completed") gate.current.rotation.y += delta * 0.4;
  });

  return (
    <>
      <color attach="background" args={["#070b14"]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[4, 8, 5]} intensity={1.1} />
      <pointLight position={[0, 3, 0]} intensity={8} color="#2dd4ff" distance={12} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[22, 14]} />
        <meshStandardMaterial color={COLORS.floor} />
      </mesh>
      <gridHelper args={[22, 22, "#1b2a44", "#101a2c"]} position={[0, 0.01, 0]} />

      <Rail z={-1.8} color={COLORS.baseline} />
      <Rail z={1.8} color={COLORS.candidate} />
      <Station position={[-7.6, 0, 0]} color="#e6ecf5" label="Experiment Manager" sub={state.status} size={[1.2, 0.9, 2.2]} />
      <Station position={[-2.2, 0, -3.3]} color={COLORS.baseline} label="Baseline runner" sub={`${counts.baseline.active} active`} size={[2.6, 0.18, 0.5]} />
      <Station position={[-2.2, 0, 3.3]} color={COLORS.candidate} label="Candidate runner (Nebius)" sub={`${counts.candidate.active} active`} size={[2.6, 0.18, 0.5]} />
      <Station position={[1.4, 0, 0]} color="#c7d2e3" label="Test chambers" sub="deterministic graders" size={[1.1, 0.25, 4.6]} />
      <Station position={[3.6, 0, -3.3]} color={COLORS.ok} label="Baseline results" sub={`${counts.baseline.pass} pass · ${counts.baseline.fail} fail`} size={[1.6, 0.12, 0.5]} />
      <Station position={[3.6, 0, 3.3]} color={COLORS.ok} label="Candidate results" sub={`${counts.candidate.pass} pass · ${counts.candidate.fail} fail`} size={[1.6, 0.12, 0.5]} />
      <Station position={[6.2, 0, 2.4]} color={COLORS.warn} label="Investigation table" sub={state.investigating.length ? `${state.investigating.length} under analysis` : `${Object.keys(state.findings).length} hypotheses`} size={[1.4, 0.4, 1.2]} />
      <Station position={[6.2, 0, -2.4]} color="#b9a4ff" label="Cost station" sub="usage × dated price" size={[1.2, 0.4, 1.0]} />

      <group position={[8.4, 0, 0]}>
        <group ref={gate}>
          <mesh position={[0, 1.1, 0]}>
            <torusGeometry args={[0.8, 0.08, 16, 48]} />
            <meshStandardMaterial color={decisionColor} emissive={decisionColor} emissiveIntensity={0.8} />
          </mesh>
        </group>
        <Html center position={[0, 2.35, 0]} distanceFactor={11} style={{ pointerEvents: "none" }}>
          <div style={{ font: "700 13px Archivo, sans-serif", color: decisionColor, textAlign: "center", textShadow: "0 1px 4px #000", whiteSpace: "nowrap" }}>
            Release gate<br />{state.decision ? state.decision.toUpperCase() : "pending"}{state.githubStatus !== "idle" ? ` · GitHub ${state.githubStatus}` : ""}
          </div>
        </Html>
      </group>

      {tasks.map((task, i) =>
        (["baseline", "candidate"] as Lane[]).map((lane) => (
          <Capsule key={caseKey(task.id, lane)} task={task} lane={lane} index={i} count={tasks.length} state={state}
            selected={selectedTask === task.id && selectedLane === lane} reducedMotion={reducedMotion} onSelect={onSelect} />
        )),
      )}
      {tasks.filter((t) => state.investigating.includes(t.id)).map((t, i) => (
        <mesh key={`inv-${t.id}`} position={[6.2 + (i % 3) * 0.3 - 0.3, 0.75, 2.4]}>
          <sphereGeometry args={[0.1, 12, 12]} />
          <meshStandardMaterial color={COLORS.warn} emissive={COLORS.warn} emissiveIntensity={0.8} />
        </mesh>
      ))}
      <OrbitControls enablePan={false} minDistance={8} maxDistance={24} maxPolarAngle={Math.PI / 2.2} />
    </>
  );
}

export default function ModelLab(props: {
  tasks: TaskSummary[]; state: LabState; selectedTask: string | null; selectedLane: Lane; onSelect: (id: string, lane: Lane) => void;
}) {
  const reducedMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  return (
    <Canvas camera={{ position: [0, 9.5, 12.5], fov: 45 }} dpr={[1, 1.75]} gl={{ preserveDrawingBuffer: true }} frameloop={reducedMotion ? "demand" : "always"}>
      <Scene {...props} reducedMotion={Boolean(reducedMotion)} />
    </Canvas>
  );
}
