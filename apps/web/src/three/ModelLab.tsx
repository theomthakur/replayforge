import { ContactShadows, Html, OrbitControls, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import type { Group } from "three";

import type { Lane, TaskSummary } from "../api/types";
import { caseKey, type CaseStage, type LabState } from "../features/experiments/labState";

const COLOR = {
  baseline: "#42c6d9", candidate: "#85c95b", waiting: "#8390a1", warn: "#e9a23b",
  fail: "#e46755", ok: "#55c6a6", ink: "#18202a", wall: "#d9d4c8", floor: "#b8b3a7",
};

const STAGE_X: Record<CaseStage, number> = {
  queued: -6.7, provisioning: -4.7, reasoning: -3.5, tool_execution: -2.0,
  grading: 0.8, passed: 3.2, failed: 3.2,
};

function stageColor(stage: CaseStage, lane: Lane): string {
  if (stage === "passed") return COLOR.ok;
  if (stage === "failed") return COLOR.fail;
  if (stage === "queued") return COLOR.waiting;
  return COLOR[lane];
}

function WorkPacket({ task, lane, index, count, state, selected, reducedMotion, onSelect }: {
  task: TaskSummary; lane: Lane; index: number; count: number; state: LabState;
  selected: boolean; reducedMotion: boolean; onSelect: (id: string, lane: Lane) => void;
}) {
  const ref = useRef<Group>(null);
  const current = state.cases[caseKey(task.id, lane)];
  const stage: CaseStage = current?.stage ?? "queued";
  const laneZ = lane === "baseline" ? -2.25 : 2.25;
  const spread = (index - (count - 1) / 2) * 0.22;
  const target: [number, number, number] = [STAGE_X[stage], 0.28, laneZ + spread];
  const active = ["provisioning", "reasoning", "tool_execution", "grading"].includes(stage);
  const color = stageColor(stage, lane);

  useFrame((clock, delta) => {
    const group = ref.current;
    if (!group) return;
    const lift = active && !reducedMotion ? Math.sin(clock.clock.elapsedTime * 3 + index) * 0.04 : 0;
    const k = reducedMotion ? 1 : Math.min(1, delta * 4);
    group.position.x += (target[0] - group.position.x) * k;
    group.position.y += (target[1] + lift - group.position.y) * k;
    group.position.z += (target[2] - group.position.z) * k;
  });

  return (
    <group ref={ref} position={target} scale={selected ? 1.35 : 1} onClick={(event) => { event.stopPropagation(); onSelect(task.id, lane); }}
      onPointerOver={() => { document.body.style.cursor = "pointer"; }} onPointerOut={() => { document.body.style.cursor = "default"; }}>
      <RoundedBox args={[0.46, task.critical ? 0.22 : 0.15, 0.32]} radius={0.035} smoothness={2}>
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={active || selected ? 0.55 : 0.12} roughness={0.35} />
      </RoundedBox>
      <mesh position={[0, 0.14, 0]}><boxGeometry args={[0.22, 0.025, 0.08]} /><meshStandardMaterial color="#f6f1e7" /></mesh>
      {task.critical && <mesh position={[0.18, 0.14, -0.1]}><sphereGeometry args={[0.035, 8, 8]} /><meshStandardMaterial color={COLOR.warn} emissive={COLOR.warn} /></mesh>}
    </group>
  );
}

function Monitor({ color, active = false }: { color: string; active?: boolean }) {
  return (
    <group>
      <RoundedBox args={[0.68, 0.43, 0.07]} radius={0.025} smoothness={2} position={[0, 0.55, 0]}>
        <meshStandardMaterial color="#222b35" metalness={0.45} roughness={0.38} />
      </RoundedBox>
      <mesh position={[0, 0.55, 0.041]}><planeGeometry args={[0.57, 0.32]} /><meshStandardMaterial color={active ? color : "#34404c"} emissive={active ? color : "#202a34"} emissiveIntensity={active ? 0.6 : 0.1} /></mesh>
      <mesh position={[0, 0.29, 0]}><boxGeometry args={[0.08, 0.16, 0.06]} /><meshStandardMaterial color="#333b42" /></mesh>
    </group>
  );
}

function Desk({ position, rotation = 0, color, active, label, detail }: {
  position: [number, number, number]; rotation?: number; color: string; active: boolean; label: string; detail: string;
}) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <RoundedBox args={[1.55, 0.12, 0.72]} radius={0.04} smoothness={2} position={[0, 0.73, 0]}><meshStandardMaterial color="#725a43" roughness={0.65} /></RoundedBox>
      {[-0.62, 0.62].map((x) => <mesh key={x} position={[x, 0.36, 0]}><boxGeometry args={[0.07, 0.7, 0.55]} /><meshStandardMaterial color="#34393d" metalness={0.5} /></mesh>)}
      <group position={[0, 0.72, -0.08]}><Monitor color={color} active={active} /></group>
      <group position={[0, 0, 0.76]} rotation={[0, Math.PI, 0]}>
        <mesh position={[0, 0.54, 0]}><sphereGeometry args={[0.15, 20, 20]} /><meshStandardMaterial color="#d6b08a" roughness={0.8} /></mesh>
        <mesh position={[0, 0.28, 0]}><capsuleGeometry args={[0.18, 0.32, 6, 12]} /><meshStandardMaterial color={color} roughness={0.72} /></mesh>
        <mesh position={[0, 0.1, 0.13]}><boxGeometry args={[0.55, 0.08, 0.48]} /><meshStandardMaterial color="#39414a" /></mesh>
      </group>
      <Html center position={[0, 1.52, 0]} distanceFactor={13} style={{ pointerEvents: "none" }}>
        <div className="world-label"><strong style={{ color }}>{label}</strong><span>{detail}</span></div>
      </Html>
    </group>
  );
}

