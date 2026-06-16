import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { VRButton } from "three/examples/jsm/webxr/VRButton.js";

interface VideoPlayerProps {
  streamStatusCallback: (status: boolean) => void;
  onStatsUpdate: (stats: { fps: number; latency: number }) => void;
}

const normalizeBackendHttpUrl = () => {
  let raw = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000").trim();
  
  // Automatically fix common typos like "https//domain.com"
  if (raw.startsWith("https//")) {
    raw = "https://" + raw.substring(7);
  } else if (raw.startsWith("http//")) {
    raw = "http://" + raw.substring(6);
  }
  
  const withProtocol = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
  return withProtocol.replace(/\/+$/, "");
};

export default function VideoPlayer({ streamStatusCallback, onStatsUpdate }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let pc = new RTCPeerConnection();
    let statsInterval: NodeJS.Timeout;
    let renderer: THREE.WebGLRenderer | null = null;

    const container = containerRef.current;
    const video = videoRef.current;

    if (!container || !video) return;

    // 1. Setup Three.js Scene
    const scene = new THREE.Scene();

    // Camera: Field of View, Aspect Ratio, Near, Far
    const camera = new THREE.PerspectiveCamera(
      75,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0, 0); // Center of the sphere

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.xr.enabled = true; // Enable WebXR VR
    container.appendChild(renderer.domElement);

    // VR Button integration
    const vrButton = VRButton.createButton(renderer);
    // Custom style of the VR Button
    vrButton.style.position = "absolute";
    vrButton.style.bottom = "16px";
    vrButton.style.left = "50%";
    vrButton.style.transform = "translateX(-50%)";
    vrButton.style.backgroundColor = "#18181b";
    vrButton.style.border = "1px solid #27272a";
    vrButton.style.borderRadius = "6px";
    vrButton.style.color = "#ffffff";
    vrButton.style.fontFamily = "inherit";
    vrButton.style.fontSize = "13px";
    vrButton.style.fontWeight = "600";
    vrButton.style.padding = "10px 20px";
    vrButton.style.cursor = "pointer";
    vrButton.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)";
    vrButton.style.transition = "all 0.2s ease";
    vrButton.style.zIndex = "40";
    
    // Add hover styles to VR Button
    const onMouseOver = () => {
      vrButton.style.backgroundColor = "#27272a";
      vrButton.style.transform = "translateX(-50%) scale(1.05)";
    };
    const onMouseOut = () => {
      vrButton.style.backgroundColor = "#18181b";
      vrButton.style.transform = "translateX(-50%) scale(1)";
    };

    vrButton.addEventListener("mouseover", onMouseOver);
    vrButton.addEventListener("mouseout", onMouseOut);

    container.appendChild(vrButton);

    // 2. Create the 360-degree Sphere
    const geometry = new THREE.SphereGeometry(500, 60, 40);
    // Invert the sphere geometry so the textures are mapped to the inside
    geometry.scale(-1, 1, 1);

    // Create the Video Texture
    const texture = new THREE.VideoTexture(video);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;

    // Create material
    const material = new THREE.MeshBasicMaterial({ map: texture });

    // Create mesh
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    // 3. OrbitControls for Desktop navigation
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableZoom = true;
    controls.enablePan = false;
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.rotateSpeed = -0.25; // Drag direction matches natural pan
    controls.minDistance = 1;
    controls.maxDistance = 100;

    // 4. WebRTC setup
    const startWebRTC = async () => {
      try {
        pc.addTransceiver("video", { direction: "recvonly" });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const backendHttpUrl = normalizeBackendHttpUrl();
        const response = await fetch(`${backendHttpUrl}/offer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: pc.localDescription?.sdp,
            type: pc.localDescription?.type,
          }),
        });

        if (!response.ok) throw new Error("Failed to connect to video stream");

        const answer = await response.json();
        await pc.setRemoteDescription(answer);

        // Start collecting WebRTC statistics
        statsInterval = setInterval(async () => {
          try {
            const statsObj = await pc.getStats();
            let currentFps = 0;
            let currentLatency = 0;
            
            statsObj.forEach((report) => {
              if (report.type === "inbound-rtp" && report.kind === "video") {
                currentFps = report.framesPerSecond || 0;
              }
              if (report.type === "candidate-pair" && report.state === "succeeded") {
                currentLatency = report.currentRoundTripTime ? report.currentRoundTripTime * 1000 : 0;
              }
            });
            
            onStatsUpdate({ fps: currentFps, latency: currentLatency });
          } catch (e) {}
        }, 1000);

      } catch (err: any) {
        setError(err.message);
        streamStatusCallback(false);
      }
    };

    pc.ontrack = (event) => {
      if (video) {
        video.srcObject = event.streams[0];
        video.play().catch((e) => console.log("Video playback delayed", e));
        streamStatusCallback(true);
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
        streamStatusCallback(false);
      }
    };

    startWebRTC();

    // 5. Handle resizing of the container
    const handleResize = () => {
      if (!container || !renderer) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    window.addEventListener("resize", handleResize);

    // 6. Animation/Render Loop
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer!.render(scene, camera);
    });

    // 7. Cleanup on unmount
    return () => {
      window.removeEventListener("resize", handleResize);
      if (statsInterval) clearInterval(statsInterval);
      
      pc.close();
      streamStatusCallback(false);

      if (renderer) {
        renderer.setAnimationLoop(null);
        renderer.dispose();
        if (container.contains(renderer.domElement)) {
          container.removeChild(renderer.domElement);
        }
        if (container.contains(vrButton)) {
          container.removeChild(vrButton);
        }
      }
      
      vrButton.removeEventListener("mouseover", onMouseOver);
      vrButton.removeEventListener("mouseout", onMouseOut);
      geometry.dispose();
      material.dispose();
      texture.dispose();
    };
  }, []);

  return (
    <div className="relative w-full aspect-video bg-zinc-950 rounded-xl overflow-hidden border border-zinc-200 shadow-md">
      {/* Hidden video element that WebRTC streams into */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ display: "none" }}
      />
      
      {/* Three.js Canvas Container */}
      <div 
        ref={containerRef} 
        className="w-full h-full relative" 
      />

      {/* 360 & VR UI Overlay HUD */}
      <div className="absolute top-4 left-4 pointer-events-none bg-white/95 backdrop-blur-sm border border-zinc-200/80 rounded-lg p-2 px-3 text-xs text-zinc-800 font-semibold flex items-center gap-2 z-10 shadow-sm">
        <span className="w-2 h-2 rounded-full bg-zinc-900 animate-pulse" />
        <span>360° VR View Active</span>
      </div>

      <div className="absolute top-4 right-4 pointer-events-none bg-white/95 backdrop-blur-sm border border-zinc-200/80 rounded-lg p-2 px-3 text-xs text-zinc-600 font-semibold z-10 shadow-sm">
        <span>Drag to pan | Scroll to zoom</span>
      </div>

      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-rose-600 bg-white/90 z-50">
          <p className="font-semibold">Error: {error}</p>
        </div>
      )}
    </div>
  );
}
