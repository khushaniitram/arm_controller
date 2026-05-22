import React, { useRef, useState, useEffect } from "react";

interface JoystickProps {
  onMove: (x: number, y: number) => void;
  onStop: () => void;
  label?: string;
}

export default function Joystick({ onMove, onStop, label }: JoystickProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const handleMove = (clientX: number, clientY: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const maxDistance = rect.width / 2;

    let deltaX = clientX - centerX;
    let deltaY = clientY - centerY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

    if (distance > maxDistance) {
      deltaX = (deltaX / distance) * maxDistance;
      deltaY = (deltaY / distance) * maxDistance;
    }

    setPosition({ x: deltaX, y: deltaY });
    
    // Normalize to -1 to 1
    onMove(deltaX / maxDistance, deltaY / maxDistance);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    setIsDragging(true);
    handleMove(e.clientX, e.clientY);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    handleMove(e.clientX, e.clientY);
  };

  const onPointerUp = (e: React.PointerEvent) => {
    setIsDragging(false);
    setPosition({ x: 0, y: 0 });
    onStop();
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  };

  return (
    <div className="flex flex-col items-center gap-2">
      {label && <span className="text-sm text-slate-400 font-semibold">{label}</span>}
      <div 
        ref={containerRef}
        className="w-32 h-32 rounded-full bg-slate-800 border-2 border-slate-700 relative touch-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div 
          className="w-12 h-12 rounded-full bg-blue-500 absolute top-1/2 left-1/2 shadow-lg shadow-blue-500/50"
          style={{
            transform: `translate(calc(-50% + ${position.x}px), calc(-50% + ${position.y}px))`,
            transition: isDragging ? 'none' : 'transform 0.2s ease-out'
          }}
        />
      </div>
    </div>
  );
}
