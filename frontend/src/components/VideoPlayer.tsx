import { useEffect, useRef, useState } from "react";

interface VideoPlayerProps {
  streamStatusCallback: (status: boolean) => void;
  onStatsUpdate: (stats: { fps: number; latency: number }) => void;
}

export default function VideoPlayer({ streamStatusCallback, onStatsUpdate }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let pc = new RTCPeerConnection();
    let statsInterval: NodeJS.Timeout;

    const startWebRTC = async () => {
      try {
        pc.addTransceiver("video", { direction: "recvonly" });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "localhost:8000";
        const response = await fetch(`http://${backendUrl}/offer`, {
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

        // Start collecting stats
        statsInterval = setInterval(async () => {
          const stats = await pc.getStats();
          let currentFps = 0;
          let currentLatency = 0;
          
          stats.forEach((report) => {
            if (report.type === "inbound-rtp" && report.kind === "video") {
              currentFps = report.framesPerSecond || 0;
            }
            if (report.type === "candidate-pair" && report.state === "succeeded") {
              currentLatency = report.currentRoundTripTime ? report.currentRoundTripTime * 1000 : 0; // Convert to ms
            }
          });
          
          onStatsUpdate({ fps: currentFps, latency: currentLatency });
        }, 1000);

      } catch (err: any) {
        setError(err.message);
        streamStatusCallback(false);
      }
    };

    pc.ontrack = (event) => {
      if (videoRef.current) {
        videoRef.current.srcObject = event.streams[0];
        streamStatusCallback(true);
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
        streamStatusCallback(false);
      }
    };

    startWebRTC();

    return () => {
      if (statsInterval) clearInterval(statsInterval);
      pc.close();
      streamStatusCallback(false);
    };
  }, []);

  return (
    <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden border border-slate-700 shadow-xl">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-cover"
      />
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-red-500 bg-black/80">
          <p>Error: {error}</p>
        </div>
      )}
    </div>
  );
}
