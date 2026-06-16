import React from "react";

interface StatusIndicatorsProps {
  wsStatus: string; // 'Connected' | 'Disconnected'
  cameraStatus: boolean;
  robotState: string; // 'Simulation Mode' | 'Hardware Disconnected' | 'Hardware Connected'
}

export default function StatusIndicators({ wsStatus, cameraStatus, robotState }: StatusIndicatorsProps) {
  const isWsConnected = wsStatus === 'Connected';
  const isCameraReady = cameraStatus;
  const isSim = robotState === 'Simulation Mode';
  const isRobotConnected = robotState.includes('Connected') || isSim;

  return (
    <div className="bg-white rounded-xl p-3 border border-zinc-200 flex flex-wrap gap-2 text-xs font-semibold shadow-xs">
      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${isWsConnected ? 'text-emerald-700 bg-emerald-50/60 border-emerald-200/80' : 'text-rose-700 bg-rose-50/60 border-rose-200/80'}`}>
        <span className={`w-2 h-2 rounded-full ${isWsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
        WS: {wsStatus}
      </div>
      
      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${isCameraReady ? 'text-emerald-700 bg-emerald-50/60 border-emerald-200/80' : 'text-rose-700 bg-rose-50/60 border-rose-200/80'}`}>
        <span className={`w-2 h-2 rounded-full ${isCameraReady ? 'bg-emerald-500' : 'bg-rose-500'}`} />
        Cam: {isCameraReady ? 'Ready' : 'Offline'}
      </div>

      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${isSim ? 'text-amber-700 bg-amber-50/60 border-amber-200/80' : (isRobotConnected ? 'text-emerald-700 bg-emerald-50/60 border-emerald-200/80' : 'text-rose-700 bg-rose-50/60 border-rose-200/80')}`}>
        <span className={`w-2 h-2 rounded-full ${isSim ? 'bg-amber-500' : (isRobotConnected ? 'bg-emerald-500' : 'bg-rose-500')}`} />
        {robotState}
      </div>
    </div>
  );
}
