// ============================================================
// Photo Editor — Canvas-based editing with filters and adjustments
// ============================================================

import { useState, useCallback, memo } from 'react';
import {
  Sun, Contrast, Droplet, Palette, RotateCcw, RotateCw, FlipHorizontal,
  FlipVertical, Download, Undo, Redo, ZoomIn, ZoomOut
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ---- Types ----
interface Adjustments {
  brightness: number;
  contrast: number;
  saturation: number;
  blur: number;
  hueRotate: number;
}

interface FilterPreset {
  name: string;
  cssFilter: string;
}

// ---- Filter Presets ----
const FILTER_PRESETS: FilterPreset[] = [
  { name: 'None', cssFilter: 'none' },
  { name: 'Warm', cssFilter: 'sepia(0.2) saturate(1.2) hue-rotate(-10deg)' },
  { name: 'Cool', cssFilter: 'hue-rotate(10deg) saturate(0.9)' },
  { name: 'B&W', cssFilter: 'grayscale(1)' },
  { name: 'Vintage', cssFilter: 'sepia(0.4) contrast(1.1) brightness(0.95)' },
  { name: 'Dramatic', cssFilter: 'contrast(1.4) saturate(1.2)' },
  { name: 'Vivid', cssFilter: 'saturate(1.5) contrast(1.1)' },
  { name: 'Fade', cssFilter: 'brightness(1.1) contrast(0.85) saturate(0.8)' },
  { name: 'Noir', cssFilter: 'grayscale(1) contrast(1.2) brightness(0.9)' },
  { name: 'Chrome', cssFilter: 'contrast(1.3) saturate(1.4) brightness(1.05)' },
];

const DEFAULT_ADJUSTMENTS: Adjustments = {
  brightness: 0,
  contrast: 0,
  saturation: 0,
  blur: 0,
  hueRotate: 0,
};

// ---- Adjustment Slider Component ----
const AdjustmentSlider = memo(function AdjustmentSlider({
  icon: Icon, label, value, min, max, onChange
}: {
  icon: LucideIcon; label: string; value: number; min: number; max: number;
  onChange: (val: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon size={14} style={{ color: 'var(--text-secondary)' }} />
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{label}</span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
        style={{ accentColor: 'var(--accent-primary)', height: 4 }}
      />
    </div>
  );
});

// ---- Main Photo Editor ----
export default function PhotoEditor() {
  const imageSrc = 'https://picsum.photos/seed/edit/800/600';
  const [adjustments, setAdjustments] = useState<Adjustments>(DEFAULT_ADJUSTMENTS);
  const [activeFilter, setActiveFilter] = useState<string>('None');
  const [rotation, setRotation] = useState(0);
  const [flipH, setFlipH] = useState(false);
  const [flipV, setFlipV] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [showCompare, setShowCompare] = useState(false);
  const [comparePosition, setComparePosition] = useState(50);
  const [history] = useState<{ adjustments: Adjustments; filter: string; rotation: number; flipH: boolean; flipV: boolean }[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  const undo = () => {
    if (historyIndex > 0) {
      const state = history[historyIndex - 1];
      setAdjustments(state.adjustments);
      setActiveFilter(state.filter);
      setRotation(state.rotation);
      setFlipH(state.flipH);
      setFlipV(state.flipV);
      setHistoryIndex(historyIndex - 1);
    }
  };

  const redo = () => {
    if (historyIndex < history.length - 1) {
      const state = history[historyIndex + 1];
      setAdjustments(state.adjustments);
      setActiveFilter(state.filter);
      setRotation(state.rotation);
      setFlipH(state.flipH);
      setFlipV(state.flipV);
      setHistoryIndex(historyIndex + 1);
    }
  };

  const resetAll = () => {
    setAdjustments(DEFAULT_ADJUSTMENTS);
    setActiveFilter('None');
    setRotation(0);
    setFlipH(false);
    setFlipV(false);
  };

  // Build CSS filter string
  const buildFilterString = useCallback((adj: Adjustments, filterName: string): string => {
    const preset = FILTER_PRESETS.find((f) => f.name === filterName);
    const baseFilter = preset && preset.name !== 'None' ? preset.cssFilter : '';
    const adjFilters = [
      `brightness(${100 + adj.brightness}%)`,
      `contrast(${100 + adj.contrast}%)`,
      `saturate(${100 + adj.saturation}%)`,
      adj.blur > 0 ? `blur(${adj.blur}px)` : '',
      adj.hueRotate !== 0 ? `hue-rotate(${adj.hueRotate}deg)` : '',
    ].filter(Boolean).join(' ');
    return `${baseFilter} ${adjFilters}`.trim();
  }, []);

  const filterString = buildFilterString(adjustments, activeFilter);

  const transformString = `
    rotate(${rotation}deg)
    scaleX(${flipH ? -1 : 1})
    scaleY(${flipV ? -1 : 1})
    scale(${zoom})
  `;

  // Export image
  const exportImage = () => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const img = document.createElement('img');
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.filter = filterString;
      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate((rotation * Math.PI) / 180);
      ctx.scale(flipH ? -1 : 1, flipV ? -1 : 1);
      ctx.drawImage(img, -img.width / 2, -img.height / 2);
      ctx.restore();
      const link = document.createElement('a');
      link.download = 'edited-image.png';
      link.href = canvas.toDataURL();
      link.click();
    };
    img.src = imageSrc;
  };

  const handleCompareMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!showCompare) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    setComparePosition(Math.max(5, Math.min(95, x)));
  };

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Left Sidebar - Tools */}
      <div className="flex flex-col shrink-0 overflow-y-auto custom-scrollbar" style={{ width: 220, background: 'var(--bg-titlebar)', borderRight: '1px solid var(--border-subtle)' }}>
        {/* Toolbar */}
        <div className="flex items-center gap-1 px-2 py-2 shrink-0" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <button onClick={undo} disabled={historyIndex <= 0} className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)] disabled:opacity-30" style={{ width: 28, height: 28 }}>
            <Undo size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>
          <button onClick={redo} disabled={historyIndex >= history.length - 1} className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)] disabled:opacity-30" style={{ width: 28, height: 28 }}>
            <Redo size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>
          <div style={{ width: 1, height: 16, background: 'var(--border-subtle)', margin: '0 2px' }} />
          <button onClick={exportImage} className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)]" style={{ width: 28, height: 28 }}>
            <Download size={14} style={{ color: 'var(--accent-primary)' }} />
          </button>
        </div>

        {/* Adjustments */}
        <div className="p-3 flex flex-col gap-3">
          <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Adjustments</h3>
          <AdjustmentSlider icon={Sun} label="Brightness" value={adjustments.brightness} min={-100} max={100} onChange={(v) => setAdjustments((a) => ({ ...a, brightness: v }))} />
          <AdjustmentSlider icon={Contrast} label="Contrast" value={adjustments.contrast} min={-100} max={100} onChange={(v) => setAdjustments((a) => ({ ...a, contrast: v }))} />
          <AdjustmentSlider icon={Droplet} label="Saturation" value={adjustments.saturation} min={-100} max={100} onChange={(v) => setAdjustments((a) => ({ ...a, saturation: v }))} />
          <AdjustmentSlider icon={Droplet} label="Blur" value={adjustments.blur} min={0} max={10} onChange={(v) => setAdjustments((a) => ({ ...a, blur: v }))} />
          <AdjustmentSlider icon={Palette} label="Hue Rotate" value={adjustments.hueRotate} min={-180} max={180} onChange={(v) => setAdjustments((a) => ({ ...a, hueRotate: v }))} />
        </div>

        {/* Filters */}
        <div className="p-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Filters</h3>
          <div className="grid grid-cols-3 gap-2">
            {FILTER_PRESETS.map((filter) => (
              <button
                key={filter.name}
                onClick={() => setActiveFilter(filter.name)}
                className="flex flex-col items-center gap-1 p-1.5 rounded-lg transition-all"
                style={{
                  background: activeFilter === filter.name ? 'var(--bg-selected)' : 'transparent',
                  border: activeFilter === filter.name ? '2px solid var(--accent-primary)' : '2px solid transparent',
                }}
              >
                <div
                  className="rounded-md overflow-hidden"
                  style={{ width: 50, height: 40, background: '#333' }}
                >
                  <img
                    src={imageSrc}
                    alt={filter.name}
                    className="w-full h-full object-cover"
                    style={{ filter: filter.cssFilter, transform: 'scale(1.2)' }}
                  />
                </div>
                <span style={{ fontSize: '10px', color: activeFilter === filter.name ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>{filter.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Transform */}
        <div className="p-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Transform</h3>
          <div className="grid grid-cols-2 gap-2">
            <TransformButton icon={RotateCcw} label="Rotate Left" onClick={() => setRotation((r) => r - 90)} />
            <TransformButton icon={RotateCw} label="Rotate Right" onClick={() => setRotation((r) => r + 90)} />
            <TransformButton icon={FlipHorizontal} label="Flip H" onClick={() => setFlipH((f) => !f)} />
            <TransformButton icon={FlipVertical} label="Flip V" onClick={() => setFlipV((f) => !f)} />
          </div>
        </div>

        {/* Reset */}
        <div className="p-3 mt-auto" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <button
            onClick={resetAll}
            className="w-full py-2 rounded-lg transition-all hover:bg-[var(--bg-hover)]"
            style={{ fontSize: '12px', color: 'var(--accent-error)', border: '1px solid var(--border-default)' }}
          >
            Reset All
          </button>
        </div>
      </div>

      {/* Canvas Area */}
      <div className="flex-1 flex flex-col relative overflow-hidden" style={{ background: '#1A1A1A' }}>
        {/* Top Toolbar */}
        <div className="flex items-center justify-between px-3 py-1.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center gap-1">
            <button onClick={() => setZoom((z) => Math.max(0.1, z - 0.1))} className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)]" style={{ width: 28, height: 28 }}>
              <ZoomOut size={14} style={{ color: 'var(--text-secondary)' }} />
            </button>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', minWidth: 36, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom((z) => Math.min(5, z + 0.1))} className="flex items-center justify-center rounded hover:bg-[var(--bg-hover)]" style={{ width: 28, height: 28 }}>
              <ZoomIn size={14} style={{ color: 'var(--text-secondary)' }} />
            </button>
          </div>
          <button
            onClick={() => setShowCompare((s) => !s)}
            className="px-3 py-1 rounded-lg transition-all"
            style={{
              fontSize: '12px',
              background: showCompare ? 'var(--accent-primary)' : 'transparent',
              color: showCompare ? 'white' : 'var(--text-secondary)',
              border: showCompare ? 'none' : '1px solid var(--border-default)',
            }}
          >
            Compare
          </button>
        </div>

        {/* Image Canvas */}
        <div className="flex-1 flex items-center justify-center overflow-hidden p-4">
          {showCompare ? (
            <div
              className="relative w-full h-full flex items-center justify-center overflow-hidden cursor-col-resize"
              onMouseMove={handleCompareMove}
              onMouseLeave={() => setComparePosition(50)}
            >
              {/* Original (left) */}
              <img
                src={imageSrc}
                alt="Original"
                className="absolute max-w-full max-h-full object-contain"
                style={{ clipPath: `inset(0 ${100 - comparePosition}% 0 0)` }}
              />
              {/* Edited (right) */}
              <img
                src={imageSrc}
                alt="Edited"
                className="absolute max-w-full max-h-full object-contain"
                style={{ filter: filterString, transform: transformString, clipPath: `inset(0 0 0 ${comparePosition}%)` }}
              />
              {/* Divider line */}
              <div
                className="absolute top-0 bottom-0"
                style={{ left: `${comparePosition}%`, width: 2, background: 'var(--accent-primary)', transform: 'translateX(-50%)' }}
              />
            </div>
          ) : (
            <img
              src={imageSrc}
              alt="Edit"
              className="max-w-full max-h-full object-contain transition-all"
              style={{ filter: filterString, transform: transformString }}
              draggable={false}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ---- Transform Button ----
function TransformButton({ icon: Icon, label, onClick }: { icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center justify-center gap-1.5 py-2 rounded-lg transition-all hover:bg-[var(--bg-hover)]"
      style={{ fontSize: '11px', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}
