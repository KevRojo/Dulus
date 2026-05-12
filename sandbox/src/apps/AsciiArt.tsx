// ============================================================
// ASCII Art — Text to ASCII, Image to ASCII, ASCII Draw
// ============================================================

import { useState, useCallback, useRef, useMemo } from 'react';
import {
  Type, Image, Pencil, Copy, Check, Download, Trash2,
  RefreshCw,
} from 'lucide-react';

type AsciiTab = 'text' | 'image' | 'draw';

const ASCII_FONTS: Record<string, Record<string, string[]>> = {
  block: {
    'A': ['███','█ █','███','█ █','█ █'],'B': ['██ ','█ █','██ ','█ █','██ '],
    'C': [' ██','█  ','█  ','█  ',' ██'],'D': ['██ ','█ █','█ █','█ █','██ '],
    'E': ['███','█  ','██ ','█  ','███'],'F': ['███','█  ','██ ','█  ','█  '],
    'G': [' ██','█  ','█ █','█ █',' ██'],'H': ['█ █','█ █','███','█ █','█ █'],
    'I': ['███',' █ ',' █ ',' █ ','███'],'J': ['  █','  █','  █','█ █',' █ '],
    'K': ['█ █','█ █','██ ','█ █','█ █'],'L': ['█  ','█  ','█  ','█  ','███'],
    'M': ['█ █','███','█ █','█ █','█ █'],'N': ['███','█ █','█ █','█ █','█ █'],
    'O': [' █ ','█ █','█ █','█ █',' █ '],'P': ['██ ','█ █','██ ','█  ','█  '],
    'Q': [' █ ','█ █','█ █',' ██','  █'],'R': ['██ ','█ █','██ ','█ █','█ █'],
    'S': [' ██','█  ',' █ ','  █','██ '],'T': ['███',' █ ',' █ ',' █ ',' █ '],
    'U': ['█ █','█ █','█ █','█ █','███'],'V': ['█ █','█ █','█ █','█ █',' █ '],
    'W': ['█ █','█ █','█ █','███','█ █'],'X': ['█ █','█ █',' █ ','█ █','█ █'],
    'Y': ['█ █','█ █',' █ ',' █ ',' █ '],'Z': ['███','  █',' █ ','█  ','███'],
    ' ': ['   ','   ','   ','   ','   '],'0': [' █ ','█ █','█ █','█ █',' █ '],
    '1': [' █ ','██ ',' █ ',' █ ','███'],'2': ['██ ','  █',' █ ','█  ','███'],
    '3': ['██ ','  █',' █ ','  █','██ '],'4': ['█ █','█ █','███','  █','  █'],
    '5': ['███','█  ','██ ','  █','██ '],'6': [' ██','█  ','██ ','█ █',' ██'],
    '7': ['███','  █',' █ ','█  ','█  '],'8': [' █ ','█ █',' █ ','█ █',' █ '],
    '9': [' █ ','█ █',' ██','  █','██ '],
  },
  simple: {
    'A': [' .A. ','A   A','AAAAA','A   A','A   A'],'B': ['BBBB ','B   B','BBBB ','B   B','BBBB '],
    'C': [' CCCC','C    ','C    ','C    ',' CCCC'],'D': ['DDDD ','D   D','D   D','D   D','DDDD '],
    'E': ['EEEEE','E    ','EEEEE','E    ','EEEEE'],'F': ['FFFFF','F    ','FFFF ','F    ','F    '],
    'G': [' GGGG','G    ','G  GG','G   G',' GGG '],'H': ['H   H','H   H','HHHHH','H   H','H   H'],
    'I': ['IIIII','  I  ','  I  ','  I  ','IIIII'],'J': ['    J','    J','    J','J   J',' JJJ '],
    'K': ['K   K','K  K ','KKK  ','K  K ','K   K'],'L': ['L    ','L    ','L    ','L    ','LLLLL'],
    'M': ['M   M','MM MM','M M M','M   M','M   M'],'N': ['N   N','NN  N','N N N','N  NN','N   N'],
    'O': [' OOO ','O   O','O   O','O   O',' OOO '],'P': ['PPPP ','P   P','PPPP ','P    ','P    '],
    'Q': [' QQQ ','Q   Q','Q   Q','Q  Q ',' QQ Q'],'R': ['RRRR ','R   R','RRRR ','R   R','R   R'],
    'S': [' SSSS','S    ',' SSS ','    S','SSSS '],'T': ['TTTTT','  T  ','  T  ','  T  ','  T  '],
    'U': ['U   U','U   U','U   U','U   U',' UUU '],'V': ['V   V','V   V','V   V',' V V ','  V  '],
    'W': ['W   W','W   W','W W W','WW WW','W   W'],'X': ['X   X',' X X ','  X  ',' X X ','X   X'],
    'Y': ['Y   Y',' Y Y ','  Y  ','  Y  ','  Y  '],'Z': ['ZZZZZ','   Z ','  Z  ',' Z   ','ZZZZZ'],
    ' ': ['     ','     ','     ','     ','     '],'0': [' 000 ','0   0','0 0 0','0   0',' 000 '],
    '1': [' 11  ','111  ',' 11  ',' 11  ','11111'],'2': [' 222 ','2   2','   2 ','  2  ','22222'],
    '3': [' 333 ','3   3','  33 ','3   3',' 333 '],'4': ['   44 ','  4 4 ',' 4  4 ','444444','    4 '],
    '5': ['55555','5    ','5555 ','    5','5555 '],'6': [' 6666','6    ','6666 ','6   6',' 666 '],
    '7': ['77777','    7','   7 ','  7  ',' 7   '],'8': [' 888 ','8   8',' 888 ','8   8',' 888 '],
    '9': [' 999 ','9   9',' 9999','    9',' 999 '],
  },
};

