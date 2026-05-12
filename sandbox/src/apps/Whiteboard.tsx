import { useState, useRef, useEffect, useCallback, type ReactElement } from 'react';
import {
  Pencil, Eraser, Minus, Square, Circle, Type, Download, Trash2,
  RotateCcw, RotateCw, StickyNote, MousePointer
} from 'lucide-react';

type Tool = 'pen' | 'eraser' | 'line' | 'rect' | 'circle' | 'text' | 'select';

interface DrawAction {
  type: 'draw' | 'erase' | 'line' | 'rect' | 'circle' | 'text';
  points?: { x: number; y: number }[];
  color: string;
  size: number;
  text?: string;
  x?: number;
  y?: number;
  endX?: number;
  endY?: number;
}

interface StickyNoteData {
  id: string;
  x: number;
  y: number;
  text: string;
  color: string;
}

const CANVAS_WIDTH = 2000;
const CANVAS_HEIGHT = 1500;
const COLORS = ['#E0E0E0', '#F44336', '#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#00BCD4', '#FFEB3B', '#FFFFFF'];
const NOTE_COLORS = ['#FFEB3B', '#FF9800', '#4CAF50', '#2196F3', '#E91E63', '#9C27B0'];

export default function Whiteboard() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<Tool>('pen');
  const [color, setColor] = useState('#E0E0E0');
  const [brushSize, setBrushSize] = useState(3);
  const [actions, setActions] = useState<DrawAction[]>([]);
  const [redoStack, setRedoStack] = useState<DrawAction[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentPoints, setCurrentPoints] = useState<{ x: number; y: number }[]>([]);
  const [stickyNotes, setStickyNotes] = useState<StickyNoteData[]>([]);
  const [showTextInput, setShowTextInput] = useState(false);
  const [textPos, setTextPos] = useState({ x: 0, y: 0 });
  const [textValue, setTextValue] = useState('');
  const [draggedNote, setDraggedNote] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const getCanvasPoint = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const scaleX = CANVAS_WIDTH / rect.width;
    const scaleY = CANVAS_HEIGHT / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  }, []);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let x = 0; x < CANVAS_WIDTH; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, CANVAS_HEIGHT); ctx.stroke(); }
    for (let y = 0; y < CANVAS_HEIGHT; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(CANVAS_WIDTH, y); ctx.stroke(); }
    // Actions
    actions.forEach(action => {
      ctx.strokeStyle = action.color;
      ctx.fillStyle = action.color;
      ctx.lineWidth = action.size;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      if ((action.type === 'draw' || action.type === 'erase') && action.points && action.points.length > 0) {
        ctx.globalCompositeOperation = action.type === 'erase' ? 'destination-out' : 'source-over';
        ctx.beginPath();
        ctx.moveTo(action.points[0].x, action.points[0].y);
        action.points.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.stroke();
        ctx.globalCompositeOperation = 'source-over';
      } else if (action.type === 'line' && action.x !== undefined) {
        ctx.beginPath();
        ctx.moveTo(action.x, action.y!);
        ctx.lineTo(action.endX!, action.endY!);
        ctx.stroke();
      } else if (action.type === 'rect' && action.x !== undefined) {
        ctx.strokeRect(action.x, action.y!, (action.endX! - action.x), (action.endY! - action.y!));
      } else if (action.type === 'circle' && action.x !== undefined) {
        const rx = Math.abs(action.endX! - action.x) / 2;
        const ry = Math.abs(action.endY! - action.y!) / 2;
        const cx = (action.x + action.endX!) / 2;
        const cy = (action.y! + action.endY!) / 2;
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.stroke();
      } else if (action.type === 'text' && action.x !== undefined) {
        ctx.font = `${action.size * 4}px Inter, sans-serif`;
        ctx.fillStyle = action.color;
        ctx.fillText(action.text || '', action.x, action.y!);
      }
    });
  }, [actions]);

  useEffect(() => { redraw(); }, [redraw]);

  const handleMouseDown = (e: React.MouseEvent) => {
    const p = getCanvasPoint(e);
    if (tool === 'text') {
      setTextPos(p);
      setShowTextInput(true);
      setTextValue('');
      return;
    }
    setIsDrawing(true);
    setStartPos(p);
    setCurrentPoints([p]);
    if (tool === 'pen' || tool === 'eraser') {
      setActions(prev => [...prev, { type: tool === 'eraser' ? 'erase' : 'draw', points: [p], color, size: brushSize }]);
      setRedoStack([]);
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDrawing) return;
    const p = getCanvasPoint(e);
    if (tool === 'pen' || tool === 'eraser') {
      setActions(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && (last.type === 'draw' || last.type === 'erase')) {
          last.points = [...(last.points || []), p];
        }
        return next;
      });
    }
    setCurrentPoints(prev => [...prev, p]);
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);
    if (tool === 'line' || tool === 'rect' || tool === 'circle') {
      const endP = currentPoints[currentPoints.length - 1];
      if (endP) {
        setActions(prev => [...prev, { type: tool as 'line' | 'rect' | 'circle', color, size: brushSize, x: startPos.x, y: startPos.y, endX: endP.x, endY: endP.y }]);
        setRedoStack([]);
      }
    }
    setCurrentPoints([]);
  };

  const addText = () => {
    if (!textValue.trim()) { setShowTextInput(false); return; }
    setActions(prev => [...prev, { type: 'text', color, size: brushSize, x: textPos.x, y: textPos.y, text: textValue.trim() }]);
    setRedoStack([]);
    setShowTextInput(false);
    setTextValue('');
  };

  const addStickyNote = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const sx = containerRef.current?.scrollLeft || 0;
    const sy = containerRef.current?.scrollTop || 0;
    const rect = canvas.getBoundingClientRect();
    const scaleX = CANVAS_WIDTH / rect.width;
    const scaleY = CANVAS_HEIGHT / rect.height;
    const x = sx * scaleX + 50;
    const y = sy * scaleY + 50;
    const note: StickyNoteData = { id: Date.now().toString(), x, y, text: 'New note', color: NOTE_COLORS[Math.floor(Math.random() * NOTE_COLORS.length)] };
    setStickyNotes(prev => [...prev, note]);
  };

  const undo = () => {
    setActions(prev => { if (prev.length === 0) return prev; const last = prev[prev.length - 1]; setRedoStack(r => [...r, last]); return prev.slice(0, -1); });
  };

  const redo = () => {
    setRedoStack(prev => { if (prev.length === 0) return prev; const last = prev[prev.length - 1]; setActions(a => [...a, last]); return prev.slice(0, -1); });
  };

  const clearCanvas = () => { setActions([]); setRedoStack([]); setStickyNotes([]); };

  const exportCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // Draw sticky notes onto canvas for export
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = CANVAS_WIDTH;
    exportCanvas.height = CANVAS_HEIGHT;
    const ctx = exportCanvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    // Copy main canvas
    ctx.drawImage(canvas, 0, 0);
    // Draw notes
    const container = containerRef.current;
    if (container) {
      const rect = canvas.getBoundingClientRect();
      const scaleX = CANVAS_WIDTH / rect.width;
      const scaleY = CANVAS_HEIGHT / rect.height;
      stickyNotes.forEach(note => {
        const nx = note.x / scaleX * (rect.width / CANVAS_WIDTH);
        const ny = note.y / scaleY * (rect.height / CANVAS_HEIGHT);
        ctx.fillStyle = note.color;
        ctx.fillRect(note.x, note.y, 160, 120);
        ctx.fillStyle = '#000';
        ctx.font = '12px Inter, sans-serif';
        const words = note.text.split(' ');
        let line = '';
        let y = note.y + 20;
        words.forEach(word => {
          const test = line + word + ' ';
          if (ctx.measureText(test).width > 140 && line) {
            ctx.fillText(line, note.x + 8, y);
            line = word + ' ';
            y += 16;
          } else line = test;
        });
        ctx.fillText(line, note.x + 8, y);
      });
    }
    const link = document.createElement('a');
    link.download = 'whiteboard.png';
    link.href = exportCanvas.toDataURL('image/png');
    link.click();
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) { e.preventDefault(); redo(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [actions, redoStack]);

  const toolBtn = (t: Tool, icon: ReactElement, label: string) => (
    <button
      onClick={() => setTool(t)}
      className="flex flex-col items-center gap-0.5 p-1.5 rounded-md transition-colors"
      style={{ color: tool === t ? 'var(--accent-primary)' : 'var(--text-secondary)', background: tool === t ? 'var(--bg-active)' : 'transparent' }}
      title={label}
    >
      {icon}
      <span className="text-[9px]">{label}</span>
    </button>
  );

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        {toolBtn('select', <MousePointer size={16} />, 'Select')}
        {toolBtn('pen', <Pencil size={16} />, 'Pen')}
        {toolBtn('eraser', <Eraser size={16} />, 'Eraser')}
        {toolBtn('line', <Minus size={16} />, 'Line')}
        {toolBtn('rect', <Square size={16} />, 'Rect')}
        {toolBtn('circle', <Circle size={16} />, 'Circle')}
        {toolBtn('text', <Type size={16} />, 'Text')}
        <div className="w-px h-6 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={addStickyNote} className="flex flex-col items-center gap-0.5 p-1.5 rounded-md transition-colors" style={{ color: 'var(--text-secondary)' }} title="Sticky Note"><StickyNote size={16} /><span className="text-[9px]">Note</span></button>
        <div className="w-px h-6 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <div className="flex gap-0.5">
          {COLORS.map(c => (
            <button key={c} onClick={() => setColor(c)} className="w-5 h-5 rounded-full border transition-transform" style={{ background: c, borderColor: color === c ? '#fff' : 'rgba(255,255,255,0.2)', transform: color === c ? 'scale(1.2)' : 'scale(1)' }} />
          ))}
        </div>
        <div className="w-px h-6 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <input type="range" min={1} max={20} value={brushSize} onChange={e => setBrushSize(Number(e.target.value))} className="w-16" />
        <div className="flex-1" />
        <button onClick={undo} className="p-1.5 rounded" style={{ color: 'var(--text-secondary)' }}><RotateCcw size={14} /></button>
        <button onClick={redo} className="p-1.5 rounded" style={{ color: 'var(--text-secondary)' }}><RotateCw size={14} /></button>
        <button onClick={clearCanvas} className="p-1.5 rounded" style={{ color: 'var(--accent-error)' }}><Trash2 size={14} /></button>
        <button onClick={exportCanvas} className="p-1.5 rounded" style={{ color: 'var(--text-secondary)' }}><Download size={14} /></button>
      </div>
      {/* Canvas Area */}
      <div ref={containerRef} className="flex-1 overflow-auto custom-scrollbar relative">
        <canvas
          ref={canvasRef}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT, cursor: tool === 'text' ? 'text' : 'crosshair' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        {/* Sticky Notes overlay */}
        {stickyNotes.map(note => {
          const canvas = canvasRef.current;
          if (!canvas) return null;
          const rect = canvas.getBoundingClientRect();
          const scaleX = rect.width / CANVAS_WIDTH;
          const scaleY = rect.height / CANVAS_HEIGHT;
          const displayX = note.x * scaleX;
          const displayY = note.y * scaleY;
          return (
            <div
              key={note.id}
              style={{ position: 'absolute', left: displayX, top: displayY, width: 160 * scaleX, minHeight: 100 * scaleY, background: note.color, borderRadius: 4, padding: 8 * scaleX, color: '#000', fontSize: 11 * scaleX, cursor: 'move', zIndex: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.3)' }}
              onMouseDown={(e) => { setDraggedNote(note.id); setDragOffset({ x: e.clientX, y: e.clientY }); }}
              contentEditable
              suppressContentEditableWarning
              onBlur={(e) => { setStickyNotes(prev => prev.map(n => n.id === note.id ? { ...n, text: e.currentTarget.innerText } : n)); }}
            >
              {note.text}
            </div>
          );
        })}
        {/* Text input overlay */}
        {showTextInput && (
          <div style={{ position: 'absolute', left: textPos.x * ((canvasRef.current?.getBoundingClientRect().width || CANVAS_WIDTH) / CANVAS_WIDTH), top: textPos.y * ((canvasRef.current?.getBoundingClientRect().height || CANVAS_HEIGHT) / CANVAS_HEIGHT), zIndex: 20 }}>
            <input
              value={textValue} onChange={e => setTextValue(e.target.value)} onKeyDown={e => e.key === 'Enter' && addText()} autoFocus
              className="px-1 py-0.5 text-sm outline-none bg-transparent"
              style={{ color, minWidth: 100, borderBottom: `1px dashed ${color}` }}
              placeholder="Type..."
            />
          </div>
        )}
      </div>
      {/* Global mouse up for dragging */}
      <div style={{ display: 'none' }} onMouseUp={() => setDraggedNote(null)} />
    </div>
  );
}
