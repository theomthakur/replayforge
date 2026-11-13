import { ContactShadows, Html, Line, OrbitControls, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import type { Group, OrthographicCamera } from "three";

import type { Lane, TaskSummary } from "../api/types";
import { caseKey, type CaseStage, type LabState } from "../features/experiments/labState";

const COLOR = {
  baseline: "#268ca0", candidate: "#65a53d", waiting: "#8d9892", warn: "#d28a2f",
  fail: "#cf5848", ok: "#2a9a75", ink: "#25342c", wall: "#f0f0e8", floor: "#d9d6c9",
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

function Operator({ active, shirt, skin, hair }: { active: boolean; shirt: string; skin: string; hair: string }) {
  const leftArm = useRef<Group>(null);
  const rightArm = useRef<Group>(null);
  useFrame((clock) => {
    const movement = active ? Math.sin(clock.clock.elapsedTime * 7) * 0.045 : 0;
    if (leftArm.current) leftArm.current.rotation.x = -0.86 + movement;
    if (rightArm.current) rightArm.current.rotation.x = -0.86 - movement;
  });
  return <group>
    <group position={[0, 0, .12]}>
      <RoundedBox args={[.52, .08, .5]} radius={.04} smoothness={2} position={[0, .18, .05]}><meshStandardMaterial color="#3f474e" roughness={.7} /></RoundedBox>
      <RoundedBox args={[.5, .58, .09]} radius={.04} smoothness={2} position={[0, .48, .29]}><meshStandardMaterial color="#4a535a" roughness={.72} /></RoundedBox>
      <mesh position={[0, -.12, .13]}><cylinderGeometry args={[.055, .055, .55, 12]} /><meshStandardMaterial color="#30373d" metalness={.45} /></mesh>
      <mesh position={[0, -.4, .13]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.045, .045, .55, 12]} /><meshStandardMaterial color="#30373d" metalness={.45} /></mesh>
    </group>
    <mesh position={[0, .74, 0]}><sphereGeometry args={[.16, 24, 20]} /><meshStandardMaterial color={skin} roughness={.82} /></mesh>
    <mesh position={[0, .825, .008]} scale={[1.03, .56, 1.04]}><sphereGeometry args={[.163, 20, 16]} /><meshStandardMaterial color={hair} roughness={.9} /></mesh>
    <mesh position={[0, .66, -.145]}><sphereGeometry args={[.035, 12, 10]} /><meshStandardMaterial color={skin} roughness={.8} /></mesh>
    {[-.057, .057].map((x) => <mesh key={x} position={[x, .755, -.145]}><sphereGeometry args={[.012, 10, 8]} /><meshStandardMaterial color="#26312d" /></mesh>)}
    <mesh position={[0, .675, 0]}><cylinderGeometry args={[.065, .072, .12, 14]} /><meshStandardMaterial color={skin} roughness={.82} /></mesh>
    <mesh position={[0, .46, .015]} scale={[1, 1.05, .72]}><capsuleGeometry args={[.19, .28, 8, 16]} /><meshStandardMaterial color={shirt} roughness={.73} /></mesh>
    {[-.21, .21].map((x, index) => <group key={x} ref={index === 0 ? leftArm : rightArm} position={[x, .5, -.02]} rotation={[-.86, 0, index === 0 ? -.13 : .13]}>
      <mesh position={[0, -.14, 0]}><capsuleGeometry args={[.055, .23, 6, 12]} /><meshStandardMaterial color={shirt} roughness={.75} /></mesh>
      <mesh position={[0, -.31, -.01]}><sphereGeometry args={[.06, 12, 10]} /><meshStandardMaterial color={skin} roughness={.82} /></mesh>
    </group>)}
    {[-.095, .095].map((x) => <group key={x} position={[x, .2, .02]} rotation={[-.32, 0, 0]}>
      <mesh position={[0, -.15, 0]}><capsuleGeometry args={[.07, .22, 6, 12]} /><meshStandardMaterial color="#303a43" roughness={.82} /></mesh>
      <mesh position={[0, -.34, -.07]}><boxGeometry args={[.14, .08, .25]} /><meshStandardMaterial color="#20282d" roughness={.7} /></mesh>
    </group>)}
  </group>;
}

function Desk({ position, rotation = 0, color, active, label, detail, operator }: {
  position: [number, number, number]; rotation?: number; color: string; active: boolean; label: string; detail: string;
  operator: { skin: string; hair: string; shirt: string };
}) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <RoundedBox args={[1.55, 0.12, 0.72]} radius={0.04} smoothness={2} position={[0, 0.73, 0]}><meshStandardMaterial color="#725a43" roughness={0.65} /></RoundedBox>
      {[-0.62, 0.62].map((x) => <mesh key={x} position={[x, 0.36, 0]}><boxGeometry args={[0.07, 0.7, 0.55]} /><meshStandardMaterial color="#34393d" metalness={0.5} /></mesh>)}
      <group position={[0, 0.72, -0.08]}><Monitor color={color} active={active} /></group>
      <group position={[0, 0, 0.8]} rotation={[0, Math.PI, 0]}><Operator active={active} {...operator} /></group>
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

function SignPlate({ position, label, detail, color = "#315d3f", brand = false }: {
  position: [number, number, number]; label: string; detail: string; color?: string; brand?: boolean;
}) {
  return <group position={position}>
    <RoundedBox args={[brand ? 3.45 : 2.05, brand ? 0.72 : 0.58, 0.1]} radius={0.045} smoothness={2}>
      <meshStandardMaterial color="#fbfcf8" roughness={0.62} metalness={0.06} />
    </RoundedBox>
    <mesh position={[-(brand ? 1.64 : .94), 0, .058]}><boxGeometry args={[0.08, brand ? .56 : .43, .025]} /><meshStandardMaterial color={color} /></mesh>
    <Html center position={[0.05, 0, 0.075]} distanceFactor={13} style={{ pointerEvents: "none" }}>
      <div className={`room-sign ${brand ? "brand-sign" : ""}`} style={{ borderTopColor: color }}><strong>{label}</strong><span>{detail}</span></div>
    </Html>
  </group>;
}

function Plant({ position }: { position: [number, number, number] }) {
  return <group position={position}>
    <mesh position={[0, .22, 0]}><cylinderGeometry args={[.22, .16, .44, 16]} /><meshStandardMaterial color="#b77b52" roughness={.82} /></mesh>
    {[-.2, 0, .2].map((x, index) => <mesh key={x} position={[x, .65 + index * .06, 0]} rotation={[0, 0, x * 1.8]}>
      <sphereGeometry args={[.25, 12, 10]} /><meshStandardMaterial color={index === 1 ? "#4e864f" : "#6a9d5f"} roughness={.9} />
    </mesh>)}
  </group>;
}

function StationZone({ position, size, color, selected = false }: {
  position: [number, number, number]; size: [number, number]; color: string; selected?: boolean;
}) {
  return <group position={position}>
    <RoundedBox args={[size[0], .055, size[1]]} radius={.12} smoothness={3} receiveShadow>
      <meshStandardMaterial color={selected ? color : "#e8ece4"} roughness={.9} />
    </RoundedBox>
    <Line points={[
      [-size[0] / 2 + .12, .035, -size[1] / 2 + .12], [size[0] / 2 - .12, .035, -size[1] / 2 + .12],
      [size[0] / 2 - .12, .035, size[1] / 2 - .12], [-size[0] / 2 + .12, .035, size[1] / 2 - .12],
      [-size[0] / 2 + .12, .035, -size[1] / 2 + .12],
    ]} color={color} lineWidth={selected ? 2 : 1} transparent opacity={selected ? .8 : .42} />
  </group>;
}

function EvidenceRoutes({ gateColor }: { gateColor: string }) {
  const route = (points: [number, number, number][], color: string) => <Line points={points} color={color} lineWidth={1.35} dashed dashSize={.18} gapSize={.12} transparent opacity={.58} />;
  return <group>
    {route([[-4.7, .09, -2.75], [-1.4, .09, -2.75], [.7, .09, 0]], COLOR.baseline)}
    {route([[-4.7, .09, 2.75], [-1.4, .09, 2.75], [.7, .09, 0]], COLOR.candidate)}
    {route([[.7, .09, 0], [3.2, .09, 0], [4.9, .09, 2.8]], COLOR.warn)}
    {route([[4.9, .09, 2.8], [6.25, .09, 1.4], [7.75, .09, 0]], gateColor)}
    {route([[4.9, .09, -2.8], [6.25, .09, -1.4], [7.75, .09, 0]], "#8e79bd")}
  </group>;
}

function Room({ decision }: { decision: string | null }) {
  const gateColor = decision === "pass" ? COLOR.ok : decision === "warn" ? COLOR.warn : decision === "block" ? COLOR.fail : COLOR.waiting;
  return (
    <>
      <mesh position={[0, -0.08, 0]} receiveShadow><boxGeometry args={[18.5, 0.15, 10]} /><meshStandardMaterial color={COLOR.floor} roughness={0.92} /></mesh>
      <mesh position={[0, 2.2, -5]} receiveShadow><boxGeometry args={[18.5, 4.4, 0.12]} /><meshStandardMaterial color={COLOR.wall} roughness={0.88} /></mesh>
      <mesh position={[-9.2, 2.2, 0]} receiveShadow><boxGeometry args={[0.12, 4.4, 10]} /><meshStandardMaterial color="#e5e5dc" roughness={0.9} /></mesh>
      {[-6.8, -4.5, -2.2, 0.1, 2.4, 4.7].map((x) => <mesh key={x} position={[x, 2.75, -4.93]}><planeGeometry args={[1.6, 1.65]} /><meshStandardMaterial color="#9bc7d0" emissive="#b9dce2" emissiveIntensity={0.15} roughness={0.2} /></mesh>)}
      {[-7.25, -3.6, 0, 3.6, 7.25].map((x) => <mesh key={`tile-${x}`} position={[x, .006, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[.018, 9.7]} /><meshStandardMaterial color="#c1bdae" /></mesh>)}
      {[-3.3, 0, 3.3].map((z) => <mesh key={`tile-z-${z}`} position={[0, .007, z]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[18.1, .018]} /><meshStandardMaterial color="#c1bdae" /></mesh>)}
      <mesh position={[-3.4, .015, -2.35]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[6.2, 2.65]} /><meshStandardMaterial color="#d7ecee" transparent opacity={.66} /></mesh>
      <mesh position={[-3.4, .016, 2.35]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[6.2, 2.65]} /><meshStandardMaterial color="#e1efd7" transparent opacity={.72} /></mesh>
      {[[-4.6, 4.15], [0, 4.15], [4.6, 4.15]].map(([x, z]) => <group key={`light-${x}`} position={[x, 4.28, z - 4.15]}>
        <mesh><boxGeometry args={[2.2, .08, .48]} /><meshStandardMaterial color="#f8fbf2" emissive="#fffef1" emissiveIntensity={.55} /></mesh>
      </group>)}
      <SignPlate position={[0, 4.02, -4.86]} label="ReplayForge Evaluation Lab" detail="Paired evidence · deterministic release decisions" color="#4d8f32" brand />
      <SignPlate position={[-5.9, 1.05, -4.84]} label="Baseline Lane" detail="Current production model" color={COLOR.baseline} />
      <SignPlate position={[-2.9, 1.05, -4.84]} label="Candidate Lane" detail="Configured candidate model" color={COLOR.candidate} />
      <SignPlate position={[1.05, 1.05, -4.84]} label="Test Bench" detail="Deterministic graders only" color="#526d79" />
      <SignPlate position={[4.45, 1.05, -4.84]} label="Investigation" detail="Referenced failure taxonomy" color={COLOR.warn} />
      <Plant position={[-8.35, 0, 4.15]} /><Plant position={[8.35, 0, -4.05]} />
      <group position={[7.75, 0, 0]}>
        <mesh position={[0, 1.3, 0]}><torusGeometry args={[0.75, 0.1, 16, 48]} /><meshStandardMaterial color={gateColor} emissive={gateColor} emissiveIntensity={0.65} metalness={0.5} /></mesh>
        <mesh position={[0, 0.65, 0]}><boxGeometry args={[1.75, 1.3, 0.22]} /><meshStandardMaterial color="#30383e" metalness={0.55} /></mesh>
        <Html center position={[0, 2.55, 0]} distanceFactor={13} style={{ pointerEvents: "none" }}><div className="room-sign"><strong style={{ color: gateColor }}>Release gate</strong><span>{decision?.toUpperCase() ?? "AWAITING POLICY"}</span></div></Html>
      </group>
    </>
  );
}

function CameraRig() {
  const controls = useRef<any>(null);
  const { camera, size } = useThree();
  useEffect(() => {
    const orthographic = camera as OrthographicCamera;
    orthographic.zoom = Math.min(size.width / 22.5, size.height / 13.5);
    orthographic.updateProjectionMatrix();
    camera.position.set(12, 15, 18);
    controls.current?.target.set(0, .7, 0);
    controls.current?.update();
  }, [camera, size]);
  return <OrbitControls ref={controls} makeDefault enablePan={false} enableZoom={false} target={[0, .7, 0]} minPolarAngle={.45} maxPolarAngle={1.08} minAzimuthAngle={-.75} maxAzimuthAngle={1.15} />;
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
  const gateColor = state.decision === "pass" ? COLOR.ok : state.decision === "warn" ? COLOR.warn : state.decision === "block" ? COLOR.fail : COLOR.waiting;
  return (
    <>
      <color attach="background" args={["#dfe9e2"]} />
      <fog attach="fog" args={["#dfe9e2", 18, 31]} />
      <ambientLight intensity={0.92} />
      <hemisphereLight args={["#edf5ef", "#6e675c", 1.18]} />
      <directionalLight position={[4, 11, 7]} intensity={1.5} castShadow shadow-mapSize={[1024, 1024]} />
      <Room decision={state.decision} />
      <StationZone position={[-4.7, .035, -2.75]} size={[3.1, 2.35]} color={COLOR.baseline} selected={activity.baseline > 0} />
      <StationZone position={[-4.7, .035, 2.75]} size={[3.1, 2.35]} color={COLOR.candidate} selected={activity.candidate > 0} />
      <StationZone position={[-.15, .035, 0]} size={[3.7, 3.2]} color="#596b7c" selected={activity.grading} />
      <StationZone position={[4.9, .035, 2.8]} size={[2.85, 2.25]} color={COLOR.warn} selected={state.investigating.length > 0} />
      <StationZone position={[4.9, .035, -2.8]} size={[2.85, 2.25]} color="#8e79bd" selected={state.status === "deciding"} />
      <EvidenceRoutes gateColor={gateColor} />
      <ServerRack position={[-8.25, 0, -3.65]} color={COLOR.baseline} />
      <ServerRack position={[-7.35, 0, -3.65]} color={COLOR.candidate} />
      <Desk position={[-4.7, 0, -2.75]} color={COLOR.baseline} active={activity.baseline > 0} label="Baseline coding agent" detail={`${activity.baseline} active cases`} operator={{ skin: "#bd805d", hair: "#27201d", shirt: "#287f91" }} />
      <Desk position={[-4.7, 0, 2.75]} rotation={Math.PI} color={COLOR.candidate} active={activity.candidate > 0} label="Candidate coding agent" detail={`${activity.candidate} active cases`} operator={{ skin: "#e1b18b", hair: "#6c3d25", shirt: "#5c963d" }} />
      <Desk position={[0.7, 0, 0]} rotation={Math.PI / 2} color="#596b7c" active={activity.grading} label="Evidence pipeline" detail="deterministic test bench" operator={{ skin: "#8b5b42", hair: "#181818", shirt: "#596b7c" }} />
      <Desk position={[4.9, 0, 2.8]} rotation={Math.PI} color={COLOR.warn} active={state.investigating.length > 0} label="Regression investigator" detail={`${Object.keys(state.findings).length} findings`} operator={{ skin: "#edc7a4", hair: "#a77347", shirt: "#be7727" }} />
      <Desk position={[4.9, 0, -2.8]} color="#8e79bd" active={state.status === "deciding"} label="Release guardian" detail="deterministic policy rules" operator={{ skin: "#c9906c", hair: "#3b2925", shirt: "#8069ae" }} />
      {tasks.map((task, index) => (["baseline", "candidate"] as Lane[]).map((lane) => (
        <WorkPacket key={caseKey(task.id, lane)} task={task} lane={lane} index={index} count={tasks.length} state={state}
          selected={selectedTask === task.id && selectedLane === lane} reducedMotion={reducedMotion} onSelect={onSelect} />
      )))}
      <ContactShadows position={[0, 0.02, 0]} opacity={0.34} scale={22} blur={2.8} far={5} />
      <CameraRig />
    </>
  );
}

export default function ModelLab(props: {
  tasks: TaskSummary[]; state: LabState; selectedTask: string | null; selectedLane: Lane;
  onSelect: (id: string, lane: Lane) => void;
}) {
  const reducedMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  return (
    <Canvas orthographic shadows camera={{ position: [12, 15, 18], zoom: 42, near: .1, far: 100 }} dpr={[1, 1.6]} gl={{ preserveDrawingBuffer: true, antialias: true }} frameloop={reducedMotion ? "demand" : "always"}>
      <Scene {...props} reducedMotion={Boolean(reducedMotion)} />
    </Canvas>
  );
}
