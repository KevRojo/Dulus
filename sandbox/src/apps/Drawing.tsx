// ============================================================
// Drawing / Paint — Canvas-based drawing application
// ============================================================

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Pencil, Eraser, Square, Circle, Type, PaintBucket, Pipette,
  Undo2, Redo2, Trash2, Download, Grid3x3,
  Minus as LineIcon,
} from 'lucide-react';

type ToolType = 'pencil' | 'brush' | 'eraser' | 'line' | 'rectangle' | 'circle' | 'fill' | 'eyedropper' | 'text';

interface Point { x: number; y: number }

interface HistoryItem {
  data: string;
}

const TOOLS: { key: ToolType; label: string; icon: typeof Pencil }[] = [
  { key: 'pencil', label: 'Pencil', icon: Pencil },
  { key: 'brush', label: 'Brush', icon: PaintBucket },
  { key: 'eraser', label: 'Eraser', icon: Eraser },
  { key: 'line', label: 'Line', icon: LineIcon },
  { key: 'rectangle', label: 'Rectangle', icon: Square },
  { key: 'circle', label: 'Circle', icon: Circle },
  { key: 'fill', label: 'Fill', icon: PaintBucket },
  { key: 'eyedropper', label: 'Pick', icon: Pipette },
  { key: 'text', label: 'Text', icon: Type },
];

