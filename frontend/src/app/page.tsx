"use client"

import { useEffect, useState, useRef, useCallback } from "react";
import VideoPlayer from "@/components/VideoPlayer";
import ControlPanel from "@/components/ControlPanel";
import TelemetryPanel from "@/components/TelemetryPanel";
import StatusIndicators from "@/components/StatusIndicators";
import Joystick from "@/components/Joystick";

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
  const [stats, setStats] = useState({ fps: 0, latency: 0 });
  
  const wsRef = useRef<WebSocket | null>(null);
  const jogIntervalRef = useRef<NodeJS.Timeout | null>(null);
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
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  const stopRobot = useCallback(() => {
    if (jogIntervalRef.current) {
      clearInterval(jogIntervalRef.current);
      jogIntervalRef.current = null;
    }
    if (activeMotionRef.current !== null) {
      sendCommand({ command: "stop" });
      activeMotionRef.current = null;
    }
  }, [sendCommand]);

  const emergencyStop = useCallback(() => {
    if (jogIntervalRef.current) {
      clearInterval(jogIntervalRef.current);
      jogIntervalRef.current = null;
    }
    sendCommand({ command: "stop" });
    activeMotionRef.current = null;
  }, [sendCommand]);

  const startContinuousCommand = useCallback((motionKey: string, cmd: any) => {
    if (activeMotionRef.current === motionKey && jogIntervalRef.current) {
      return;
    }

    if (jogIntervalRef.current) {
      clearInterval(jogIntervalRef.current);
      jogIntervalRef.current = null;
    }

    if (activeMotionRef.current !== null) {
      sendCommand({ command: "stop" });
    }

    activeMotionRef.current = motionKey;
    sendCommand(cmd);
    jogIntervalRef.current = setInterval(() => sendCommand(cmd), 120);
  }, [sendCommand]);

  const startJogJoint = useCallback((joint: number, direction: string) => {
    const motionKey = `joint:${joint}:${direction}`;
    const cmd = { command: "joint", joint, direction };
    startContinuousCommand(motionKey, cmd);
  }, [startContinuousCommand]);

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
      // Only stop if no keys that trigger movement are pressed? Simple approach: just stop.
      // A more robust approach stops only if movement keys are released.
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
    // Only triggering highest axis for simplicity, or we could trigger both.
    // The backend only accepts one axis per cartesian command in the current API.
    // But since we can send commands, we could alternate, or just pick the dominant axis.
    if (Math.abs(x) < 0.1 && Math.abs(y) < 0.1) {
      stopRobot();
      return;
    }
    
    // Pick dominant axis for now since backend jog_cartesian only takes one axis at a time
    if (Math.abs(x) > Math.abs(y)) {
      startJogCartesian("X", x > 0 ? "+" : "-");
    } else {
      startJogCartesian("Y", y > 0 ? "-" : "+"); // invert Y so up is +
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-4 md:p-6 font-sans">
      <div className="max-w-7xl mx-auto space-y-4">
        
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">
              AR4 Teleoperation Control
            </h1>
            <p className="text-slate-400 text-sm mt-1">Industrial Robotics Interface</p>
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
            <VideoPlayer streamStatusCallback={setCameraStatus} onStatsUpdate={setStats} />
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
            />

            <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 flex justify-center items-center py-10">
               <Joystick onMove={handleJoystickMove} onStop={stopRobot} label="XY Movement" />
            </div>

            <button
              onPointerDown={emergencyStop}
              className="bg-red-600 hover:bg-red-500 active:bg-red-700 active:scale-95 transition-all text-white font-bold text-xl py-6 rounded-xl shadow-lg shadow-red-900/50 uppercase tracking-widest border border-red-500"
            >
              Emergency Stop (Space)
            </button>

          </div>
        </div>
      </div>
    </div>
  );
}
