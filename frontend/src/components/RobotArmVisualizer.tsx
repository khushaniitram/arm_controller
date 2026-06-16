import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { RobotTelemetry } from "@/types/telemetry";

interface RobotArmVisualizerProps {
  position: RobotTelemetry;
}

export default function RobotArmVisualizer({ position }: RobotArmVisualizerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  // References to joint meshes for rotation updates
  const jointsRef = useRef<{
    j1: THREE.Group;
    j2: THREE.Group;
    j3: THREE.Group;
    j4: THREE.Group;
    j5: THREE.Group;
    j6: THREE.Group;
    needle: THREE.Mesh;
  } | null>(null);

  // Target angles (in radians) for smooth interpolation (lerp)
  const targetAngles = useRef({
    j1: 0,
    j2: 0,
    j3: 0,
    j4: 0,
    j5: 0,
    j6: 0,
  });

  // Current angles (in radians)
  const currentAngles = useRef({
    j1: 0,
    j2: 0,
    j3: 0,
    j4: 0,
    j5: 0,
    j6: 0,
  });

  // Update target angles when position props change
  useEffect(() => {
    if (!position) return;
    if (position.feedback_ready === false && position.mode !== "Simulation Mode") return;
    targetAngles.current = {
      j1: THREE.MathUtils.degToRad(Number(position.j1 || 0)),
      j2: THREE.MathUtils.degToRad(Number(position.j2 || 0)),
      j3: THREE.MathUtils.degToRad(Number(position.j3 || 0)),
      j4: THREE.MathUtils.degToRad(Number(position.j4 || 0)),
      j5: THREE.MathUtils.degToRad(Number(position.j5 || 0)),
      j6: THREE.MathUtils.degToRad(Number(position.j6 || 0)),
    };
  }, [position]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf1f5f9); // Professional slate-100 background
    sceneRef.current = scene;

    // 2. Camera setup
    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(150, 120, 150);

    // 3. Renderer setup
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 4. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.01; // Don't go below ground
    controlsRef.current = controls;

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7); // Bright ambient lighting
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.7);
    dirLight1.position.set(200, 400, 200);
    dirLight1.castShadow = true;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x94a3b8, 0.3); // Soft blue-slate fill
    dirLight2.position.set(-200, 200, -200);
    scene.add(dirLight2);

    // 6. Floor grid
    const gridHelper = new THREE.GridHelper(300, 30, 0x94a3b8, 0xe2e8f0);
    gridHelper.position.y = -0.1;
    scene.add(gridHelper);

    // 7. Materials
    const metalMaterial = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1, // Clean titanium gray
      roughness: 0.3,
      metalness: 0.8,
    });

    const jointMaterial = new THREE.MeshStandardMaterial({
      color: 0x3b82f6, // Sleek blue joints
      roughness: 0.3,
      metalness: 0.7,
    });

    const needleMaterial = new THREE.MeshStandardMaterial({
      color: 0x0284c7, // Sky blue steel tool
      roughness: 0.2,
      metalness: 0.9,
    });

    // Helper to create joint pivots
    const createPivotGroup = (parent: THREE.Object3D) => {
      const group = new THREE.Group();
      parent.add(group);
      return group;
    };

    // 8. Build Kinematic Robot Chain
    // Root base
    const baseGeo = new THREE.CylinderGeometry(25, 30, 12, 32);
    const baseMesh = new THREE.Mesh(baseGeo, metalMaterial);
    baseMesh.position.y = 6;
    scene.add(baseMesh);

    // J1 pivot group (yaw rotation)
    const j1Group = createPivotGroup(baseMesh);
    j1Group.position.y = 6;

    // Link 1 (vertical column)
    const link1Geo = new THREE.CylinderGeometry(12, 12, 30, 16);
    const link1Mesh = new THREE.Mesh(link1Geo, metalMaterial);
    link1Mesh.position.y = 15;
    j1Group.add(link1Mesh);

    // J2 pivot group (shoulder pitch)
    const j2Group = createPivotGroup(link1Mesh);
    j2Group.position.y = 15;

    // Shoulder cap representation
    const shoulderCapGeo = new THREE.CylinderGeometry(14, 14, 10, 16);
    shoulderCapGeo.rotateX(Math.PI / 2);
    const shoulderCap = new THREE.Mesh(shoulderCapGeo, jointMaterial);
    j2Group.add(shoulderCap);

    // Link 2 (upper arm)
    const link2Geo = new THREE.BoxGeometry(10, 50, 10);
    const link2Mesh = new THREE.Mesh(link2Geo, metalMaterial);
    link2Mesh.position.y = 25; // Offset center up
    j2Group.add(link2Mesh);

    // J3 pivot group (elbow pitch)
    const j3Group = createPivotGroup(link2Mesh);
    j3Group.position.y = 25;

    // Elbow cap representation
    const elbowCapGeo = new THREE.CylinderGeometry(10, 10, 10, 16);
    elbowCapGeo.rotateX(Math.PI / 2);
    const elbowCap = new THREE.Mesh(elbowCapGeo, jointMaterial);
    j3Group.add(elbowCap);

    // Link 3 (forearm)
    const link3Geo = new THREE.BoxGeometry(8, 40, 8);
    const link3Mesh = new THREE.Mesh(link3Geo, metalMaterial);
    link3Mesh.position.y = 20;
    j3Group.add(link3Mesh);

    // J4 pivot group (wrist roll)
    const j4Group = createPivotGroup(link3Mesh);
    j4Group.position.y = 20;

    // Wrist roll connector
    const wristRollGeo = new THREE.CylinderGeometry(8, 8, 10, 16);
    const wristRoll = new THREE.Mesh(wristRollGeo, jointMaterial);
    wristRoll.position.y = 5;
    j4Group.add(wristRoll);

    // J5 pivot group (wrist pitch)
    const j5Group = createPivotGroup(wristRoll);
    j5Group.position.y = 5;

    // Wrist pitch cap
    const wristPitchGeo = new THREE.CylinderGeometry(6, 6, 8, 16);
    wristPitchGeo.rotateX(Math.PI / 2);
    const wristPitch = new THREE.Mesh(wristPitchGeo, jointMaterial);
    j5Group.add(wristPitch);

    // Link 5 (tool flange adapter)
    const link5Geo = new THREE.CylinderGeometry(6, 6, 12, 16);
    const link5Mesh = new THREE.Mesh(link5Geo, metalMaterial);
    link5Mesh.position.y = 6;
    j5Group.add(link5Mesh);

    // J6 pivot group (tool rotation)
    const j6Group = createPivotGroup(link5Mesh);
    j6Group.position.y = 6;

    // Needle tool representation
    const needleGeo = new THREE.CylinderGeometry(1, 1, 35, 16);
    needleGeo.translate(0, 17.5, 0); // Position tip down
    const needle = new THREE.Mesh(needleGeo, needleMaterial);
    j6Group.add(needle);

    // Save joint handles
    jointsRef.current = {
      j1: j1Group,
      j2: j2Group,
      j3: j3Group,
      j4: j4Group,
      j5: j5Group,
      j6: j6Group,
      needle,
    };

    // 9. Animation & Render Loop
    let animationFrameId: number;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Smooth interpolation (lerp) for joint rotations
      const lerpFactor = 0.1;
      const cur = currentAngles.current;
      const tgt = targetAngles.current;

      cur.j1 += (tgt.j1 - cur.j1) * lerpFactor;
      cur.j2 += (tgt.j2 - cur.j2) * lerpFactor;
      cur.j3 += (tgt.j3 - cur.j3) * lerpFactor;
      cur.j4 += (tgt.j4 - cur.j4) * lerpFactor;
      cur.j5 += (tgt.j5 - cur.j5) * lerpFactor;
      cur.j6 += (tgt.j6 - cur.j6) * lerpFactor;

      // Apply rotations to joint groups
      if (jointsRef.current) {
        jointsRef.current.j1.rotation.y = cur.j1;       // Yaw (standard)
        jointsRef.current.j2.rotation.z = -cur.j2;      // Pitch (inverted to match physical forward/backward)
        jointsRef.current.j3.rotation.z = -cur.j3 - Math.PI / 2; // Pitch + 90 deg offset for physical elbow calibration
        jointsRef.current.j4.rotation.y = -cur.j4;      // Roll (inverted)
        jointsRef.current.j5.rotation.z = -cur.j5 - Math.PI / 2; // Pitch + 90 deg offset for physical wrist calibration
        jointsRef.current.j6.rotation.y = -cur.j6;      // Roll (inverted)
      }

      controls.update();
      renderer.render(scene, camera);
    };

    animate();

    // 10. Handle window resize
    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };

    window.addEventListener("resize", handleResize);

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
      if (rendererRef.current && container.contains(rendererRef.current.domElement)) {
        container.removeChild(rendererRef.current.domElement);
      }
      scene.clear();
    };
  }, []);

  return (
    <div className="relative w-full aspect-video bg-slate-100 rounded-xl overflow-hidden border border-zinc-200 shadow-md">
      {/* 3D Canvas container */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Overlay status HUD */}
      <div className="absolute top-4 left-4 pointer-events-none bg-white/95 backdrop-blur-sm border border-zinc-200/80 rounded-lg p-2 px-3 text-xs text-zinc-800 font-semibold flex items-center gap-2 z-10 shadow-sm">
        <span className={`w-2 h-2 rounded-full ${position?.feedback_ready === false && position?.mode !== "Simulation Mode" ? "bg-amber-500" : "bg-blue-500 animate-pulse"}`} />
        <span>{position?.feedback_ready === false && position?.mode !== "Simulation Mode" ? "Waiting for Real Joint Feedback" : "3D Digital Twin Active"}</span>
      </div>

      <div className="absolute top-4 right-4 pointer-events-none bg-white/95 backdrop-blur-sm border border-zinc-200/80 rounded-lg p-2 px-3 text-xs text-zinc-600 font-semibold z-10 shadow-sm">
        <span>Orbit: Left Click + Drag | Pan: Right Click + Drag</span>
      </div>
    </div>
  );
}
