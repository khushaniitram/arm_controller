import React from "react";

interface TelemetryPanelProps {
  position: any;
  speed: number;
  stats: { fps: number; latency: number; controlLatency: number };
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
    <div className="bg-white rounded-xl p-6 border border-zinc-200 h-full text-zinc-900 shadow-sm">
      <h3 className="text-sm font-bold text-zinc-800 mb-4 border-b border-zinc-100 pb-2">Telemetry</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div>
          <h4 className="text-xs text-zinc-400 mb-2.5 uppercase tracking-wider font-bold">Cartesian</h4>
          <div className="space-y-1.5">
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">X:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-2 py-0.5 text-sm w-20 text-right">{formatVal(position?.x)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">Y:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-2 py-0.5 text-sm w-20 text-right">{formatVal(position?.y)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">Z:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-2 py-0.5 text-sm w-20 text-right">{formatVal(position?.z)}</span></div>
          </div>
        </div>

        <div>
          <h4 className="text-xs text-zinc-400 mb-2.5 uppercase tracking-wider font-bold">Joints</h4>
          <div className="space-y-1.5 grid grid-cols-2 gap-x-3">
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">J1:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-1.5 py-0.5 text-xs text-right w-14">{formatVal(position?.j1)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">J2:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-1.5 py-0.5 text-xs text-right w-14">{formatVal(position?.j2)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">J3:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-1.5 py-0.5 text-xs text-right w-14">{formatVal(position?.j3)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">J4:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-1.5 py-0.5 text-xs text-right w-14">{formatVal(position?.j4)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">J5:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-1.5 py-0.5 text-xs text-right w-14">{formatVal(position?.j5)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500 font-medium">J6:</span> <span className="font-mono text-zinc-950 font-semibold bg-zinc-100/60 border border-zinc-200/60 rounded px-1.5 py-0.5 text-xs text-right w-14">{formatVal(position?.j6)}</span></div>
          </div>
        </div>

        <div>
          <h4 className="text-xs text-zinc-400 mb-2.5 uppercase tracking-wider font-bold">Network & Perf</h4>
          <div className="space-y-1.5 text-sm">
            <div className="flex justify-between items-center"><span className="text-zinc-500">Robot Link:</span> <span className={`font-semibold text-xs px-2 py-0.5 rounded border ${position?.connected ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-rose-700 bg-rose-50 border-rose-200'}`}>{position?.connected ? "Connected" : "Disconnected"}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500">Port:</span> <span className="font-mono text-zinc-950 font-semibold">{position?.port || "-"}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500">Speed:</span> <span className="font-mono text-zinc-950 font-semibold">{speed}%</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500">FPS:</span> <span className="font-mono text-zinc-950 font-semibold">{Math.round(stats.fps)}</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500">Video Latency:</span> <span className="font-mono text-zinc-950 font-semibold">{Math.round(stats.latency)} ms</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500">Control Latency:</span> <span className="font-mono text-zinc-950 font-semibold">{Math.round(stats.controlLatency || 0)} ms</span></div>
            <div className="flex justify-between items-center"><span className="text-zinc-500">Quality:</span> <span className={`font-semibold text-xs px-2 py-0.5 rounded border ${getQuality(stats.latency) === 'Excellent' || getQuality(stats.latency) === 'Good' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-amber-700 bg-amber-50 border-amber-200'}`}>{getQuality(stats.latency)}</span></div>
          </div>
        </div>
      </div>
      
      {(position?.error || position?.motion_error || position?.controller_message) && (
        <div className="mt-4 pt-4 border-t border-zinc-100 flex flex-col gap-2">
          {position?.error && (
            <div className="text-xs text-rose-700 bg-rose-50/60 border border-rose-200/80 rounded-lg p-2.5 break-all font-medium">
              <strong>Serial error:</strong> {position.error}
            </div>
          )}
          {position?.motion_error && (
            <div className="text-xs text-amber-700 bg-amber-50/60 border border-amber-200/80 rounded-lg p-2.5 break-all font-medium">
              <strong>Motion status:</strong> {position.motion_error}
            </div>
          )}
          {position?.controller_message && (
            <div className="text-xs text-zinc-600 bg-zinc-50 border border-zinc-200/60 rounded-lg p-2.5 break-all font-mono">
              <strong>Controller raw:</strong> {position.controller_message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
