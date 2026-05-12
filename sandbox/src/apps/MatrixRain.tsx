import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play, Pause, Maximize, Minimize, Droplets
} from 'lucide-react';

type MatrixColor = 'green' | 'amber' | 'red' | 'blue';

const COLOR_MAP: Record<MatrixColor, { primary: string; glow: string; bg: string }> = {
  green: { primary: '#00FF00', glow: 'rgba(0,255,0,0.3)', bg: '#000000' },
  amber: { primary: '#FFB000', glow: 'rgba(255,176,0,0.3)', bg: '#0a0500' },
  red: { primary: '#FF0040', glow: 'rgba(255,0,64,0.3)', bg: '#0a0000' },
  blue: { primary: '#0080FF', glow: 'rgba(0,128,255,0.3)', bg: '#000510' },
};

const KATAKANA = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
const LATIN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
const NUMBERS = '0123456789';
const ALL_CHARS = KATAKANA + LATIN + NUMBERS;

interface Column {
  x: number;
  speed: number;
  chars: string[];
  y: number;
  length: number;
  opacity: number;
}

export default function MatrixRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [density, setDensity] = useState(1);
  const [color, setColor] = useState<MatrixColor>('green');
  const [showControls, setShowControls] = useState(true);

  const isPlayingRef = useRef(isPlaying);
  const speedRef = useRef(speed);
  const densityRef = useRef(density);
  const colorRef = useRef(color);
  const columnsRef = useRef<Column[]>([]);
  const animationRef = useRef<number>(0);
  const frameCount = useRef(0);

  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { speedRef.current = speed; }, [speed]);
  useEffect(() => { densityRef.current = density; }, [density]);
  useEffect(() => { colorRef.current = color; }, [color]);

  const colors = COLOR_MAP[color];

  const initColumns = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const fontSize = 14;
    const cols = Math.floor(canvas.width / fontSize);
    columnsRef.current = [];
    const actualCols = Math.floor(cols * densityRef.current);
    for (let i = 0; i < actualCols; i++) {
      columnsRef.current.push(createColumn(canvas.width, fontSize, i * (cols / actualCols) * fontSize));
    }
  }, []);

  const createColumn = (canvasWidth: number, fontSize: number, x?: number): Column => {
    const c: Column = {
      x: x !== undefined ? x : Math.floor(Math.random() * (canvasWidth / fontSize)) * fontSize,
      speed: 0.5 + Math.random() * 1.5,
      chars: [],
      y: -Math.random() * 500,
      length: 10 + Math.floor(Math.random() * 20),
      opacity: 0.3 + Math.random() * 0.7,
    };
    for (let j = 0; j < c.length; j++) {
      c.chars.push(ALL_CHARS[Math.floor(Math.random() * ALL_CHARS.length)]);
    }
    return c;
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      if (isFullscreen && containerRef.current) {
        canvas.width = containerRef.current.clientWidth;
        canvas.height = containerRef.current.clientHeight;
      } else {
        const parent = canvas.parentElement;
        if (parent) {
          canvas.width = parent.clientWidth;
          canvas.height = parent.clientHeight;
        }
      }
      initColumns();
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [isFullscreen, initColumns]);

  useEffect(() => { initColumns(); }, [density, initColumns]);

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const fontSize = 14;

    const draw = () => {
      const c = colorRef.current;
      const cm = COLOR_MAP[c];
      // Fade effect
      ctx.fillStyle = cm.bg + '1A'; // ~10% opacity
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      if (!isPlayingRef.current) {
        animationRef.current = requestAnimationFrame(draw);
        return;
      }

      frameCount.current++;

      columnsRef.current.forEach(col => {
        col.y += col.speed * speedRef.current;

        // Randomly change characters
        if (frameCount.current % 4 === 0) {
          const idx = Math.floor(Math.random() * col.chars.length);
          col.chars[idx] = ALL_CHARS[Math.floor(Math.random() * ALL_CHARS.length)];
        }

        // Draw characters
        for (let i = 0; i < col.chars.length; i++) {
          const charY = col.y - i * fontSize;
          if (charY < -fontSize || charY > canvas.height + fontSize) continue;

          const isHead = i === 0;
          const brightness = isHead ? 1 : Math.max(0.1, 1 - i / col.length);
          const alpha = isHead ? 1 : brightness * col.opacity;

          ctx.font = `${isHead ? 'bold' : 'normal'} ${fontSize}px 'JetBrains Mono', monospace`;

          if (isHead) {
            ctx.fillStyle = '#FFFFFF';
            ctx.shadowColor = cm.primary;
            ctx.shadowBlur = 10;
          } else {
            ctx.fillStyle = cm.primary;
            ctx.globalAlpha = alpha;
            ctx.shadowBlur = 0;
          }

          ctx.fillText(col.chars[i], col.x, charY);
          ctx.globalAlpha = 1;
          ctx.shadowBlur = 0;
        }

        // Reset column when it goes off screen
        if (col.y - col.length * fontSize > canvas.height) {
          const newCol = createColumn(canvas.width, fontSize);
          newCol.x = col.x;
          Object.assign(col, newCol);
        }
      });

      animationRef.current = requestAnimationFrame(draw);
    };

    animationRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animationRef.current);
  }, []);

  // Handle click burst
  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Add burst columns near click
    for (let i = 0; i < 5; i++) {
      const fontSize = 14;
      const newCol = createColumn(canvas.width, fontSize);
      newCol.x = x + (Math.random() - 0.5) * 80;
      newCol.y = y;
      newCol.speed = 1 + Math.random() * 2;
      columnsRef.current.push(newCol);
    }
  };

  const toggleFullscreen = () => {
    if (!isFullscreen) {
      setIsFullscreen(true);
      setShowControls(false);
    } else {
      setIsFullscreen(false);
      setShowControls(true);
    }
  };

  return (
    <div ref={containerRef} className="relative flex flex-col h-full" style={{ background: colors.bg }}>
      {/* Canvas fills the container */}
      <div className="absolute inset-0" onClick={handleClick}>
        <canvas ref={canvasRef} className="w-full h-full block" style={{ cursor: 'crosshair' }} />
      </div>

      {/* Overlay controls */}
      {showControls && (
        <div className="relative z-10">
          {/* Toolbar */}
          <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}>
            <Droplets size={14} style={{ color: colors.primary }} />
            <span className="text-xs font-medium flex-1" style={{ color: '#fff' }}>Matrix Rain</span>
            <button onClick={() => setIsPlaying(!isPlaying)} className="p-1.5 rounded" style={{ color: '#fff' }}>
              {isPlaying ? <Pause size={12} /> : <Play size={12} />}
            </button>
            <button onClick={toggleFullscreen} className="p-1.5 rounded" style={{ color: '#fff' }}>
              {isFullscreen ? <Minimize size={12} /> : <Maximize size={12} />}
            </button>
          </div>

          {/* Settings */}
          <div className="flex items-center gap-3 px-3 py-1.5 border-b" style={{ borderColor: 'rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}>
            <div className="flex items-center gap-1">
              <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.6)' }}>Speed</span>
              <input type="range" min={0.2} max={3} step={0.1} value={speed} onChange={e => setSpeed(Number(e.target.value))} className="w-14" />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.6)' }}>Density</span>
              <input type="range" min={0.3} max={2} step={0.1} value={density} onChange={e => setDensity(Number(e.target.value))} className="w-14" />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.6)' }}>Color</span>
              {(['green', 'amber', 'red', 'blue'] as MatrixColor[]).map(c => (
                <button key={c} onClick={() => setColor(c)} className="w-3.5 h-3.5 rounded-full border transition-transform" style={{ background: COLOR_MAP[c].primary, borderColor: color === c ? '#fff' : 'transparent', transform: color === c ? 'scale(1.3)' : 'scale(1)' }} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Hint text */}
      <div className="absolute bottom-2 left-0 right-0 text-center z-10 pointer-events-none">
        <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.3)' }}>Click anywhere to spawn burst</span>
      </div>
    </div>
  );
}
