// ============================================================
// Base64 Tool — Encode/Decode, JWT, URL, Hex
// ============================================================

import { useState, useCallback, useMemo } from 'react';
import {
  ArrowRight, ArrowLeft, Copy, Check,
  Trash2, Clock,
} from 'lucide-react';

type ToolTab = 'encode' | 'decode' | 'jwt' | 'url' | 'hex';

interface HistoryItem {
  id: string;
  tab: ToolTab;
  input: string;
  output: string;
  timestamp: number;
}

function isValidBase64(s: string): boolean {
  try { return btoa(atob(s)) === s; } catch { return false; }
}

function safeBtoa(s: string): string {
  try { return btoa(s); } catch { return ''; }
}

function safeAtob(s: string): string {
  try { return atob(s); } catch { return ''; }
}

function base64UrlDecode(str: string): string {
  let padded = str.replace(/-/g, '+').replace(/_/g, '/');
  while (padded.length % 4) padded += '=';
  try { return atob(padded); } catch { return '{}'; }
}

function decodeJwt(token: string): { header: string; payload: string; signature: string } | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  return {
    header: base64UrlDecode(parts[0]),
    payload: base64UrlDecode(parts[1]),
    signature: parts[2],
  };
}

function getJwtExpiry(payload: string): Date | null {
  try {
    const p = JSON.parse(payload);
    if (p.exp) return new Date(p.exp * 1000);
    return null;
  } catch { return null; }
}

const TAB_LABELS: { key: ToolTab; label: string }[] = [
  { key: 'encode', label: 'Base64 Encode' },
  { key: 'decode', label: 'Base64 Decode' },
  { key: 'jwt', label: 'JWT Decode' },
  { key: 'url', label: 'URL Encode' },
  { key: 'hex', label: 'Hex' },
];

