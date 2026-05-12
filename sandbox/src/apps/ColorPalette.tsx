// ============================================================
// Color Palette — Color harmony generator
// ============================================================

import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Check, RefreshCw, Save, Trash2, Palette,

} from 'lucide-react';

type HarmonyType = 'complementary' | 'analogous' | 'triadic' | 'split-complementary' | 'tetradic' | 'monochromatic';

type ColorBlindType = 'none' | 'deuteranopia' | 'protanopia' | 'tritanopia';

interface SavedPalette {
  id: string;
  name: string;
  colors: string[];
  timestamp: number;
}

function hexToHsl(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
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
  const hue2rgb = (p: number, q: number, t: number) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  const nh = h / 360, ns = s / 100, nl = l / 100;
  let r: number, g: number, b: number;
  if (ns === 0) { r = g = b = nl; }
  else {
    const q = nl < 0.5 ? nl * (1 + ns) : nl + ns - nl * ns;
    const p = 2 * nl - q;
    r = hue2rgb(p, q, nh + 1 / 3);
    g = hue2rgb(p, q, nh);
    b = hue2rgb(p, q, nh - 1 / 3);
  }
  const toHex = (x: number) => Math.round(x * 255).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function generateHarmony(hex: string, type: HarmonyType): string[] {
  const [h, s, l] = hexToHsl(hex);
  switch (type) {
    case 'complementary': return [hex, hslToHex((h + 180) % 360, s, l)];
    case 'analogous': return [hex, hslToHex((h + 30) % 360, s, l), hslToHex((h - 30 + 360) % 360, s, l)];
    case 'triadic': return [hex, hslToHex((h + 120) % 360, s, l), hslToHex((h + 240) % 360, s, l)];
    case 'split-complementary': return [hex, hslToHex((h + 150) % 360, s, l), hslToHex((h + 210) % 360, s, l)];
    case 'tetradic': return [hex, hslToHex((h + 90) % 360, s, l), hslToHex((h + 180) % 360, s, l), hslToHex((h + 270) % 360, s, l)];
    case 'monochromatic': return [hex, hslToHex(h, s, Math.max(10, l - 30)), hslToHex(h, s, Math.max(10, l - 15)), hslToHex(h, s, Math.min(95, l + 15)), hslToHex(h, s, Math.min(95, l + 30))];
    default: return [hex];
  }
}

function randomHex(): string {
  return '#' + Array.from({ length: 6 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
}

function getContrastRatio(hex1: string, hex2: string): number {
  const lum = (hex: string) => {
    const [r, g, b] = [parseInt(hex.slice(1, 3), 16) / 255, parseInt(hex.slice(3, 5), 16) / 255, parseInt(hex.slice(5, 7), 16) / 255];
    const [lr, lg, lb] = [r, g, b].map((c) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
  };
  const l1 = lum(hex1), l2 = lum(hex2);
  const lighter = Math.max(l1, l2), darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function simulateColorBlind(hex: string, type: ColorBlindType): string {
  if (type === 'none') return hex;
  // Simplified simulation
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);

  if (type === 'deuteranopia') { // green weak
    const nr = Math.round(0.625 * r + 0.375 * g);
    const ng = Math.round(0.7 * r + 0.3 * g);
    return `#${nr.toString(16).padStart(2, '0')}${ng.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }
  if (type === 'protanopia') { // red blind
    const nr = Math.round(0.567 * r + 0.433 * g);
    const ng = Math.round(0.558 * r + 0.442 * g);
    return `#${nr.toString(16).padStart(2, '0')}${ng.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }
  // tritanopia
  const nr = Math.round(r * 0.95 + b * 0.05);
  const nb = Math.round(g * 0.433 + b * 0.567);
  return `#${nr.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${nb.toString(16).padStart(2, '0')}`;
}

const HARMONY_LABELS: { key: HarmonyType; label: string }[] = [
  { key: 'complementary', label: 'Complementary' },
  { key: 'analogous', label: 'Analogous' },
  { key: 'triadic', label: 'Triadic' },
  { key: 'split-complementary', label: 'Split-Comp' },
  { key: 'tetradic', label: 'Tetradic' },
  { key: 'monochromatic', label: 'Monochromatic' },
];

function getWcagLabel(ratio: number): string {
  if (ratio >= 7) return 'AAA';
  if (ratio >= 4.5) return 'AA';
  if (ratio >= 3) return 'AA Large';
  return 'Fail';
}

export default function ColorPalette() {
  const [baseColor, setBaseColor] = useState('#7C4DFF');
  const [harmonyType, setHarmonyType] = useState<HarmonyType>('complementary');
  const [colors, setColors] = useState<string[]>(['#7C4DFF', '#FFB84D']);
  const [savedPalettes, setSavedPalettes] = useState<SavedPalette[]>(() => {
    try { return JSON.parse(localStorage.getItem('color_palettes') || '[]'); } catch { return []; }
  });
  const [contrastColor, setContrastColor] = useState('#FFFFFF');
  const [colorBlindMode, setColorBlindMode] = useState<ColorBlindType>('none');
  const [copied, setCopied] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [paletteName, setPaletteName] = useState('');

  useEffect(() => {
    const palette = generateHarmony(baseColor, harmonyType);
    setColors(palette);
  }, [baseColor, harmonyType]);

  useEffect(() => {
    localStorage.setItem('color_palettes', JSON.stringify(savedPalettes));
  }, [savedPalettes]);

  const generateRandom = useCallback(() => {
    const newColor = randomHex();
    setBaseColor(newColor);
  }, []);

  const savePalette = useCallback(() => {
    if (!paletteName.trim()) return;
    const newPalette: SavedPalette = {
      id: Date.now().toString(),
      name: paletteName,
      colors: [...colors],
      timestamp: Date.now(),
    };
    setSavedPalettes((prev) => [newPalette, ...prev]);
    setPaletteName('');
  }, [paletteName, colors]);

  const deletePalette = useCallback((id: string) => {
    setSavedPalettes((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const loadPalette = useCallback((palette: SavedPalette) => {
    if (palette.colors.length > 0) {
      setBaseColor(palette.colors[0]);
    }
  }, []);

  const copyHex = useCallback(async (hex: string) => {
    await navigator.clipboard.writeText(hex);
    setCopied(hex);
    setTimeout(() => setCopied(null), 1500);
  }, []);

  const exportPalette = useCallback((format: 'css' | 'json') => {
    let content = '';
    if (format === 'css') {
      content = colors.map((c, i) => `  --color-${i + 1}: ${c};`).join('\n');
      content = `:root {\n${content}\n}`;
    } else {
      content = JSON.stringify({ palette: colors.map((c, i) => ({ name: `color-${i + 1}`, hex: c })) }, null, 2);
    }
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `palette.${format}`;
    a.click();
    URL.revokeObjectURL(url);
    setExportOpen(false);
  }, [colors]);

  const contrastRatio = useMemo(() => getContrastRatio(baseColor, contrastColor), [baseColor, contrastColor]);

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg-window)' }}>
      {/* Top: Color Input */}
      <div className="shrink-0 px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <div className="flex items-center gap-4 flex-wrap">
          <input
            type="color"
            value={baseColor}
            onChange={(e) => setBaseColor(e.target.value)}
            className="w-14 h-14 rounded cursor-pointer border-0"
            style={{ background: 'transparent' }}
          />
          <div className="flex flex-col gap-1">
            <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Base Color</label>
            <input
              value={baseColor.toUpperCase()}
              onChange={(e) => { const v = e.target.value; if (/^#[0-9A-Fa-f]{0,6}$/.test(v)) setBaseColor(v); }}
              className="px-2 py-1 rounded text-sm font-mono outline-none"
              style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', width: 90 }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Harmony</label>
            <select
              value={harmonyType}
              onChange={(e) => setHarmonyType(e.target.value as HarmonyType)}
              className="px-2 py-1 rounded text-xs outline-none"
              style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
            >
              {HARMONY_LABELS.map((h) => <option key={h.key} value={h.key}>{h.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Color Blind</label>
            <select
              value={colorBlindMode}
              onChange={(e) => setColorBlindMode(e.target.value as ColorBlindType)}
              className="px-2 py-1 rounded text-xs outline-none"
              style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
            >
              <option value="none">Normal</option>
              <option value="deuteranopia">Deuteranopia</option>
              <option value="protanopia">Protanopia</option>
              <option value="tritanopia">Tritanopia</option>
            </select>
          </div>
          <button onClick={generateRandom} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ border: '1px solid var(--border-default)' }}>
            <RefreshCw size={12} /> Random
          </button>
          <div className="ml-auto flex items-center gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Contrast with</label>
              <input
                type="color"
                value={contrastColor}
                onChange={(e) => setContrastColor(e.target.value)}
                className="w-8 h-6 rounded cursor-pointer border-0 p-0"
              />
            </div>
            <div className="text-center">
              <div className="text-xs font-semibold" style={{ color: contrastRatio >= 4.5 ? '#4CAF50' : '#FF9800' }}>
                {contrastRatio.toFixed(2)}:1
              </div>
              <div className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>{getWcagLabel(contrastRatio)}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
          {/* Color swatches */}
          <div className="flex gap-3 flex-wrap mb-6">
            {colors.map((color, i) => {
              const displayColor = simulateColorBlind(color, colorBlindMode);
              return (
                <div key={`${color}-${i}`} className="flex flex-col items-center gap-1">
                  <button
                    onClick={() => copyHex(color)}
                    className="w-20 h-20 rounded-lg transition-transform hover:scale-105 relative group"
                    style={{ background: displayColor, boxShadow: 'var(--shadow-sm)' }}
                    title={color}
                  >
                    {copied === color && (
                      <div className="absolute inset-0 flex items-center justify-center rounded-lg" style={{ background: 'rgba(0,0,0,0.4)' }}>
                        <Check size={20} className="text-white" />
                      </div>
                    )}
                  </button>
                  <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>{color.toUpperCase()}</span>
                  <div className="flex gap-1">
                    {[baseColor, contrastColor].map((bg, bi) => (
                      <div key={bi} className="w-4 h-4 rounded-full" style={{ background: bg, border: `1px solid ${color}` }} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Contrast matrix */}
          <div className="mb-6">
            <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>Contrast Matrix</h3>
            <div className="flex flex-col gap-1">
              {colors.slice(0, 4).map((c1, i) => (
                <div key={i} className="flex gap-1">
                  {colors.slice(0, 4).map((c2, j) => {
                    const ratio = getContrastRatio(c1, c2);
                    return (
                      <div
                        key={j}
                        className="w-14 h-10 rounded flex items-center justify-center text-[10px] font-medium"
                        style={{ background: c1, color: c2, border: '1px solid var(--border-subtle)' }}
                        title={`${c1} on ${c2}: ${ratio.toFixed(2)}:1`}
                      >
                        {ratio.toFixed(1)}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Save palette */}
          <div className="flex items-center gap-2 mb-4">
            <input
              value={paletteName}
              onChange={(e) => setPaletteName(e.target.value)}
              placeholder="Palette name..."
              className="px-2 py-1 rounded text-xs outline-none"
              style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
            />
            <button onClick={savePalette} className="flex items-center gap-1 px-3 py-1 rounded text-xs" style={{ background: 'var(--accent-primary)', color: 'white' }}>
              <Save size={12} /> Save
            </button>
            <button onClick={() => setExportOpen((v) => !v)} className="flex items-center gap-1 px-3 py-1 rounded text-xs hover:bg-[var(--bg-hover)]" style={{ border: '1px solid var(--border-default)' }}>
              Export
            </button>
          </div>

          {exportOpen && (
            <div className="flex gap-2 mb-4">
              <button onClick={() => exportPalette('css')} className="px-3 py-1 rounded text-xs hover:bg-[var(--bg-hover)]" style={{ border: '1px solid var(--border-default)' }}>
                Export CSS
              </button>
              <button onClick={() => exportPalette('json')} className="px-3 py-1 rounded text-xs hover:bg-[var(--bg-hover)]" style={{ border: '1px solid var(--border-default)' }}>
                Export JSON
              </button>
            </div>
          )}
        </div>

        {/* Saved palettes sidebar */}
        <div className="shrink-0 overflow-y-auto custom-scrollbar p-3" style={{ width: 180, borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-window)' }}>
          <div className="flex items-center gap-1 mb-2">
            <Palette size={12} style={{ color: 'var(--text-secondary)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>SAVED</span>
          </div>
          {savedPalettes.map((p) => (
            <div key={p.id} className="p-1.5 rounded mb-2 cursor-pointer hover:bg-[var(--bg-hover)]" onClick={() => loadPalette(p)}>
              <div className="flex gap-0.5 mb-1">
                {p.colors.slice(0, 5).map((c, i) => (
                  <div key={i} className="h-4 flex-1 rounded-sm" style={{ background: c }} />
                ))}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] truncate" style={{ color: 'var(--text-primary)' }}>{p.name}</span>
                <button onClick={(e) => { e.stopPropagation(); deletePalette(p.id); }} className="p-0.5 rounded hover:bg-red-500/20">
                  <Trash2 size={10} className="text-red-400" />
                </button>
              </div>
            </div>
          ))}
          {savedPalettes.length === 0 && <p className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>No saved palettes</p>}
        </div>
      </div>
    </div>
  );
}
