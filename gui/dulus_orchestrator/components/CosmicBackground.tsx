import React from 'react';

export const CosmicBackground: React.FC = () => {
  return (
    <div className="fixed inset-0 z-[-1] bg-black overflow-hidden pointer-events-none">
      {/* Deep space gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#0a0a0a] via-black to-black"></div>

      {/* Galaxy Swirls */}
      <div className="absolute top-1/2 left-1/2 w-[150vmax] h-[150vmax] animate-galaxy-spin opacity-50 mix-blend-screen">
        <div className="absolute inset-0 rounded-full bg-[conic-gradient(from_0deg,transparent_0_180deg,rgba(255,255,255,0.05)_360deg)] blur-[80px]"></div>
        <div className="absolute inset-0 rounded-full bg-[conic-gradient(from_180deg,transparent_0_180deg,rgba(251,191,36,0.1)_360deg)] blur-[80px]"></div>
      </div>

      {/* Static Stars */}
      <div className="absolute inset-0 opacity-60 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MDAiIGhlaWdodD0iNDAwIj48ZyBmaWxsPSIjZmZmIiBvcGFjaXR5PSIwLjgiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNTAiIHI9IjEiLz48Y2lyY2xlIGN4PSIxNTAiIGN5PSIyMTAiIHI9IjEuNSIvPjxjaXJjbGUgY3g9IjMwMCIgY3k9IjgwIiByPSIwLjUiLz48Y2lyY2xlIGN4PSIyNTAiIGN5PSIyNTAiIHI9IjEiLz48Y2lyY2xlIGN4PSI4MCIgY3k9IjMzMCIgIHI9IjEiLz48Y2lyY2xlIGN4PSIzNTAiIGN5PSIzNTAiIHI9IjEuNSIvPjwvZz48L3N2Zz4=')]"></div>

      {/* Comets */}
      <div className="absolute top-[-10%] left-[80%] animate-comet-1">
        <div className="w-1 h-1 bg-white rounded-full shadow-[0_0_20px_4px_rgba(255,255,255,0.8)]"></div>
        <div className="absolute top-0 left-0 w-[200px] h-[1px] bg-gradient-to-r from-white/80 to-transparent origin-top-left -rotate-45"></div>
      </div>

      <div className="absolute top-[-10%] left-[40%] animate-comet-2">
        <div className="w-1.5 h-1.5 bg-zinc-300 rounded-full shadow-[0_0_20px_4px_rgba(255,255,255,0.5)]"></div>
        <div className="absolute top-0 left-0 w-[300px] h-[2px] bg-gradient-to-r from-zinc-300/80 to-transparent origin-top-left -rotate-45"></div>
      </div>

      <div className="absolute top-[-10%] left-[110%] animate-comet-3">
        <div className="w-1 h-1 bg-amber-300 rounded-full shadow-[0_0_20px_4px_rgba(251,191,36,0.8)]"></div>
        <div className="absolute top-0 left-0 w-[150px] h-[1px] bg-gradient-to-r from-amber-300/80 to-transparent origin-top-left -rotate-45"></div>
      </div>

      <div className="absolute top-[-10%] left-[60%] animate-comet-4">
        <div className="w-0.5 h-0.5 bg-white rounded-full shadow-[0_0_15px_3px_rgba(255,255,255,0.6)]"></div>
        <div className="absolute top-0 left-0 w-[100px] h-[1px] bg-gradient-to-r from-white/60 to-transparent origin-top-left -rotate-45"></div>
      </div>
    </div>
  );
};

