// ============================================================
// JSON Formatter — Format, validate, minify, tree view
// ============================================================

import { useState, useCallback } from 'react';
import { useFileSystem } from '@/hooks/useFileSystem';
import {
  Wand2, Minimize2, Check, X, Copy, Download,
  ChevronRight, ChevronDown, Search, FileUp, Trash2,
  Braces,
} from 'lucide-react';

interface JsonNodeProps {
  data: unknown;
  keyName?: string;
  depth?: number;
  searchQuery?: string;
}

function JsonNode({ data, keyName, depth = 0, searchQuery = '' }: JsonNodeProps) {
  const [expanded, setExpanded] = useState(true);

  const toggle = useCallback(() => setExpanded((v) => !v), []);

  if (data === null) {
    return (
      <div className="flex items-center py-0.5" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
        <span className="text-xs" style={{ color: '#569CD6' }}>null</span>
      </div>
    );
  }

  if (typeof data === 'boolean') {
    return (
      <div className="flex items-center py-0.5" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
        <span className="text-xs" style={{ color: '#569CD6' }}>{data.toString()}</span>
      </div>
    );
  }

  if (typeof data === 'number') {
    return (
      <div className="flex items-center py-0.5" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
        <span className="text-xs" style={{ color: '#B5CEA8' }}>{data}</span>
      </div>
    );
  }

  if (typeof data === 'string') {
    const displayStr = `"${data}"`;
    const isMatch = searchQuery && data.toLowerCase().includes(searchQuery.toLowerCase());
    return (
      <div className="flex items-center py-0.5" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
        <span className={`text-xs break-all ${isMatch ? 'bg-yellow-500/20' : ''}`} style={{ color: '#CE9178' }}>{displayStr}</span>
      </div>
    );
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return (
        <div className="flex items-center py-0.5" style={{ paddingLeft: depth * 16 }}>
          {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>[]</span>
        </div>
      );
    }
    return (
      <div>
        <div
          className="flex items-center py-0.5 cursor-pointer hover:bg-[var(--bg-hover)]"
          style={{ paddingLeft: depth * 16 }}
          onClick={toggle}
        >
          {expanded ? <ChevronDown size={12} className="mr-1" /> : <ChevronRight size={12} className="mr-1" />}
          {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>[{data.length} items]</span>
        </div>
        {expanded && data.map((item, i) => (
          <JsonNode key={i} data={item} depth={depth + 1} searchQuery={searchQuery} />
        ))}
      </div>
    );
  }

  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>);
    if (entries.length === 0) {
      return (
        <div className="flex items-center py-0.5" style={{ paddingLeft: depth * 16 }}>
          {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{'{}'}</span>
        </div>
      );
    }
    return (
      <div>
        <div
          className="flex items-center py-0.5 cursor-pointer hover:bg-[var(--bg-hover)]"
          style={{ paddingLeft: depth * 16 }}
          onClick={toggle}
        >
          {expanded ? <ChevronDown size={12} className="mr-1" /> : <ChevronRight size={12} className="mr-1" />}
          {keyName && <span className="text-xs mr-1" style={{ color: '#9CDCFE' }}>{`"${keyName}": `}</span>}
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{'{'} {entries.length} properties {'}'}</span>
        </div>
        {expanded && entries.map(([k, v]) => (
          <JsonNode key={k} data={v} keyName={k} depth={depth + 1} searchQuery={searchQuery} />
        ))}
      </div>
    );
  }

  return null;
}

function getJsonStats(data: unknown): { keyCount: number; arrayCount: number; maxDepth: number } {
  let keyCount = 0;
  let arrayCount = 0;

  const getDepth = (d: unknown): number => {
    if (Array.isArray(d)) {
      arrayCount++;
      return 1 + Math.max(0, ...d.map(getDepth));
    }
    if (d && typeof d === 'object') {
      keyCount += Object.keys(d).length;
      return 1 + Math.max(0, ...Object.values(d).map(getDepth));
    }
    return 0;
  };

  const maxDepth = getDepth(data);
  return { keyCount, arrayCount, maxDepth };
}