function ServerRack({ position, color }: { position: [number, number, number]; color: string }) {
  return (
    <group position={position}>
      <RoundedBox args={[0.75, 1.65, 0.6]} radius={0.04} smoothness={2} position={[0, 0.825, 0]}><meshStandardMaterial color="#252c32" metalness={0.7} roughness={0.35} /></RoundedBox>
      {[0.32, 0.56, 0.8, 1.04, 1.28].map((y, i) => <group key={y} position={[0, y, 0.307]}>
        <mesh><boxGeometry args={[0.58, 0.12, 0.02]} /><meshStandardMaterial color="#11171c" /></mesh>
        <mesh position={[-0.21 + (i % 2) * 0.1, 0, 0.015]}><sphereGeometry args={[0.018, 6, 6]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.2} /></mesh>
      </group>)}
    </group>
  );
}

function Room({ decision }: { decision: string | null }) {
  const gateColor = decision === "pass" ? COLOR.ok : decision === "warn" ? COLOR.warn : decision === "block" ? COLOR.fail : COLOR.waiting;
  return (
    <>
      <mesh position={[0, -0.08, 0]} receiveShadow><boxGeometry args={[18.5, 0.15, 10]} /><meshStandardMaterial color={COLOR.floor} roughness={0.92} /></mesh>
      <mesh position={[0, 2.2, -5]} receiveShadow><boxGeometry args={[18.5, 4.4, 0.12]} /><meshStandardMaterial color={COLOR.wall} roughness={0.88} /></mesh>
      <mesh position={[-9.2, 2.2, 0]} receiveShadow><boxGeometry args={[0.12, 4.4, 10]} /><meshStandardMaterial color="#c7c2b6" roughness={0.9} /></mesh>
      {[-6.8, -4.5, -2.2, 0.1, 2.4, 4.7].map((x) => <mesh key={x} position={[x, 2.75, -4.93]}><planeGeometry args={[1.6, 1.65]} /><meshStandardMaterial color="#9bc7d0" emissive="#b9dce2" emissiveIntensity={0.15} roughness={0.2} /></mesh>)}
      {[[-5.5, -0.1], [-1.2, -0.1], [3.1, -0.1]].map(([x, z]) => <mesh key={x} position={[x, 0.012, z]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[3.2, 0.025]} /><meshStandardMaterial color="#786e62" /></mesh>)}
      <group position={[7.75, 0, 0]}>
        <mesh position={[0, 1.3, 0]}><torusGeometry args={[0.75, 0.1, 16, 48]} /><meshStandardMaterial color={gateColor} emissive={gateColor} emissiveIntensity={0.65} metalness={0.5} /></mesh>
        <mesh position={[0, 0.65, 0]}><boxGeometry args={[1.75, 1.3, 0.22]} /><meshStandardMaterial color="#30383e" metalness={0.55} /></mesh>
        <Html center position={[0, 2.55, 0]} distanceFactor={13} style={{ pointerEvents: "none" }}><div className="world-label"><strong style={{ color: gateColor }}>Release gate</strong><span>{decision?.toUpperCase() ?? "AWAITING POLICY"}</span></div></Html>
      </group>
    </>
  );
}