const DENSITY_SIMPLE = '.-+=*#@';
const DENSITY_DETAILED = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. ";
const DENSITY_BLOCKS = '░▒▓█';

function textToAscii(text: string, fontName: string): string {
  const font = ASCII_FONTS[fontName] || ASCII_FONTS.block;
  const lines = text.toUpperCase().split('\n');
  const result: string[] = [];

  for (const line of lines) {
    const charLines: string[] = ['', '', '', '', ''];
    for (const char of line) {
      const art = font[char] || font[' '] || ['     ', '     ', '     ', '     ', '     '];
      for (let i = 0; i < 5; i++) {
        charLines[i] += (art[i] || '') + ' ';
      }
    }
    result.push(...charLines, '');
  }

  return result.join('\n');
}

function imageToAscii(img: HTMLImageElement, width: number, density: string): string {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  const aspect = img.height / img.width;
  const w = width;
  const h = Math.round(w * aspect * 0.5); // 0.5 for character aspect ratio
  canvas.width = w;
  canvas.height = h;
  ctx.drawImage(img, 0, 0, w, h);

  const imageData = ctx.getImageData(0, 0, w, h);
  const pixels = imageData.data;

  let result = '';
  for (let y = 0; y < h; y++) {
    let line = '';
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const brightness = (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
      const charIndex = Math.floor((brightness / 255) * (density.length - 1));
      line += density[density.length - 1 - charIndex];
    }
    result += line + '\n';
  }
  return result;
}

