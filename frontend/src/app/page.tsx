"use client"

import { useEffect, useState, useRef, useCallback } from "react";
import VideoPlayer from "@/components/VideoPlayer";
import ControlPanel from "@/components/ControlPanel";
import TelemetryPanel from "@/components/TelemetryPanel";
import StatusIndicators from "@/components/StatusIndicators";
import Joystick from "@/components/Joystick";
import RobotArmVisualizer from "@/components/RobotArmVisualizer";

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

export default function Home() {
  const [wsStatus, setWsStatus] = useState("Disconnected");
  const [cameraStatus, setCameraStatus] = useState(false);
  const [position, setPosition] = useState<any>({});
  const [speed, setSpeed] = useState(25);
  const [stats, setStats] = useState({ fps: 0, latency: 0, controlLatency: 0 });
  const [lockNeedle, setLockNeedle] = useState(false);
  const [needleLength, setNeedleLength] = useState(50);
  const [targetX, setTargetX] = useState("");
  const [targetY, setTargetY] = useState("");
  const [activeTab, setActiveTab] = useState<"video" | "twin">("video");
  
  const wsRef = useRef<WebSocket | null>(null);
  const activeKeys = useRef<Set<string>>(new Set());
  const activeMotionRef = useRef<string | null>(null);

  useEffect(() => {
    const backendHttpUrl = normalizeBackendHttpUrl();
    const backendWsUrl = backendHttpUrl.startsWith("https://")
      ? backendHttpUrl.replace("https://", "wss://")
      : backendHttpUrl.replace("http://", "ws://");

    const connectWs = () => {
      const ws = new WebSocket(`${backendWsUrl}/ws`);
      
      ws.onopen = () => {
        setWsStatus("Connected");
        ws.send(JSON.stringify({ command: "speed", speed: 25 }));
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "feedback") {
            setPosition(data.data);
            if (data.timestamp) {
              const currentLatency = Date.now() - data.timestamp;
              setStats((prev) => ({ ...prev, controlLatency: currentLatency }));
            }
          }
        } catch (e) {}
      };

      ws.onclose = () => {
        setWsStatus("Disconnected");
        setTimeout(connectWs, 2000); // Auto reconnect
      };

      ws.onerror = () => {
        setWsStatus("Disconnected");
      };

      wsRef.current = ws;
    };

    connectWs();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const sendCommand = useCallback((cmd: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const cmdWithTimestamp = { ...cmd, timestamp: Date.now() };
      wsRef.current.send(JSON.stringify(cmdWithTimestamp));
    }
  }, []);

  const handleVideoStatsUpdate = useCallback((videoStats: { fps: number; latency: number }) => {
    setStats((prev) => ({
      ...prev,
      fps: videoStats.fps,
      latency: videoStats.latency,
    }));
  }, []);

  const handleExecuteMove = useCallback(() => {
    if (!targetX || !targetY) return;
    sendCommand({
      command: "move_to",
      x: parseFloat(targetX),
      y: parseFloat(targetY)
    });
  }, [targetX, targetY, sendCommand]);

  const stopRobot = useCallback(() => {
    if (activeMotionRef.current !== null) {
      sendCommand({ command: "stop", lock_needle: lockNeedle, needle_length: needleLength });
      activeMotionRef.current = null;
    }
  }, [sendCommand, lockNeedle, needleLength]);

  const emergencyStop = useCallback(() => {
    sendCommand({ command: "stop" });
    activeMotionRef.current = null;
  }, [sendCommand]);

  const startContinuousCommand = useCallback((motionKey: string, cmd: any) => {
    if (activeMotionRef.current === motionKey) {
      return;
    }

    if (activeMotionRef.current !== null) {
      sendCommand({ command: "stop" });
    }

    activeMotionRef.current = motionKey;
    sendCommand(cmd);
  }, [sendCommand]);

  const startJogJoint = useCallback((joint: number, direction: string) => {
    const motionKey = `joint:${joint}:${direction}`;
    const cmd = { command: "joint", joint, direction, lock_needle: lockNeedle, needle_length: needleLength };
    startContinuousCommand(motionKey, cmd);
  }, [startContinuousCommand, lockNeedle, needleLength]);

  const startJogCartesian = useCallback((axis: string, direction: string) => {
    const motionKey = `cartesian:${axis}:${direction}`;
    const cmd = { command: "cartesian", axis, direction };
    startContinuousCommand(motionKey, cmd);
  }, [startContinuousCommand]);

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed);
    sendCommand({ command: "speed", speed: newSpeed });
  };

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (activeKeys.current.has(e.code)) return; // Prevent repeat triggers on hold
      activeKeys.current.add(e.code);

      if (e.code === "Space") {
        e.preventDefault();
        emergencyStop();
        return;
      }

      const key = e.key.toLowerCase();
      const isShift = e.shiftKey;
      
      // Cartesian Mapping
      if (key === 'w') startJogCartesian("Y", "+");
      else if (key === 's') startJogCartesian("Y", "-");
      else if (key === 'a') startJogCartesian("X", "-");
      else if (key === 'd') startJogCartesian("X", "+");
      else if (key === 'q') startJogCartesian("Z", "+");
      else if (key === 'e') startJogCartesian("Z", "-");

      // Joint Mapping
      const jointNum = parseInt(key);
      if (jointNum >= 1 && jointNum <= 6) {
        startJogJoint(jointNum, isShift ? "-" : "+");
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      activeKeys.current.delete(e.code);
      stopRobot();
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [startJogCartesian, startJogJoint, stopRobot, emergencyStop]);

  // Joystick handling
  const handleJoystickMove = (x: number, y: number) => {
    if (Math.abs(x) < 0.1 && Math.abs(y) < 0.1) {
      stopRobot();
      return;
    }
    
    if (Math.abs(x) > Math.abs(y)) {
      startJogCartesian("X", x > 0 ? "+" : "-");
    } else {
      startJogCartesian("Y", y > 0 ? "-" : "+");
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 p-4 md:p-6 font-sans">
      <div className="max-w-7xl mx-auto space-y-6">
        
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-2 pb-4 border-b border-zinc-200">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-zinc-950">
              AR4 Teleoperation Control
            </h1>
            <p className="text-zinc-500 text-sm mt-1">Industrial Robotics Interface</p>
          </div>
          <StatusIndicators 
            wsStatus={wsStatus} 
            cameraStatus={cameraStatus} 
            robotState={position?.mode || "Unknown Mode"} 
          />
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Main Content: Video & Telemetry */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            {/* View Tab Selector */}
            <div className="flex bg-zinc-200/50 p-1 rounded-xl w-fit border border-zinc-300/40">
              <button 
                onClick={() => setActiveTab("video")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all duration-200 flex items-center gap-2 ${
                  activeTab === "video" 
                    ? "bg-white text-zinc-950 shadow-sm" 
                    : "text-zinc-600 hover:text-zinc-900"
                }`}
              >
                📹 360° Live Camera
              </button>
              <button 
                onClick={() => setActiveTab("twin")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all duration-200 flex items-center gap-2 ${
                  activeTab === "twin" 
                    ? "bg-white text-zinc-950 shadow-sm" 
                    : "text-zinc-600 hover:text-zinc-900"
                }`}
              >
                🤖 3D Digital Twin
              </button>
            </div>

            {activeTab === "video" ? (
              <VideoPlayer streamStatusCallback={setCameraStatus} onStatsUpdate={handleVideoStatsUpdate} />
            ) : (
              <RobotArmVisualizer position={position} />
            )}
            <TelemetryPanel position={position} speed={speed} stats={stats} />
          </div>

          {/* Sidebar: Controls */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            
            <ControlPanel 
              onJogJoint={startJogJoint} 
              onJogCartesian={startJogCartesian} 
              onStop={stopRobot}
              speed={speed}
              onSpeedChange={handleSpeedChange}
              lockNeedle={lockNeedle}
            />

            {/* Needle Control Panel */}
            <div className="bg-white rounded-xl p-6 border border-zinc-200 flex flex-col gap-4 shadow-sm text-zinc-900">
              <div className="flex justify-between items-center border-b border-zinc-150 pb-2.5 mb-1">
                <h3 className="text-sm font-bold text-zinc-800 flex items-center gap-1.5">
                  📍 Needle Positioner
                </h3>
                {position?.moving_to_coords && (
                  <span className="flex h-2.5 w-2.5 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                  </span>
                )}
              </div>

              {/* Lock Needle Toggle Button */}
              <button
                onClick={() => setLockNeedle(prev => !prev)}
                className={`flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-bold text-sm transition-all active:scale-[0.98] cursor-pointer shadow-xs border ${
                  lockNeedle
                    ? "bg-zinc-900 text-white border-zinc-955 hover:bg-zinc-850"
                    : "bg-zinc-100 text-zinc-700 border-zinc-200 hover:bg-zinc-205"
                }`}
              >
                {lockNeedle ? "🔒 Needle Direction Locked" : "🔓 Lock Needle Direction"}
              </button>

              {/* Needle Length Configuration Slider */}
              <div className="flex flex-col gap-1.5 mt-2 bg-zinc-50 border border-zinc-200 rounded-lg p-3">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-zinc-500">Needle Offset Length</label>
                  <span className="font-mono text-xs text-zinc-800 font-bold bg-zinc-200/60 px-1.5 py-0.5 rounded">{needleLength} units</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="150"
                  value={needleLength}
                  onChange={(e) => setNeedleLength(parseInt(e.target.value))}
                  className="w-full accent-zinc-900 h-2 bg-zinc-200 rounded-lg appearance-none cursor-pointer"
                />
              </div>

              {/* Coordinate Fields */}
              <div className={`transition-all duration-300 overflow-hidden ${lockNeedle ? "max-h-60 opacity-100 mt-1" : "max-h-0 opacity-0 pointer-events-none"}`}>
                <div className="space-y-3.5">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-500 mb-1">Target X</label>
                      <input
                        type="number"
                        step="0.1"
                        value={targetX}
                        onChange={(e) => setTargetX(e.target.value)}
                        placeholder="e.g. 15.0"
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-lg py-2 px-3 text-sm font-mono text-zinc-900 focus:outline-hidden focus:border-zinc-500 focus:ring-1 focus:ring-zinc-200 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-500 mb-1">Target Y</label>
                      <input
                        type="number"
                        step="0.1"
                        value={targetY}
                        onChange={(e) => setTargetY(e.target.value)}
                        placeholder="e.g. -10.0"
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-lg py-2 px-3 text-sm font-mono text-zinc-900 focus:outline-hidden focus:border-zinc-500 focus:ring-1 focus:ring-zinc-200 transition-all"
                      />
                    </div>
                  </div>

                  <button
                    onClick={handleExecuteMove}
                    disabled={!targetX || !targetY || position?.moving_to_coords}
                    className={`w-full py-3 rounded-lg font-bold text-sm transition-all active:scale-[0.98] cursor-pointer border shadow-xs ${
                      position?.moving_to_coords
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200 cursor-wait animate-pulse"
                        : (!targetX || !targetY)
                        ? "bg-zinc-100 text-zinc-400 border-zinc-200 cursor-not-allowed"
                        : "bg-zinc-900 text-white border-zinc-950 hover:bg-zinc-800"
                    }`}
                  >
                    {position?.moving_to_coords 
                      ? "Moving to coordinates..." 
                      : "Go to Coordinates (X, Y)"}
                  </button>
                  
                  {position?.moving_to_coords && (
                    <button
                      onClick={emergencyStop}
                      className="w-full py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg font-bold text-xs transition-colors cursor-pointer"
                    >
                      Cancel Movement
                    </button>
                  )}
                </div>
              </div>

              {!lockNeedle && (
                <p className="text-xs text-zinc-400 text-center leading-relaxed">
                  Lock the needle direction to enable coordinate target positioning.
                </p>
              )}
            </div>

            <div className="bg-white rounded-xl p-6 border border-zinc-200 flex justify-center items-center py-10 shadow-sm">
               <Joystick onMove={handleJoystickMove} onStop={stopRobot} label="XY Movement" />
            </div>

            <button
              onPointerDown={emergencyStop}
              className="bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white font-bold text-lg py-5 rounded-xl transition-all shadow-md active:scale-[0.98] uppercase tracking-widest border border-rose-500 cursor-pointer"
            >
              Emergency Stop (Space)
            </button>

          </div>
        </div>
      </div>
    </div>
  );
}