function Scene({ tasks, state, selectedTask, selectedLane, reducedMotion, onSelect }: {
  tasks: TaskSummary[]; state: LabState; selectedTask: string | null; selectedLane: Lane;
  reducedMotion: boolean; onSelect: (id: string, lane: Lane) => void;
}) {
  const activity = useMemo(() => {
    const all = Object.values(state.cases);
    return {
      baseline: all.filter((item) => item.lane === "baseline" && !["queued", "passed", "failed"].includes(item.stage)).length,
      candidate: all.filter((item) => item.lane === "candidate" && !["queued", "passed", "failed"].includes(item.stage)).length,
      grading: all.some((item) => item.stage === "grading"),
    };
  }, [state.cases]);
  return (
    <>
      <color attach="background" args={["#c8d1cf"]} />
      <fog attach="fog" args={["#c8d1cf", 17, 30]} />
      <ambientLight intensity={0.75} />
      <hemisphereLight args={["#dce9e8", "#4d463d", 1.1]} />
      <directionalLight position={[4, 11, 7]} intensity={1.5} castShadow shadow-mapSize={[1024, 1024]} />
      <Room decision={state.decision} />
      <ServerRack position={[-8.25, 0, -3.65]} color={COLOR.baseline} />
      <ServerRack position={[-7.35, 0, -3.65]} color={COLOR.candidate} />
      <Desk position={[-4.7, 0, -2.75]} color={COLOR.baseline} active={activity.baseline > 0} label="Baseline engineer" detail={`${activity.baseline} active cases`} />
      <Desk position={[-4.7, 0, 2.75]} rotation={Math.PI} color={COLOR.candidate} active={activity.candidate > 0} label="NVIDIA engineer" detail={`${activity.candidate} active cases`} />
      <Desk position={[0.7, 0, 0]} rotation={Math.PI / 2} color="#596b7c" active={activity.grading} label="Test engineer" detail="deterministic test bench" />
      <Desk position={[4.9, 0, 2.8]} rotation={Math.PI} color={COLOR.warn} active={state.investigating.length > 0} label="Investigator" detail={`${Object.keys(state.findings).length} findings`} />
      <Desk position={[4.9, 0, -2.8]} color="#8e79bd" active={state.status === "deciding"} label="Policy officer" detail="stored release rules" />
      {tasks.map((task, index) => (["baseline", "candidate"] as Lane[]).map((lane) => (
        <WorkPacket key={caseKey(task.id, lane)} task={task} lane={lane} index={index} count={tasks.length} state={state}
          selected={selectedTask === task.id && selectedLane === lane} reducedMotion={reducedMotion} onSelect={onSelect} />
      )))}
      <ContactShadows position={[0, 0.02, 0]} opacity={0.34} scale={22} blur={2.8} far={5} />
      <OrbitControls makeDefault enablePan={false} target={[0, 0.7, 0]} minDistance={10} maxDistance={24} minPolarAngle={0.65} maxPolarAngle={1.35} />
    </>
  );
}

export default function ModelLab(props: {
  tasks: TaskSummary[]; state: LabState; selectedTask: string | null; selectedLane: Lane;
  onSelect: (id: string, lane: Lane) => void;
}) {
  const reducedMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  return (
    <Canvas shadows camera={{ position: [11.5, 10.5, 13.5], fov: 40 }} dpr={[1, 1.6]} gl={{ preserveDrawingBuffer: true, antialias: true }} frameloop={reducedMotion ? "demand" : "always"}>
      <Scene {...props} reducedMotion={Boolean(reducedMotion)} />
    </Canvas>
  );
}
