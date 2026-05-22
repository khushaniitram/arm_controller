import React from "react";

interface ControlPanelProps {
  onJogJoint: (joint: number, direction: string) => void;
  onJogCartesian: (axis: string, direction: string) => void;
  onStop: () => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
}

export default function ControlPanel({ onJogJoint, onJogCartesian, onStop, speed, onSpeedChange }: ControlPanelProps) {
  const joints = [1, 2, 3, 4, 5, 6];
  const cartesian = ["X", "Y", "Z"];

  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 flex flex-col gap-6">
      
      {/* Speed Control */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-sm font-semibold text-slate-300">Speed</h3>
          <span className="text-blue-400 font-mono text-sm">{speed}%</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="100" 
          value={speed}
          onChange={(e) => onSpeedChange(parseInt(e.target.value))}
          className="w-full accent-blue-500 h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Joint Controls */}
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3 border-b border-slate-800 pb-2">Joint Control</h3>
          <div className="grid grid-cols-2 gap-2">
            {joints.map(j => (
              <div key={j} className="flex gap-1">
                <button 
                  onPointerDown={() => onJogJoint(j, "-")}
                  onPointerUp={onStop}
                  onPointerLeave={onStop}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 px-2 py-3 rounded text-sm select-none touch-none transition-colors"
                >
                  J{j}-
                </button>
                <button 
                  onPointerDown={() => onJogJoint(j, "+")}
                  onPointerUp={onStop}
                  onPointerLeave={onStop}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 px-2 py-3 rounded text-sm select-none touch-none transition-colors"
                >
                  J{j}+
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Cartesian Controls */}
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3 border-b border-slate-800 pb-2">Cartesian Control</h3>
          <div className="grid grid-cols-1 gap-2">
            {cartesian.map(axis => (
              <div key={axis} className="flex gap-2">
                <button 
                  onPointerDown={() => onJogCartesian(axis, "-")}
                  onPointerUp={onStop}
                  onPointerLeave={onStop}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 px-4 py-3 rounded select-none touch-none transition-colors"
                >
                  {axis}-
                </button>
                <button 
                  onPointerDown={() => onJogCartesian(axis, "+")}
                  onPointerUp={onStop}
                  onPointerLeave={onStop}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 px-4 py-3 rounded select-none touch-none transition-colors"
                >
                  {axis}+
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