export default function Base64Tool() {
  const [activeTab, setActiveTab] = useState<ToolTab>('encode');
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [isUrlSafe, setIsUrlSafe] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [jwtToken, setJwtToken] = useState('');
  const [decodedJwt, setDecodedJwt] = useState<ReturnType<typeof decodeJwt>>(null);

  const addToHistory = useCallback((tab: ToolTab, inp: string, out: string) => {
    if (!inp || !out) return;
    setHistory((prev) => [{
      id: Date.now().toString(), tab, input: inp.slice(0, 100), output: out.slice(0, 100), timestamp: Date.now(),
    }, ...prev].slice(0, 20));
  }, []);

  const encodeBase64 = useCallback(() => {
    setError('');
    let result = safeBtoa(input);
    if (isUrlSafe) {
      result = result.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }
    setOutput(result);
    if (result) addToHistory('encode', input, result);
  }, [input, isUrlSafe, addToHistory]);

  const decodeBase64 = useCallback(() => {
    setError('');
    let text = input;
    if (isUrlSafe) {
      text = text.replace(/-/g, '+').replace(/_/g, '/');
      while (text.length % 4) text += '=';
    }
    if (!isValidBase64(text)) {
      setError('Invalid Base64 string');
      setOutput('');
      return;
    }
    const result = safeAtob(text);
    setOutput(result);
    addToHistory('decode', input, result);
  }, [input, isUrlSafe, addToHistory]);

  const processUrl = useCallback((encode: boolean) => {
    setError('');
    try {
      const result = encode ? encodeURIComponent(input) : decodeURIComponent(input);
      setOutput(result);
      addToHistory('url', input, result);
    } catch (e) {
      setError((e as Error).message);
      setOutput('');
    }
  }, [input, addToHistory]);

  const processHex = useCallback((encode: boolean) => {
    setError('');
    try {
      if (encode) {
        const result = input.split('').map((c) => c.charCodeAt(0).toString(16).padStart(2, '0')).join(' ');
        setOutput(result);
        addToHistory('hex', input, result);
      } else {
        const result = input.replace(/\s/g, '').match(/.{1,2}/g)?.map((b) => String.fromCharCode(parseInt(b, 16))).join('') || '';
        setOutput(result);
        addToHistory('hex', input, result);
      }
    } catch (e) {
      setError('Invalid hex input');
      setOutput('');
    }
  }, [input, addToHistory]);

  const processJwt = useCallback((token: string) => {
    setError('');
    setJwtToken(token);
    const decoded = decodeJwt(token.trim());
    if (!decoded) {
      setError('Invalid JWT token (expected 3 parts separated by dots)');
      setDecodedJwt(null);
      return;
    }
    setDecodedJwt(decoded);
  }, []);

  const copyOutput = useCallback(async () => {
    if (!output) return;
    await navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [output]);

  const clearAll = useCallback(() => {
    setInput('');
    setOutput('');
    setError('');
  }, []);

  const byteSize = useMemo(() => new Blob([input]).size, [input]);
  const outSize = useMemo(() => new Blob([output]).size, [output]);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Tabs */}
      <div className="flex items-center px-3 shrink-0" style={{ height: 36, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        {TAB_LABELS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setActiveTab(t.key); setError(''); setOutput(''); }}
            className="px-3 py-1 text-xs font-medium transition-colors"
            style={{
              color: activeTab === t.key ? 'var(--accent-primary)' : 'var(--text-secondary)',
              borderBottom: activeTab === t.key ? '2px solid var(--accent-primary)' : '2px solid transparent',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main area */}
        <div className="flex-1 flex flex-col overflow-hidden p-4 gap-3">
          {/* JWT tab */}
          {activeTab === 'jwt' && (
            <div className="flex flex-col gap-3">
              <div>
                <span className="text-xs font-semibold block mb-1" style={{ color: 'var(--text-secondary)' }}>JWT Token</span>
                <textarea
                  value={jwtToken}
                  onChange={(e) => processJwt(e.target.value)}
                  placeholder="Paste JWT token here..."
                  spellCheck={false}
                  className="w-full resize-none outline-none p-3 rounded text-xs custom-scrollbar"
                  style={{ height: 80, background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', fontFamily: "'JetBrains Mono', monospace" }}
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 px-2 py-1 rounded" style={{ background: 'rgba(244,67,54,0.1)' }}>
                  <span className="text-xs text-red-400">{error}</span>
                </div>
              )}

              {decodedJwt && (
                <div className="flex flex-col gap-2">
                  {/* Header */}
                  <div className="p-3 rounded" style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold" style={{ color: 'var(--accent-primary)' }}>HEADER</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-active)', color: 'var(--text-secondary)' }}>ALGORITHM</span>
                    </div>
                    <pre className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>
                      {JSON.stringify(JSON.parse(decodedJwt.header), null, 2)}
                    </pre>
                  </div>

                  {/* Payload */}
                  <div className="p-3 rounded" style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold" style={{ color: 'var(--accent-success)' }}>PAYLOAD</span>
                      {(() => {
                        const exp = getJwtExpiry(decodedJwt.payload);
                        if (!exp) return null;
                        const isExpired = exp.getTime() < Date.now();
                        return (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${isExpired ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                            {isExpired ? 'Expired' : `Exp: ${exp.toLocaleString()}`}
                          </span>
                        );
                      })()}
                    </div>
                    <pre className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>
                      {JSON.stringify(JSON.parse(decodedJwt.payload), null, 2)}
                    </pre>
                  </div>

                  {/* Signature */}
                  <div className="p-3 rounded" style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}>
                    <span className="text-xs font-semibold block mb-1" style={{ color: 'var(--accent-warning)' }}>SIGNATURE</span>
                    <span className="text-xs break-all font-mono" style={{ color: 'var(--text-secondary)' }}>{decodedJwt.signature}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Encode/Decode/URL/Hex tabs */}
          {activeTab !== 'jwt' && (
            <>
              {/* Input */}
              <div className="flex-1 flex flex-col">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                    {activeTab === 'encode' ? 'Text to encode' : activeTab === 'decode' ? 'Base64 to decode' : activeTab === 'url' ? 'Text to encode/decode' : 'Text / Hex'}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--text-disabled)' }}>{input.length} chars | {byteSize} bytes</span>
                </div>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Enter text..."
                  spellCheck={false}
                  className="flex-1 w-full resize-none outline-none p-3 rounded text-xs custom-scrollbar"
                  style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', fontFamily: "'JetBrains Mono', monospace" }}
                />
              </div>

              {/* Controls */}
              <div className="flex items-center gap-2 shrink-0">
                {(activeTab === 'encode' || activeTab === 'decode') && (
                  <label className="flex items-center gap-1 text-xs cursor-pointer">
                    <input type="checkbox" checked={isUrlSafe} onChange={(e) => setIsUrlSafe(e.target.checked)} className="accent-purple-500" />
                    <span style={{ color: 'var(--text-secondary)' }}>URL-safe</span>
                  </label>
                )}

                {activeTab === 'encode' && (
                  <button onClick={encodeBase64} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                    <ArrowRight size={12} /> Encode
                  </button>
                )}
                {activeTab === 'decode' && (
                  <button onClick={decodeBase64} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                    <ArrowLeft size={12} /> Decode
                  </button>
                )}
                {activeTab === 'url' && (
                  <>
                    <button onClick={() => processUrl(true)} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                      <ArrowRight size={12} /> Encode
                    </button>
                    <button onClick={() => processUrl(false)} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border-default)' }}>
                      <ArrowLeft size={12} /> Decode
                    </button>
                  </>
                )}
                {activeTab === 'hex' && (
                  <>
                    <button onClick={() => processHex(true)} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                      <ArrowRight size={12} /> To Hex
                    </button>
                    <button onClick={() => processHex(false)} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border-default)' }}>
                      <ArrowLeft size={12} /> From Hex
                    </button>
                  </>
                )}

                <button onClick={clearAll} className="p-1.5 rounded hover:bg-[var(--bg-hover)]">
                  <Trash2 size={14} style={{ color: 'var(--text-secondary)' }} />
                </button>

                {error && <span className="text-xs text-red-400 ml-2">{error}</span>}
              </div>

              {/* Output */}
              {output && (
                <div className="flex-1 flex flex-col">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Output</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs" style={{ color: 'var(--text-disabled)' }}>{output.length} chars | {outSize} bytes</span>
                      <button onClick={copyOutput} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">
                        {copied ? <Check size={10} /> : <Copy size={10} />} {copied ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={output}
                    readOnly
                    className="flex-1 w-full resize-none outline-none p-3 rounded text-xs custom-scrollbar"
                    style={{ background: 'var(--bg-hover)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', fontFamily: "'JetBrains Mono', monospace" }}
                  />
                </div>
              )}
            </>
          )}
        </div>

        {/* History sidebar */}
        <div className="shrink-0 overflow-y-auto custom-scrollbar p-2" style={{ width: 180, borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-window)' }}>
          <div className="flex items-center gap-1 mb-2">
            <Clock size={12} style={{ color: 'var(--text-secondary)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>HISTORY</span>
          </div>
          {history.map((h) => (
            <div key={h.id} className="p-1.5 rounded mb-1" style={{ background: 'var(--bg-hover)' }}>
              <span className="text-[10px] px-1 py-0.5 rounded" style={{ background: 'var(--bg-active)', color: 'var(--text-secondary)' }}>{h.tab}</span>
              <div className="text-[10px] mt-0.5 truncate font-mono" style={{ color: 'var(--text-secondary)' }}>{h.input}</div>
              <div className="text-[10px] truncate font-mono" style={{ color: 'var(--accent-primary)' }}>{h.output}</div>
            </div>
          ))}
          {history.length === 0 && <p className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>No history yet</p>}
        </div>
      </div>
    </div>
  );
}