export default function Drawing() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<ToolType>('pencil');
  const [color, setColor] = useState('#7C4DFF');
  const [size, setSize] = useState(3);
  const [opacity, setOpacity] = useState(100);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<Point | null>(null);
  const [showGrid, setShowGrid] = useState(false);
  const [bgColor, _setBgColor] = useState('#FFFFFF');
  const [canvasSize, _setCanvasSize] = useState({ width: 800, height: 500 });
  const lastPoint = useRef<Point | null>(null);
  const [textInput, setTextInput] = useState('');
  const [textPos, setTextPos] = useState<Point | null>(null);

  // Initialize canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    canvas.width = canvasSize.width;
    canvas.height = canvasSize.height;
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    saveHistory();
  }, []);

  const saveHistory = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const data = canvas.toDataURL();
    setHistory((prev) => {
      const next = prev.slice(0, historyIndex + 1);
      next.push({ data });
      if (next.length > 50) next.shift();
      return next;
    });
    setHistoryIndex((prev) => Math.min(prev + 1, 49));
  }, [historyIndex]);

  const undo = useCallback(() => {
    if (historyIndex <= 0) return;
    const newIndex = historyIndex - 1;
    setHistoryIndex(newIndex);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const img = document.createElement('img');
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = history[newIndex].data;
  }, [history, historyIndex]);

  const redo = useCallback(() => {
    if (historyIndex >= history.length - 1) return;
    const newIndex = historyIndex + 1;
    setHistoryIndex(newIndex);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const img = document.createElement('img');
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = history[newIndex].data;
  }, [history, historyIndex]);

  const getCanvasPoint = useCallback((e: React.MouseEvent<HTMLCanvasElement>): Point => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return { x: (e.clientX - rect.left) * (canvas.width / rect.width), y: (e.clientY - rect.top) * (canvas.height / rect.height) };
  }, []);

  const floodFill = useCallback((x: number, y: number, fillColor: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data;

    const targetR = parseInt(fillColor.slice(1, 3), 16);
    const targetG = parseInt(fillColor.slice(3, 5), 16);
    const targetB = parseInt(fillColor.slice(5, 7), 16);
    const targetA = 255;

    const idx = (Math.floor(y) * canvas.width + Math.floor(x)) * 4;
    const startR = pixels[idx], startG = pixels[idx + 1], startB = pixels[idx + 2], startA = pixels[idx + 3];

    if (startR === targetR && startG === targetG && startB === targetB && startA === targetA) return;

    const stack: [number, number][] = [[Math.floor(x), Math.floor(y)]];
    const visited = new Set<number>();

    while (stack.length > 0) {
      const [cx, cy] = stack.pop()!;
      const i = (cy * canvas.width + cx) * 4;
      const key = cy * canvas.width + cx;
      if (cx < 0 || cx >= canvas.width || cy < 0 || cy >= canvas.height) continue;
      if (visited.has(key)) continue;
      if (pixels[i] !== startR || pixels[i + 1] !== startG || pixels[i + 2] !== startB || pixels[i + 3] !== startA) continue;

      visited.add(key);
      pixels[i] = targetR;
      pixels[i + 1] = targetG;
      pixels[i + 2] = targetB;
      pixels[i + 3] = targetA;

      stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }

    ctx.putImageData(imageData, 0, 0);
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const point = getCanvasPoint(e);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (tool === 'eyedropper') {
      const pixel = ctx.getImageData(point.x, point.y, 1, 1).data;
      const hex = '#' + [pixel[0], pixel[1], pixel[2]].map((v) => v.toString(16).padStart(2, '0')).join('');
      setColor(hex);
      setTool('pencil');
      return;
    }

    if (tool === 'fill') {
      floodFill(point.x, point.y, color);
      saveHistory();
      return;
    }

    if (tool === 'text') {
      setTextPos(point);
      return;
    }

    setIsDrawing(true);
    setStartPoint(point);
    lastPoint.current = point;

    ctx.globalAlpha = opacity / 100;
    ctx.strokeStyle = tool === 'eraser' ? bgColor : color;
    ctx.fillStyle = tool === 'eraser' ? bgColor : color;
    ctx.lineWidth = size;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (tool === 'pencil' || tool === 'brush') {
      ctx.beginPath();
      ctx.moveTo(point.x, point.y);
    }
  }, [tool, color, size, opacity, bgColor, getCanvasPoint, floodFill, saveHistory]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint) return;
    const point = getCanvasPoint(e);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.globalAlpha = opacity / 100;
    ctx.strokeStyle = tool === 'eraser' ? bgColor : color;
    ctx.fillStyle = tool === 'eraser' ? bgColor : color;
    ctx.lineWidth = size;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (tool === 'pencil' || tool === 'eraser') {
      ctx.beginPath();
      ctx.moveTo(lastPoint.current?.x ?? point.x, lastPoint.current?.y ?? point.y);
      ctx.lineTo(point.x, point.y);
      ctx.stroke();
      lastPoint.current = point;
    } else if (tool === 'brush') {
      // Soft brush
      ctx.save();
      ctx.globalAlpha = (opacity / 100) * 0.5;
      ctx.beginPath();
      ctx.moveTo(lastPoint.current?.x ?? point.x, lastPoint.current?.y ?? point.y);
      ctx.lineTo(point.x, point.y);
      ctx.stroke();
      ctx.restore();
      lastPoint.current = point;
    }
  }, [isDrawing, startPoint, tool, color, size, opacity, bgColor, getCanvasPoint]);

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint) return;
    const point = getCanvasPoint(e);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.globalAlpha = opacity / 100;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = size;
    ctx.lineCap = 'round';

    if (tool === 'line') {
      ctx.beginPath();
      ctx.moveTo(startPoint.x, startPoint.y);
      ctx.lineTo(point.x, point.y);
      ctx.stroke();
    } else if (tool === 'rectangle') {
      const w = point.x - startPoint.x;
      const h = point.y - startPoint.y;
      ctx.strokeRect(startPoint.x, startPoint.y, w, h);
    } else if (tool === 'circle') {
      const radius = Math.sqrt(Math.pow(point.x - startPoint.x, 2) + Math.pow(point.y - startPoint.y, 2));
      ctx.beginPath();
      ctx.arc(startPoint.x, startPoint.y, radius, 0, 2 * Math.PI);
      ctx.stroke();
    }

    setIsDrawing(false);
    setStartPoint(null);
    lastPoint.current = null;
    saveHistory();
  }, [isDrawing, startPoint, tool, color, size, opacity, getCanvasPoint, saveHistory]);

  const clearCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    saveHistory();
  }, [bgColor, saveHistory]);

  const exportImage = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = 'drawing.png';
    a.click();
  }, []);

  const addText = useCallback(() => {
    if (!textInput || !textPos) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.globalAlpha = opacity / 100;
    ctx.fillStyle = color;
    ctx.font = `${size * 3 + 10}px sans-serif`;
    ctx.fillText(textInput, textPos.x, textPos.y);
    setTextInput('');
    setTextPos(null);
    saveHistory();
  }, [textInput, textPos, color, size, opacity, saveHistory]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'y') { e.preventDefault(); redo(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, redo]);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 shrink-0 flex-wrap" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        {/* Tools */}
        {TOOLS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTool(t.key)}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors"
              style={{
                background: tool === t.key ? 'var(--accent-primary)' : 'transparent',
                color: tool === t.key ? 'white' : 'var(--text-secondary)',
              }}
              title={t.label}
            >
              <Icon size={14} />
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          );
        })}

        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />

        {/* Undo/Redo */}
        <button onClick={undo} className="p-1 rounded hover:bg-[var(--bg-hover)]" title="Undo (Ctrl+Z)"><Undo2 size={14} /></button>
        <button onClick={redo} className="p-1 rounded hover:bg-[var(--bg-hover)]" title="Redo (Ctrl+Y)"><Redo2 size={14} /></button>

        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />

        {/* Size */}
        <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Size:</label>
        <input type="range" min={1} max={50} value={size} onChange={(e) => setSize(Number(e.target.value))} className="w-20 accent-purple-500" />
        <span className="text-xs w-5" style={{ color: 'var(--text-secondary)' }}>{size}</span>

        {/* Opacity */}
        <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Op:</label>
        <input type="range" min={1} max={100} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="w-16 accent-purple-500" />
        <span className="text-xs w-6" style={{ color: 'var(--text-secondary)' }}>{opacity}%</span>

        {/* Color */}
        <input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="w-7 h-7 rounded cursor-pointer border-0 p-0" />

        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />

        <button onClick={() => setShowGrid((v) => !v)} className="p-1 rounded hover:bg-[var(--bg-hover)]" title="Toggle Grid"><Grid3x3 size={14} /></button>
        <button onClick={clearCanvas} className="p-1 rounded hover:bg-[var(--bg-hover)]" title="Clear"><Trash2 size={14} /></button>
        <button onClick={exportImage} className="p-1 rounded hover:bg-[var(--bg-hover)]" title="Export PNG"><Download size={14} /></button>
      </div>

      {/* Text input overlay */}
      {textPos && (
        <div className="shrink-0 px-3 py-1 flex items-center gap-2" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
          <input
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Enter text..."
            className="flex-1 px-2 py-0.5 rounded text-xs outline-none"
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter') addText(); }}
          />
          <button onClick={addText} className="px-2 py-0.5 rounded text-xs" style={{ background: 'var(--accent-primary)', color: 'white' }}>Add</button>
          <button onClick={() => { setTextPos(null); setTextInput(''); }} className="px-2 py-0.5 rounded text-xs hover:bg-[var(--bg-hover)]">Cancel</button>
        </div>
      )}

      {/* Canvas area */}
      <div ref={containerRef} className="flex-1 flex items-center justify-center overflow-auto p-4 custom-scrollbar" style={{ background: '#1A1A1A' }}>
        <div className="relative" style={{ boxShadow: 'var(--shadow-lg)' }}>
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{
              width: canvasSize.width,
              height: canvasSize.height,
              cursor: tool === 'eyedropper' ? 'crosshair' : 'default',
              background: bgColor,
            }}
            className="block"
          />
          {/* Grid overlay */}
          {showGrid && (
            <div className="absolute inset-0 pointer-events-none" style={{
              backgroundImage: 'linear-gradient(#E0E0E0 1px, transparent 1px), linear-gradient(90deg, #E0E0E0 1px, transparent 1px)',
              backgroundSize: '20px 20px',
              width: canvasSize.width,
              height: canvasSize.height,
            }} />
          )}
        </div>
      </div>
    </div>
  );
}