export default function JsonFormatter() {
  const fs = useFileSystem();
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [viewMode, setViewMode] = useState<'formatted' | 'tree'>('tree');
  const [indent, setIndent] = useState(2);
  const [error, setError] = useState('');
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [parsedData, setParsedData] = useState<unknown>(null);
  const [stats, setStats] = useState({ keyCount: 0, arrayCount: 0, maxDepth: 0 });
  const [copied, setCopied] = useState(false);

  const validateJson = useCallback((text: string) => {
    try {
      JSON.parse(text);
      return { valid: true, error: '' };
    } catch (e) {
      return { valid: false, error: (e as Error).message };
    }
  }, []);

  const processJson = useCallback((text: string) => {
    const { valid, error } = validateJson(text);
    setIsValid(valid);
    setError(error);
    if (valid) {
      const data = JSON.parse(text);
      setParsedData(data);
      setOutput(JSON.stringify(data, null, indent));
      setStats(getJsonStats(data));
    } else {
      setParsedData(null);
      setOutput('');
      setStats({ keyCount: 0, arrayCount: 0, maxDepth: 0 });
    }
  }, [validateJson, indent]);

  const formatJson = useCallback(() => {
    if (!input.trim()) return;
    processJson(input);
  }, [input, processJson]);

  const minifyJson = useCallback(() => {
    if (!input.trim()) return;
    try {
      const data = JSON.parse(input);
      const minified = JSON.stringify(data);
      setOutput(minified);
      setError('');
      setIsValid(true);
      setParsedData(data);
      setStats(getJsonStats(data));
      setViewMode('formatted');
    } catch (e) {
      setError((e as Error).message);
      setIsValid(false);
    }
  }, [input]);

  const validate = useCallback(() => {
    if (!input.trim()) return;
    processJson(input);
  }, [input, processJson]);

  const clearAll = useCallback(() => {
    setInput('');
    setOutput('');
    setParsedData(null);
    setError('');
    setIsValid(null);
    setStats({ keyCount: 0, arrayCount: 0, maxDepth: 0 });
  }, []);

  const copyOutput = useCallback(async () => {
    if (!output) return;
    await navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [output]);

  const downloadJson = useCallback(() => {
    if (!output) return;
    const blob = new Blob([output], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'formatted.json';
    a.click();
    URL.revokeObjectURL(url);
  }, [output]);

  const loadSample = useCallback(() => {
    const sample = {
      name: 'Dulus OS',
      version: '1.0.0',
      description: 'A web-based Linux desktop environment',
      features: ['File Manager', 'Terminal', 'Code Editor', 'Browser'],
      config: {
        theme: { mode: 'dark', accent: '#7C4DFF' },
        desktop: { icons: 8, wallpaper: 'default' },
      },
      contributors: [
        { name: 'Alice', role: 'Developer' },
        { name: 'Bob', role: 'Designer' },
      ],
    };
    const text = JSON.stringify(sample);
    setInput(text);
    processJson(text);
  }, [processJson]);

  const handleInputChange = useCallback((text: string) => {
    setInput(text);
    if (text.trim()) {
      const { valid, error } = validateJson(text);
      setIsValid(valid);
      setError(error);
      if (valid) {
        const data = JSON.parse(text);
        setParsedData(data);
        setOutput(JSON.stringify(data, null, indent));
        setStats(getJsonStats(data));
      }
    } else {
      setIsValid(null);
      setError('');
    }
  }, [validateJson, indent]);

  const loadFromFS = useCallback(() => {
    const docs = Object.values(fs.fs.nodes).find(
      (n) => n.name === 'Documents' && n.parentId
    );
    if (!docs) return;
    const files = fs.getChildren(docs.id).filter((n) => n.type === 'file' && n.name.endsWith('.json'));
    if (files.length > 0) {
      const content = fs.readFile(files[0].id) || '';
      setInput(content);
      processJson(content);
    }
  }, [fs, processJson]);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        <button onClick={formatJson} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors" style={{ background: 'var(--accent-primary)', color: 'white' }}>
          <Wand2 size={13} /> Format
        </button>
        <button onClick={minifyJson} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ border: '1px solid var(--border-default)' }}>
          <Minimize2 size={13} /> Minify
        </button>
        <button onClick={validate} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ border: '1px solid var(--border-default)' }}>
          <Check size={13} /> Validate
        </button>
        <button onClick={clearAll} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ border: '1px solid var(--border-default)' }}>
          <Trash2 size={13} /> Clear
        </button>
        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={copyOutput} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ border: '1px solid var(--border-default)' }}>
          <Copy size={13} /> {copied ? 'Copied!' : 'Copy'}
        </button>
        <button onClick={downloadJson} className="flex items-center gap-1 px-2.5 py-1 rounded text-xs hover:bg-[var(--bg-hover)] transition-colors" style={{ border: '1px solid var(--border-default)' }}>
          <Download size={13} /> Download
        </button>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Indent:</span>
          <select
            value={indent}
            onChange={(e) => { setIndent(Number(e.target.value)); if (input) processJson(input); }}
            className="text-xs px-1 py-0.5 rounded outline-none"
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
          >
            <option value={2}>2 spaces</option>
            <option value={4}>4 spaces</option>
          </select>
          <select
            value={viewMode}
            onChange={(e) => setViewMode(e.target.value as 'formatted' | 'tree')}
            className="text-xs px-1 py-0.5 rounded outline-none"
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
          >
            <option value="tree">Tree</option>
            <option value="formatted">Text</option>
          </select>
        </div>
      </div>

      {/* Validation status */}
      {isValid !== null && (
        <div className="flex items-center gap-2 px-3 py-1 shrink-0" style={{
          background: isValid ? 'rgba(76,175,80,0.1)' : 'rgba(244,67,54,0.1)',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          {isValid ? <Check size={14} className="text-green-500" /> : <X size={14} className="text-red-500" />}
          <span className="text-xs" style={{ color: isValid ? '#4CAF50' : '#F44336' }}>
            {isValid ? 'Valid JSON' : error}
          </span>
          {isValid && stats.keyCount > 0 && (
            <span className="text-xs ml-auto" style={{ color: 'var(--text-secondary)' }}>
              {stats.keyCount} keys | {stats.arrayCount} arrays | depth {stats.maxDepth} | {new Blob([input]).size} bytes
            </span>
          )}
        </div>
      )}

      {/* Main area: input + output */}
      <div className="flex-1 flex overflow-hidden">
        {/* Input */}
        <div className="flex-1 flex flex-col overflow-hidden" style={{ borderRight: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center justify-between px-2 py-0.5 shrink-0" style={{ background: 'var(--bg-titlebar)' }}>
            <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Input</span>
            <div className="flex gap-1">
              <button onClick={loadSample} className="text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">Sample</button>
              <button onClick={loadFromFS} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">
                <FileUp size={10} /> Load
              </button>
            </div>
          </div>
          <textarea
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            placeholder="Paste your JSON here..."
            spellCheck={false}
            className="flex-1 w-full resize-none outline-none p-3 custom-scrollbar"
            style={{ background: 'var(--bg-input)', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, lineHeight: '18px', color: 'var(--text-primary)' }}
          />
        </div>

        {/* Output */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-2 py-0.5 shrink-0" style={{ background: 'var(--bg-titlebar)' }}>
            <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Output</span>
            <div className="flex items-center gap-1">
              <Search size={12} className="text-[var(--text-secondary)]" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
                className="text-xs px-1.5 py-0.5 rounded outline-none w-28"
                style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
              />
            </div>
          </div>
          <div className="flex-1 overflow-auto p-2 custom-scrollbar">
            {viewMode === 'tree' && parsedData ? (
              <JsonNode data={parsedData} searchQuery={searchQuery} />
            ) : output ? (
              <pre className="text-xs whitespace-pre-wrap break-all" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{output}</pre>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Braces size={36} className="text-[var(--text-disabled)]" />
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Formatted output will appear here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
