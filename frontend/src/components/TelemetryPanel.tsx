import React from "react";

interface TelemetryPanelProps {
  position: any;
  speed: number;
  stats: { fps: number; latency: number };
}

export default function TelemetryPanel({ position, speed, stats }: TelemetryPanelProps) {
  const formatVal = (val: any) => (typeof val === 'number' ? val.toFixed(2) : '0.00');

  const getQuality = (latency: number) => {
    if (latency === 0) return "Unknown";
    if (latency < 100) return "Excellent";
    if (latency < 300) return "Good";
    return "Poor";
  };

  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 h-full">
      <h3 className="text-sm font-semibold text-slate-300 mb-4 border-b border-slate-800 pb-2">Telemetry</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div>
          <h4 className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Cartesian</h4>
          <div className="space-y-1">
            <div className="flex justify-between"><span className="text-slate-400">X:</span> <span className="font-mono text-green-400">{formatVal(position?.x)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Y:</span> <span className="font-mono text-green-400">{formatVal(position?.y)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Z:</span> <span className="font-mono text-green-400">{formatVal(position?.z)}</span></div>
          </div>
        </div>

        <div>
          <h4 className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Joints</h4>
          <div className="space-y-1 grid grid-cols-2 gap-x-4">
            <div className="flex justify-between"><span className="text-slate-400">J1:</span> <span className="font-mono text-blue-400">{formatVal(position?.j1)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">J2:</span> <span className="font-mono text-blue-400">{formatVal(position?.j2)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">J3:</span> <span className="font-mono text-blue-400">{formatVal(position?.j3)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">J4:</span> <span className="font-mono text-blue-400">{formatVal(position?.j4)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">J5:</span> <span className="font-mono text-blue-400">{formatVal(position?.j5)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">J6:</span> <span className="font-mono text-blue-400">{formatVal(position?.j6)}</span></div>
          </div>
        </div>

        <div>
          <h4 className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Network & Perf</h4>
          <div className="space-y-1">
            <div className="flex justify-between"><span className="text-slate-400">Speed:</span> <span className="font-mono text-yellow-400">{speed}%</span></div>
            <div className="flex justify-between"><span className="text-slate-400">FPS:</span> <span className="font-mono text-yellow-400">{Math.round(stats.fps)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Latency:</span> <span className="font-mono text-yellow-400">{Math.round(stats.latency)} ms</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Quality:</span> <span className="font-mono text-yellow-400">{getQuality(stats.latency)}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
