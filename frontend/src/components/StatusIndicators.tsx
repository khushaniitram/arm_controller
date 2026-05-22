import React from "react";

interface StatusIndicatorsProps {
  wsStatus: string; // 'Connected' | 'Disconnected'
  cameraStatus: boolean;
  robotState: string; // 'Simulation Mode' | 'Hardware Disconnected' | 'Hardware Connected'
}

export default function StatusIndicators({ wsStatus, cameraStatus, robotState }: StatusIndicatorsProps) {
  return (
    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800 flex flex-wrap gap-4 text-sm font-medium">
      <div className={`flex items-center gap-2 ${wsStatus === 'Connected' ? 'text-green-400' : 'text-red-400'}`}>
        <span className={`w-2.5 h-2.5 rounded-full ${wsStatus === 'Connected' ? 'bg-green-500' : 'bg-red-500'}`} />
        WebSocket {wsStatus}
      </div>
      
      <div className={`flex items-center gap-2 ${cameraStatus ? 'text-green-400' : 'text-red-400'}`}>
        <span className={`w-2.5 h-2.5 rounded-full ${cameraStatus ? 'bg-green-500' : 'bg-red-500'}`} />
        Camera {cameraStatus ? 'Ready' : 'Disconnected'}
      </div>

      <div className={`flex items-center gap-2 ${robotState === 'Simulation Mode' ? 'text-yellow-400' : (robotState.includes('Disconnected') ? 'text-red-400' : 'text-green-400')}`}>
        <span className={`w-2.5 h-2.5 rounded-full ${robotState === 'Simulation Mode' ? 'bg-yellow-500' : (robotState.includes('Disconnected') ? 'bg-red-500' : 'bg-green-500')}`} />
        {robotState}
      </div>
    </div>
  );
}