export default function AsciiArt() {
  const [activeTab, setActiveTab] = useState<AsciiTab>('text');
  const [textInput, setTextInput] = useState('HELLO');
  const [fontName, setFontName] = useState('block');
  const [asciiOutput, setAsciiOutput] = useState(() => textToAscii('HELLO', 'block'));
  const [width, setWidth] = useState(80);
  const [density, setDensity] = useState('detailed');
  const [densityChars, setDensityChars] = useState(DENSITY_DETAILED);
  const [copied, setCopied] = useState(false);
  const [drawGrid, setDrawGrid] = useState<string[][]>(() =>
    Array.from({ length: 20 }, () => Array.from({ length: 40 }, () => ' '))
  );
  const [drawChar, setDrawChar] = useState('#');
  const [isDrawing, setIsDrawing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const densityOptions = [
    { key: 'simple', label: 'Simple', chars: DENSITY_SIMPLE },
    { key: 'detailed', label: 'Detailed', chars: DENSITY_DETAILED },
    { key: 'blocks', label: 'Blocks', chars: DENSITY_BLOCKS },
  ];

  const generateTextAscii = useCallback(() => {
    const result = textToAscii(textInput, fontName);
    setAsciiOutput(result);
  }, [textInput, fontName]);

  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = document.createElement('img');
      img.onload = () => {
        const result = imageToAscii(img, width, densityChars);
        setAsciiOutput(result);
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  }, [width, densityChars]);

  const copyOutput = useCallback(async () => {
    await navigator.clipboard.writeText(asciiOutput);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [asciiOutput]);

  const downloadTxt = useCallback(() => {
    const blob = new Blob([asciiOutput], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ascii-art.txt';
    a.click();
    URL.revokeObjectURL(url);
  }, [asciiOutput]);

  const clearOutput = useCallback(() => {
    setAsciiOutput('');
  }, []);

  const handleDrawCell = useCallback((row: number, col: number) => {
    setDrawGrid((prev) => {
      const next = prev.map((r) => [...r]);
      next[row][col] = drawChar;
      return next;
    });
  }, [drawChar]);

  const drawAsciiFromGrid = useMemo(() => {
    return drawGrid.map((row) => row.join('')).join('\n');
  }, [drawGrid]);

  const clearDrawGrid = useCallback(() => {
    setDrawGrid(Array.from({ length: 20 }, () => Array.from({ length: 40 }, () => ' ')));
  }, []);

  const sampleTexts = ['HELLO', 'WORLD', 'Dulus OS', 'ASCII', 'CODE'];

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Tabs */}
      <div className="flex items-center px-3 shrink-0" style={{ height: 36, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        {([
          { key: 'text' as AsciiTab, label: 'Text to ASCII', icon: Type },
          { key: 'image' as AsciiTab, label: 'Image to ASCII', icon: Image },
          { key: 'draw' as AsciiTab, label: 'ASCII Draw', icon: Pencil },
        ]).map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className="flex items-center gap-1 px-3 py-1 text-xs font-medium transition-colors"
              style={{
                color: activeTab === t.key ? 'var(--accent-primary)' : 'var(--text-secondary)',
                borderBottom: activeTab === t.key ? '2px solid var(--accent-primary)' : '2px solid transparent',
              }}
            >
              <Icon size={12} /> {t.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Controls */}
        <div className="shrink-0 overflow-y-auto custom-scrollbar p-3" style={{ width: 220, borderRight: '1px solid var(--border-subtle)', background: 'var(--bg-window)' }}>
          {/* Text tab controls */}
          {activeTab === 'text' && (
            <>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Text</label>
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Enter text..."
                  className="w-full resize-none outline-none p-2 rounded text-xs"
                  style={{ height: 60, background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                />
              </div>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Font</label>
                <select
                  value={fontName}
                  onChange={(e) => setFontName(e.target.value)}
                  className="w-full text-xs px-1 py-1 rounded outline-none"
                  style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                >
                  <option value="block">Block</option>
                  <option value="simple">Simple</option>
                </select>
              </div>
              <button onClick={generateTextAscii} className="w-full flex items-center justify-center gap-1 px-3 py-1.5 rounded text-xs font-medium mb-3" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                <RefreshCw size={12} /> Convert
              </button>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Samples</label>
                <div className="flex flex-wrap gap-1">
                  {sampleTexts.map((s) => (
                    <button key={s} onClick={() => setTextInput(s)} className="px-2 py-0.5 rounded text-xs hover:bg-[var(--bg-hover)]" style={{ border: '1px solid var(--border-default)' }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Image tab controls */}
          {activeTab === 'image' && (
            <>
              <div className="mb-3">
                <button onClick={() => fileInputRef.current?.click()} className="w-full flex items-center justify-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                  <Image size={12} /> Upload Image
                </button>
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleImageUpload} className="hidden" />
              </div>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Width (chars): {width}</label>
                <input type="range" min={20} max={200} value={width} onChange={(e) => setWidth(Number(e.target.value))} className="w-full accent-purple-500" />
              </div>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Density</label>
                <div className="flex flex-col gap-1">
                  {densityOptions.map((opt) => (
                    <button
                      key={opt.key}
                      onClick={() => { setDensity(opt.key); setDensityChars(opt.chars); }}
                      className="text-left px-2 py-1 rounded text-xs transition-colors"
                      style={{
                        background: density === opt.key ? 'var(--accent-primary)' : 'var(--bg-hover)',
                        color: density === opt.key ? 'white' : 'var(--text-primary)',
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <input
                  value={densityChars}
                  onChange={(e) => setDensityChars(e.target.value)}
                  className="w-full mt-1 px-1 py-0.5 rounded text-xs font-mono"
                  style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                />
              </div>
            </>
          )}

          {/* Draw tab controls */}
          {activeTab === 'draw' && (
            <>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Brush Character</label>
                <input
                  value={drawChar}
                  onChange={(e) => setDrawChar(e.target.value.slice(0, 1) || ' ')}
                  maxLength={1}
                  className="w-10 px-1 py-1 rounded text-center text-xs font-mono"
                  style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
                />
              </div>
              <div className="mb-3">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-secondary)' }}>Character Palette</label>
                <div className="flex flex-wrap gap-0.5">
                  {' .-+=*#@░▒▓█/\\|()[]{}<>~_^'.split('').map((c) => (
                    <button
                      key={c}
                      onClick={() => setDrawChar(c)}
                      className="w-6 h-6 rounded text-xs font-mono flex items-center justify-center hover:bg-[var(--bg-hover)]"
                      style={{ border: drawChar === c ? '1px solid var(--accent-primary)' : '1px solid var(--border-default)' }}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={clearDrawGrid} className="w-full flex items-center justify-center gap-1 px-3 py-1.5 rounded text-xs mb-3 hover:bg-[var(--bg-hover)]" style={{ border: '1px solid var(--border-default)' }}>
                <Trash2 size={12} /> Clear Canvas
              </button>
            </>
          )}

          {/* Common actions */}
          <div className="flex flex-col gap-1">
            <button onClick={copyOutput} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
              {copied ? <Check size={12} /> : <Copy size={12} />} {copied ? 'Copied!' : 'Copy'}
            </button>
            <button onClick={downloadTxt} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
              <Download size={12} /> Download .txt
            </button>
            <button onClick={clearOutput} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)]">
              <Trash2 size={12} /> Clear
            </button>
          </div>
        </div>

        {/* Right: Output */}
        <div className="flex-1 overflow-auto p-4 custom-scrollbar" style={{ background: 'var(--bg-input)' }}>
          {activeTab === 'draw' ? (
            <div className="flex flex-col gap-2">
              {/* Draw grid */}
              <div
                className="inline-block"
                style={{ background: 'var(--bg-window)', border: '1px solid var(--border-default)', borderRadius: 4 }}
                onMouseLeave={() => setIsDrawing(false)}
              >
                {drawGrid.map((row, ri) => (
                  <div key={ri} className="flex">
                    {row.map((cell, ci) => (
                      <div
                        key={ci}
                        className="w-4 h-4 flex items-center justify-center text-[10px] font-mono cursor-pointer select-none hover:bg-[var(--bg-hover)]"
                        style={{ color: 'var(--text-primary)' }}
                        onMouseDown={() => { setIsDrawing(true); handleDrawCell(ri, ci); }}
                        onMouseEnter={() => { if (isDrawing) handleDrawCell(ri, ci); }}
                        onMouseUp={() => setIsDrawing(false)}
                      >
                        {cell}
                      </div>
                    ))}
                  </div>
                ))}
              </div>

              {/* ASCII output from grid */}
              <pre className="text-xs font-mono p-3 rounded" style={{ background: 'var(--bg-window)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}>
                {drawAsciiFromGrid}
              </pre>
            </div>
          ) : (
            <pre className="text-xs font-mono leading-none" style={{ color: 'var(--text-primary)' }}>
              {asciiOutput || (
                <span style={{ color: 'var(--text-disabled)' }}>Output will appear here...</span>
              )}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
