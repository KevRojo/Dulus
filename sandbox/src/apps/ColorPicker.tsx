// ============================================================
// Color Picker — Advanced color picker tool
// ============================================================

import { useState, useCallback, useMemo } from 'react';
import {
  Copy, Check, RefreshCw, Plus, Trash2,
} from 'lucide-react';

interface SavedColor {
  id: string;
  hex: string;
  timestamp: number;
}

interface RecentColor {
  hex: string;
  timestamp: number;
}

function hexToRgb(hex: string): [number, number, number] {
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
}

function rgbToHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
}

function hexToHsl(hex: string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex).map((v) => v / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
}

function hslToHex(h: number, s: number, l: number): string {
  const nh = h / 360, ns = s / 100, nl = l / 100;
  let r: number, g: number, b: number;
  if (ns === 0) { r = g = b = nl; }
  else {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = nl < 0.5 ? nl * (1 + ns) : nl + ns - nl * ns;
    const p = 2 * nl - q;
    r = hue2rgb(p, q, nh + 1 / 3);
    g = hue2rgb(p, q, nh);
    b = hue2rgb(p, q, nh - 1 / 3);
  }
  return rgbToHex(r * 255, g * 255, b * 255);
}

function hexToCmyk(hex: string): [number, number, number, number] {
  const [r, g, b] = hexToRgb(hex).map((v) => v / 255);
  const k = 1 - Math.max(r, g, b);
  if (k === 1) return [0, 0, 0, 100];
  const c = ((1 - r - k) / (1 - k)) * 100;
  const m = ((1 - g - k) / (1 - k)) * 100;
  const y = ((1 - b - k) / (1 - k)) * 100;
  return [Math.round(c), Math.round(m), Math.round(y), Math.round(k * 100)];
}

function getLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function getContrastRatio(hex1: string, hex2: string): number {
  const l1 = getLuminance(hex1), l2 = getLuminance(hex2);
  const lighter = Math.max(l1, l2), darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

const PRESET_COLORS = [
  '#F44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5', '#2196F3',
  '#03A9F4', '#00BCD4', '#009688', '#4CAF50', '#8BC34A', '#CDDC39',
  '#FFEB3B', '#FFC107', '#FF9800', '#FF5722', '#795548', '#9E9E9E',
  '#607D8B', '#000000', '#FFFFFF', '#7C4DFF',
];

export default function ColorPicker() {
  const [color, setColor] = useState('#7C4DFF');
  const [savedColors, setSavedColors] = useState<SavedColor[]>(() => {
    try { return JSON.parse(localStorage.getItem('saved_colors') || '[]'); } catch { return []; }
  });
  const [recentColors, setRecentColors] = useState<RecentColor[]>(() => {
    try { return JSON.parse(localStorage.getItem('recent_colors') || '[]'); } catch { return []; }
  });
  const [contrastBg, setContrastBg] = useState('#FFFFFF');
  const [copied, setCopied] = useState<string | null>(null);

  const [h, s, l] = hexToHsl(color);
  const [r, g, b] = hexToRgb(color);
  const [c, m, y, k] = hexToCmyk(color);
  const contrastRatio = getContrastRatio(color, contrastBg);

  const updateColor = useCallback((newHex: string) => {
    setColor(newHex);
    setRecentColors((prev) => {
      const next = [{ hex: newHex, timestamp: Date.now() }, ...prev.filter((c) => c.hex !== newHex)].slice(0, 10);
      localStorage.setItem('recent_colors', JSON.stringify(next));
      return next;
    });
  }, []);

  const updateFromHsl = useCallback((nh: number, ns: number, nl: number) => {
    updateColor(hslToHex(nh, ns, nl));
  }, [updateColor]);

  const updateFromRgb = useCallback((nr: number, ng: number, nb: number) => {
    updateColor(rgbToHex(nr, ng, nb));
  }, [updateColor]);

  const copyValue = useCallback(async (value: string, key: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  }, []);

  const saveColor = useCallback(() => {
    const newColor: SavedColor = { id: Date.now().toString(), hex: color, timestamp: Date.now() };
    setSavedColors((prev) => {
      const next = [newColor, ...prev].slice(0, 20);
      localStorage.setItem('saved_colors', JSON.stringify(next));
      return next;
    });
  }, [color]);

  const removeSaved = useCallback((id: string) => {
    setSavedColors((prev) => {
      const next = prev.filter((c) => c.id !== id);
      localStorage.setItem('saved_colors', JSON.stringify(next));
      return next;
    });
  }, []);

  const randomColor = useCallback(() => {
    const hex = '#' + Array.from({ length: 6 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
    updateColor(hex);
  }, [updateColor]);

  // Generate shades and tints
  const shades = useMemo(() => Array.from({ length: 10 }, (_, i) => hslToHex(h, s, (i + 1) * 10)), [h, s]);
  const tints = useMemo(() => Array.from({ length: 10 }, (_, i) => {
    const factor = i / 9;
    return rgbToHex(
      Math.round(r + (255 - r) * factor),
      Math.round(g + (255 - g) * factor),
      Math.round(b + (255 - b) * factor)
    );
  }), [r, g, b]);

  const getWcagLabel = (ratio: number): string => {
    if (ratio >= 7) return 'AAA';
    if (ratio >= 4.5) return 'AA';
    if (ratio >= 3) return 'AA Large';
    return 'Fail';
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto custom-scrollbar" style={{ background: 'var(--bg-window)' }}>
      {/* Large preview */}
      <div className="h-28 shrink-0 flex items-center justify-center gap-4" style={{ background: color }}>
        <div className="text-center">
          <p className="text-sm font-semibold" style={{ color: getLuminance(color) > 0.5 ? '#000' : '#fff' }}>
            {color.toUpperCase()}
          </p>
          <p className="text-xs" style={{ color: getLuminance(color) > 0.5 ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,255,0.6)' }}>
            {getWcagLabel(contrastRatio)} on white
          </p>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
          {/* Sliders */}
          <div className="mb-4">
            <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Hue: {h}°</label>
            <input
              type="range" min={0} max={360} value={h}
              onChange={(e) => updateFromHsl(Number(e.target.value), s, l)}
              className="w-full h-3 rounded-full appearance-none cursor-pointer accent-transparent"
              style={{ background: 'linear-gradient(to right, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00)' }}
            />
          </div>
          <div className="mb-4">
            <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Saturation: {s}%</label>
            <input
              type="range" min={0} max={100} value={s}
              onChange={(e) => updateFromHsl(h, Number(e.target.value), l)}
              className="w-full h-2 rounded-full appearance-none cursor-pointer accent-purple-500"
              style={{ background: `linear-gradient(to right, hsl(${h},0%,${l}%), hsl(${h},100%,${l}%))` }}
            />
          </div>
          <div className="mb-4">
            <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Lightness: {l}%</label>
            <input
              type="range" min={0} max={100} value={l}
              onChange={(e) => updateFromHsl(h, s, Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none cursor-pointer accent-purple-500"
              style={{ background: `linear-gradient(to right, hsl(${h},${s}%,0%), hsl(${h},${s}%,50%), hsl(${h},${s}%,100%))` }}
            />
          </div>

          {/* Color values */}
          <div className="grid grid-cols-1 gap-2 mb-4">
            {/* HEX */}
            <div className="flex items-center gap-2">
              <span className="text-xs w-10" style={{ color: 'var(--text-secondary)' }}>HEX</span>
              <input value={color.toUpperCase()} onChange={(e) => { const v = e.target.value; if (/^#[0-9A-Fa-f]{0,6}$/.test(v)) updateColor(v); }} className="flex-1 px-2 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <button onClick={() => copyValue(color.toUpperCase(), 'hex')} className="p-1 rounded hover:bg-[var(--bg-hover)]">{copied === 'hex' ? <Check size={12} /> : <Copy size={12} />}</button>
            </div>
            {/* RGB */}
            <div className="flex items-center gap-2">
              <span className="text-xs w-10" style={{ color: 'var(--text-secondary)' }}>RGB</span>
              <input type="number" min={0} max={255} value={r} onChange={(e) => updateFromRgb(Number(e.target.value), g, b)} className="w-14 px-1 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <input type="number" min={0} max={255} value={g} onChange={(e) => updateFromRgb(r, Number(e.target.value), b)} className="w-14 px-1 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <input type="number" min={0} max={255} value={b} onChange={(e) => updateFromRgb(r, g, Number(e.target.value))} className="w-14 px-1 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <button onClick={() => copyValue(`rgb(${r}, ${g}, ${b})`, 'rgb')} className="p-1 rounded hover:bg-[var(--bg-hover)]">{copied === 'rgb' ? <Check size={12} /> : <Copy size={12} />}</button>
            </div>
            {/* HSL */}
            <div className="flex items-center gap-2">
              <span className="text-xs w-10" style={{ color: 'var(--text-secondary)' }}>HSL</span>
              <input type="number" min={0} max={360} value={h} onChange={(e) => updateFromHsl(Number(e.target.value), s, l)} className="w-14 px-1 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <input type="number" min={0} max={100} value={s} onChange={(e) => updateFromHsl(h, Number(e.target.value), l)} className="w-14 px-1 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <input type="number" min={0} max={100} value={l} onChange={(e) => updateFromHsl(h, s, Number(e.target.value))} className="w-14 px-1 py-1 rounded text-xs font-mono outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }} />
              <button onClick={() => copyValue(`hsl(${h}, ${s}%, ${l}%)`, 'hsl')} className="p-1 rounded hover:bg-[var(--bg-hover)]">{copied === 'hsl' ? <Check size={12} /> : <Copy size={12} />}</button>
            </div>
            {/* CMYK */}
            <div className="flex items-center gap-2">
              <span className="text-xs w-10" style={{ color: 'var(--text-secondary)' }}>CMYK</span>
              <span className="text-xs font-mono w-8 text-center" style={{ color: 'var(--text-primary)' }}>{c}%</span>
              <span className="text-xs font-mono w-8 text-center" style={{ color: 'var(--text-primary)' }}>{m}%</span>
              <span className="text-xs font-mono w-8 text-center" style={{ color: 'var(--text-primary)' }}>{y}%</span>
              <span className="text-xs font-mono w-8 text-center" style={{ color: 'var(--text-primary)' }}>{k}%</span>
              <button onClick={() => copyValue(`cmyk(${c}%, ${m}%, ${y}%, ${k}%)`, 'cmyk')} className="p-1 rounded hover:bg-[var(--bg-hover)]">{copied === 'cmyk' ? <Check size={12} /> : <Copy size={12} />}</button>
            </div>
          </div>

          {/* Contrast checker */}
          <div className="mb-4 p-3 rounded" style={{ background: 'var(--bg-titlebar)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Contrast Checker</span>
              <input type="color" value={contrastBg} onChange={(e) => setContrastBg(e.target.value)} className="w-6 h-6 rounded cursor-pointer border-0 p-0" />
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-20 h-12 rounded text-xs font-medium" style={{ background: contrastBg, color }}>
                Aa
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: contrastRatio >= 4.5 ? '#4CAF50' : '#FF9800' }}>
                  {contrastRatio.toFixed(2)}:1
                </div>
                <div className="flex gap-1 mt-0.5">
                  {(['AA', 'AAA'] as const).map((level) => (
                    <span key={level} className="text-[10px] px-1.5 py-0.5 rounded" style={{
                      background: contrastRatio >= (level === 'AAA' ? 7 : 4.5) ? 'rgba(76,175,80,0.2)' : 'rgba(244,67,54,0.2)',
                      color: contrastRatio >= (level === 'AAA' ? 7 : 4.5) ? '#4CAF50' : '#F44336',
                    }}>
                      {level}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Presets */}
          <div className="mb-4">
            <span className="text-xs font-semibold block mb-2" style={{ color: 'var(--text-secondary)' }}>Presets</span>
            <div className="flex flex-wrap gap-1">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => updateColor(c)}
                  className="w-6 h-6 rounded-sm transition-transform hover:scale-110"
                  style={{ background: c, border: color === c ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)' }}
                />
              ))}
            </div>
          </div>

          {/* Shades */}
          <div className="mb-2">
            <span className="text-xs font-semibold block mb-1" style={{ color: 'var(--text-secondary)' }}>Shades</span>
            <div className="flex gap-0.5">
              {shades.map((c, i) => (
                <button key={i} onClick={() => updateColor(c)} className="h-6 flex-1 rounded-sm transition-transform hover:scale-105" style={{ background: c }} />
              ))}
            </div>
          </div>

          {/* Tints */}
          <div className="mb-4">
            <span className="text-xs font-semibold block mb-1" style={{ color: 'var(--text-secondary)' }}>Tints</span>
            <div className="flex gap-0.5">
              {tints.map((c, i) => (
                <button key={i} onClick={() => updateColor(c)} className="h-6 flex-1 rounded-sm transition-transform hover:scale-105" style={{ background: c }} />
              ))}
            </div>
          </div>

          <button onClick={randomColor} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs mb-4" style={{ background: 'var(--accent-primary)', color: 'white' }}>
            <RefreshCw size={12} /> Random Color
          </button>
        </div>

        {/* Right sidebar: Recent + Saved */}
        <div className="shrink-0 overflow-y-auto custom-scrollbar p-3" style={{ width: 120, borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-window)' }}>
          {/* Recent */}
          <div className="mb-4">
            <span className="text-xs font-semibold block mb-2" style={{ color: 'var(--text-secondary)' }}>RECENT</span>
            <div className="flex flex-wrap gap-1">
              {recentColors.map((rc, i) => (
                <button key={`${rc.hex}-${i}`} onClick={() => updateColor(rc.hex)} className="w-7 h-7 rounded-sm transition-transform hover:scale-110" style={{ background: rc.hex }} />
              ))}
            </div>
          </div>

          {/* Saved */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>SAVED</span>
              <button onClick={saveColor} className="p-0.5 rounded hover:bg-[var(--bg-hover)]"><Plus size={12} /></button>
            </div>
            <div className="flex flex-col gap-1">
              {savedColors.map((sc) => (
                <div key={sc.id} className="flex items-center gap-1">
                  <button onClick={() => updateColor(sc.hex)} className="w-6 h-6 rounded-sm shrink-0" style={{ background: sc.hex }} />
                  <span className="text-[10px] font-mono flex-1 truncate" style={{ color: 'var(--text-secondary)' }}>{sc.hex}</span>
                  <button onClick={() => removeSaved(sc.id)} className="p-0.5 rounded hover:bg-red-500/20"><Trash2 size={10} className="text-red-400" /></button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
