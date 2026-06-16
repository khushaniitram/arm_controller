import React from "react";

interface ControlPanelProps {
  onJogJoint: (joint: number, direction: string) => void;
  onJogCartesian: (axis: string, direction: string) => void;
  onStop: () => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
  lockNeedle?: boolean;
}

export default function ControlPanel({ onJogJoint, onJogCartesian, onStop, speed, onSpeedChange, lockNeedle = false }: ControlPanelProps) {
  const joints = [1, 2, 3, 4, 5, 6];
  const cartesian = ["X", "Y", "Z"];

  return (
    <div className="bg-white rounded-xl p-6 border border-zinc-200 flex flex-col gap-6 shadow-sm text-zinc-900">
      
      {/* Speed Control */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-sm font-bold text-zinc-800">Speed</h3>
          <span className="text-zinc-950 font-mono text-sm font-semibold">{speed}%</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="100" 
          value={speed}
          onChange={(e) => onSpeedChange(parseInt(e.target.value))}
          className="w-full accent-zinc-900 h-2 bg-zinc-200 rounded-lg appearance-none cursor-pointer"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Joint Controls */}
        <div>
          <h3 className="text-sm font-bold text-zinc-800 mb-3 border-b border-zinc-100 pb-2">Joint Control</h3>
          <div className="grid grid-cols-2 gap-2">
            {joints.map(j => {
              const isWrist = j >= 4;
              const isCompensated = isWrist && lockNeedle;
              return (
                <div key={j} className="flex gap-1">
                  <button 
                    onPointerDown={() => onJogJoint(j, "-")}
                    onPointerUp={onStop}
                    onPointerLeave={onStop}
                    onPointerCancel={onStop}
                    className="flex-1 px-2 py-3 rounded text-sm font-semibold select-none touch-none transition-all border shadow-xs cursor-pointer bg-zinc-100 hover:bg-zinc-200 text-zinc-900 active:bg-zinc-950 active:text-white border-zinc-200/60"
                  >
                    {isCompensated ? "🔗 " : ""} J{j}-
                  </button>
                  <button 
                    onPointerDown={() => onJogJoint(j, "+")}
                    onPointerUp={onStop}
                    onPointerLeave={onStop}
                    onPointerCancel={onStop}
                    className="flex-1 px-2 py-3 rounded text-sm font-semibold select-none touch-none transition-all border shadow-xs cursor-pointer bg-zinc-100 hover:bg-zinc-200 text-zinc-900 active:bg-zinc-950 active:text-white border-zinc-200/60"
                  >
                    {isCompensated ? "🔗 " : ""} J{j}+
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Cartesian Controls */}
        <div>
          <h3 className="text-sm font-bold text-zinc-800 mb-3 border-b border-zinc-100 pb-2">Cartesian Control</h3>
          <div className="grid grid-cols-1 gap-2">
            {cartesian.map(axis => (
              <div key={axis} className="flex gap-2">
                <button 
                  onPointerDown={() => onJogCartesian(axis, "-")}
                  onPointerUp={onStop}
                  onPointerLeave={onStop}
                  onPointerCancel={onStop}
                  className="flex-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-900 active:bg-zinc-950 active:text-white px-4 py-3 rounded font-semibold select-none touch-none transition-all border border-zinc-200/60 shadow-xs cursor-pointer"
                >
                  {axis}-
                </button>
                <button 
                  onPointerDown={() => onJogCartesian(axis, "+")}
                  onPointerUp={onStop}
                  onPointerLeave={onStop}
                  onPointerCancel={onStop}
                  className="flex-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-900 active:bg-zinc-950 active:text-white px-4 py-3 rounded font-semibold select-none touch-none transition-all border border-zinc-200/60 shadow-xs cursor-pointer"
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
