// ============================================================
// Text Editor — Multi-file text editor with syntax highlighting
// ============================================================

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  FileText, FolderOpen, Save, Search, X, Plus, WrapText,
  Hash, ZoomIn, ZoomOut,
} from 'lucide-react';
import { useFileSystem } from '@/hooks/useFileSystem';

interface OpenFile {
  id: string;
  name: string;
  content: string;
  isModified: boolean;
  cursorLine: number;
  cursorCol: number;
}

const HIGHLIGHT_PATTERNS: Record<string, { pattern: RegExp; color: string }[]> = {
  js: [
    { pattern: /\/\/.*$/gm, color: '#6A9955' },
    { pattern: /\/\*[\s\S]*?\*\//g, color: '#6A9955' },
    { pattern: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, color: '#CE9178' },
    { pattern: /\b(const|let|var|function|return|if|else|for|while|class|import|export|from|async|await|new|this|try|catch|throw|typeof|instanceof)\b/g, color: '#569CD6' },
    { pattern: /\b(true|false|null|undefined)\b/g, color: '#569CD6' },
    { pattern: /\b\d+(?:\.\d+)?\b/g, color: '#B5CEA8' },
  ],
  ts: [
    { pattern: /\/\/.*$/gm, color: '#6A9955' },
    { pattern: /\/\*[\s\S]*?\*\//g, color: '#6A9955' },
    { pattern: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, color: '#CE9178' },
    { pattern: /\b(const|let|var|function|return|if|else|for|while|class|import|export|from|async|await|new|this|try|catch|interface|type|extends|implements|readonly)\b/g, color: '#569CD6' },
    { pattern: /\b(string|number|boolean|any|void|null|undefined|true|false)\b/g, color: '#4EC9B0' },
    { pattern: /\b\d+(?:\.\d+)?\b/g, color: '#B5CEA8' },
  ],
  json: [
    { pattern: /"(?:[^"\\]|\\.)*"(?=\s*:)/g, color: '#9CDCFE' },
    { pattern: /"(?:[^"\\]|\\.)*"/g, color: '#CE9178' },
    { pattern: /\b(true|false|null)\b/g, color: '#569CD6' },
    { pattern: /\b\d+(?:\.\d+)?\b/g, color: '#B5CEA8' },
  ],
  md: [
    { pattern: /^#{1,6}\s+.*/gm, color: '#569CD6' },
    { pattern: /\*\*(?:[^*]+)\*\*/g, color: '#CE9178' },
    { pattern: /`[^`]+`/g, color: '#DCDCAA' },
    { pattern: /^\s*[-*+]\s+/gm, color: '#6796E6' },
    { pattern: /^\s*\d+\.\s+/gm, color: '#6796E6' },
  ],
};

const getFileExt = (name: string): string => {
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
  if (ext === '.js' || ext === '.jsx') return 'js';
  if (ext === '.ts' || ext === '.tsx') return 'ts';
  if (ext === '.json') return 'json';
  if (ext === '.md') return 'md';
  return '';
};

const TextEditor: React.FC = () => {
  const { fs, readFile, writeFile, createFile } = useFileSystem();
  const [files, setFiles] = useState<OpenFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [showOpen, setShowOpen] = useState(false);
  const [showFind, setShowFind] = useState(false);
  const [findQuery, setFindQuery] = useState('');
  const [fontSize, setFontSize] = useState(13);
  const [wordWrap, setWordWrap] = useState(true);
  const [showLineNumbers, setShowLineNumbers] = useState(true);
  const [recentFiles, setRecentFiles] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('texteditor_recent') || '[]'); } catch { return []; }
  });
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const activeFile = files.find(f => f.id === activeFileId) || null;
  const lines = useMemo(() => activeFile ? activeFile.content.split('\n') : [], [activeFile]);

  const saveRecent = useCallback((ids: string[]) => {
    setRecentFiles(ids);
    localStorage.setItem('texteditor_recent', JSON.stringify(ids));
  }, []);

  const newFile = () => {
    const id = 'new-' + Date.now();
    const file: OpenFile = { id, name: 'Untitled.txt', content: '', isModified: false, cursorLine: 1, cursorCol: 1 };
    setFiles(prev => [...prev, file]);
    setActiveFileId(id);
  };

  const openFileById = (nodeId: string) => {
    const node = fs.nodes[nodeId];
    if (!node || node.type !== 'file') return;
    const content = readFile(nodeId) || '';
    const existing = files.find(f => f.id === nodeId);
    if (existing) {
      setActiveFileId(nodeId);
      return;
    }
    const file: OpenFile = { id: nodeId, name: node.name, content, isModified: false, cursorLine: 1, cursorCol: 1 };
    setFiles(prev => [...prev, file]);
    setActiveFileId(nodeId);
    setShowOpen(false);
    const updated = [nodeId, ...recentFiles.filter(r => r !== nodeId)].slice(0, 10);
    saveRecent(updated);
  };

  const saveActiveFile = () => {
    if (!activeFile) return;
    if (activeFile.id.startsWith('new-')) {
      // Save as new file in Documents
      const docsNode = Object.values(fs.nodes).find(n => n.name === 'Documents');
      if (docsNode) {
        const newId = createFile(docsNode.id, activeFile.name, activeFile.content);
        setFiles(prev => prev.map(f => f.id === activeFile.id ? { ...f, id: newId, isModified: false } : f));
        setActiveFileId(newId);
        const updated = [newId, ...recentFiles.filter(r => r !== newId)].slice(0, 10);
        saveRecent(updated);
      }
    } else {
      writeFile(activeFile.id, activeFile.content);
      setFiles(prev => prev.map(f => f.id === activeFile.id ? { ...f, isModified: false } : f));
    }
  };

  const closeFile = (id: string) => {
    setFiles(prev => {
      const filtered = prev.filter(f => f.id !== id);
      if (activeFileId === id) {
        setActiveFileId(filtered.length > 0 ? filtered[filtered.length - 1].id : null);
      }
      return filtered;
    });
  };

  const updateContent = (content: string) => {
    if (!activeFile) return;
    setFiles(prev => prev.map(f => f.id === activeFile.id ? { ...f, content, isModified: true } : f));
  };

  const handleCursorChange = () => {
    const ta = textareaRef.current;
    if (!ta || !activeFile) return;
    const val = ta.value;
    const pos = ta.selectionStart;
    const line = val.slice(0, pos).split('\n').length;
    const col = pos - val.lastIndexOf('\n', pos - 1);
    setFiles(prev => prev.map(f => f.id === activeFile.id ? { ...f, cursorLine: line, cursorCol: col } : f));
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveActiveFile();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        setShowFind(v => !v);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        newFile();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
        e.preventDefault();
        setShowOpen(true);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [activeFile, files]);

  // Highlighted lines
  const renderHighlighted = (line: string, ext: string) => {
    if (!ext || !HIGHLIGHT_PATTERNS[ext]) return line;
    const patterns = HIGHLIGHT_PATTERNS[ext];
    // Simple approach: wrap matches in spans
    let result: React.ReactNode[] = [line];
    patterns.forEach(({ pattern, color }) => {
      const newResult: React.ReactNode[] = [];
      result.forEach((node, i) => {
        if (typeof node !== 'string') { newResult.push(node); return; }
        let lastIndex = 0;
        const matches = [...node.matchAll(new RegExp(pattern, 'g'))];
        matches.forEach((match) => {
          const idx = match.index ?? 0;
          if (idx > lastIndex) newResult.push(node.slice(lastIndex, idx));
          newResult.push(<span key={`${i}-${idx}`} style={{ color }}>{match[0]}</span>);
          lastIndex = idx + match[0].length;
        });
        if (lastIndex < node.length) newResult.push(node.slice(lastIndex));
      });
      result = newResult;
    });
    return result;
  };

  // Open dialog file list
  const allFiles = Object.values(fs.nodes).filter(n => n.type === 'file');
  const getFilePath = (node: typeof allFiles[0]): string => {
    const parts: string[] = [];
    let current: typeof node | undefined = node;
    while (current) {
      parts.unshift(current.name);
      current = current.parentId ? fs.nodes[current.parentId] : undefined;
    }
    return parts.join('/');
  };

  const fileExt = activeFile ? getFileExt(activeFile.name) : '';

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 h-10 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <button onClick={newFile} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)] text-[var(--text-primary)]" title="New (Ctrl+N)">
          <Plus size={14} /> New
        </button>
        <button onClick={() => setShowOpen(true)} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)] text-[var(--text-primary)]" title="Open (Ctrl+O)">
          <FolderOpen size={14} /> Open
        </button>
        <button onClick={saveActiveFile} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)] text-[var(--text-primary)]" title="Save (Ctrl+S)">
          <Save size={14} /> Save
        </button>
        <div className="w-px h-5 mx-1" style={{ background: 'var(--border-subtle)' }} />
        <button onClick={() => setShowFind(!showFind)} className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--bg-hover)] text-[var(--text-primary)]">
          <Search size={14} /> Find
        </button>
        <button onClick={() => setWordWrap(!wordWrap)} className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${wordWrap ? 'text-[var(--accent-primary)]' : 'text-[var(--text-primary)]'} hover:bg-[var(--bg-hover)]`} title="Word Wrap">
          <WrapText size={14} />
        </button>
        <button onClick={() => setShowLineNumbers(!showLineNumbers)} className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${showLineNumbers ? 'text-[var(--accent-primary)]' : 'text-[var(--text-primary)]'} hover:bg-[var(--bg-hover)]`} title="Line Numbers">
          <Hash size={14} />
        </button>
        <div className="flex-1" />
        <button onClick={() => setFontSize(s => Math.max(8, s - 1))} className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]">
          <ZoomOut size={14} />
        </button>
        <span className="text-[10px] text-[var(--text-secondary)] w-6 text-center">{fontSize}</span>
        <button onClick={() => setFontSize(s => Math.min(32, s + 1))} className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]">
          <ZoomIn size={14} />
        </button>
      </div>

      {/* Find bar */}
      {showFind && (
        <div className="flex items-center gap-2 px-3 h-9 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
          <Search size={14} className="text-[var(--text-secondary)]" />
          <input
            autoFocus
            value={findQuery}
            onChange={e => setFindQuery(e.target.value)}
            placeholder="Find..."
            className="flex-1 bg-transparent text-xs text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
          />
          <button onClick={() => setShowFind(false)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Tabs */}
      {files.length > 0 && (
        <div className="flex items-center gap-0 border-b overflow-x-auto custom-scrollbar" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
          {files.map(f => (
            <button
              key={f.id}
              onClick={() => setActiveFileId(f.id)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border-r min-w-0 shrink-0 transition-colors"
              style={{
                borderColor: 'var(--border-subtle)',
                background: activeFileId === f.id ? 'var(--bg-window)' : 'transparent',
                color: activeFileId === f.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                borderBottom: activeFileId === f.id ? '2px solid var(--accent-primary)' : '2px solid transparent',
              }}
            >
              <FileText size={12} />
              <span className="truncate max-w-[120px]">{f.isModified ? '● ' : ''}{f.name}</span>
              <button
                onClick={e => { e.stopPropagation(); closeFile(f.id); }}
                className="ml-1 hover:text-[var(--accent-error)]"
              >
                <X size={12} />
              </button>
            </button>
          ))}
        </div>
      )}

      {/* Editor area */}
      {activeFile ? (
        <div className="flex-1 flex overflow-hidden relative">
          {/* Line numbers */}
          {showLineNumbers && (
            <div
              className="shrink-0 overflow-hidden py-2 text-right select-none"
              style={{
                width: 48,
                background: 'var(--bg-titlebar)',
                borderRight: '1px solid var(--border-subtle)',
                fontSize,
                lineHeight: `${fontSize + 6}px`,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {lines.map((_, i) => (
                <div
                  key={i}
                  className="px-2"
                  style={{
                    color: i + 1 === activeFile.cursorLine ? 'var(--text-primary)' : 'var(--text-disabled)',
                    fontWeight: i + 1 === activeFile.cursorLine ? 600 : 400,
                  }}
                >
                  {i + 1}
                </div>
              ))}
            </div>
          )}

          {/* Textarea + highlight overlay */}
          <div className="flex-1 relative overflow-auto custom-scrollbar">
            <textarea
              ref={textareaRef}
              value={activeFile.content}
              onChange={e => updateContent(e.target.value)}
              onKeyUp={handleCursorChange}
              onClick={handleCursorChange}
              spellCheck={false}
              className="absolute inset-0 w-full h-full resize-none outline-none bg-transparent text-transparent caret-[var(--text-primary)] p-2 z-10"
              style={{
                fontSize,
                lineHeight: `${fontSize + 6}px`,
                fontFamily: "'JetBrains Mono', monospace",
                whiteSpace: wordWrap ? 'pre-wrap' : 'pre',
                tabSize: 4,
              }}
            />
            {/* Syntax highlight overlay */}
            <div
              className="absolute inset-0 pointer-events-none p-2"
              style={{
                fontSize,
                lineHeight: `${fontSize + 6}px`,
                fontFamily: "'JetBrains Mono', monospace",
                whiteSpace: wordWrap ? 'pre-wrap' : 'pre',
                tabSize: 4,
                color: 'var(--text-primary)',
              }}
            >
              {fileExt && HIGHLIGHT_PATTERNS[fileExt]
                ? lines.map((line, i) => (
                  <div key={i}>{renderHighlighted(line, fileExt)}</div>
                ))
                : activeFile.content
              }
            </div>
          </div>

          {/* Find matches indicator */}
          {showFind && findQuery && (
            <div className="absolute bottom-8 right-4 px-2 py-1 rounded text-[10px]" style={{ background: 'var(--accent-primary)', color: 'white' }}>
              {(activeFile.content.match(new RegExp(findQuery, 'g')) || []).length} matches
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <FileText size={48} className="text-[var(--text-disabled)] opacity-30" />
          <div className="text-sm text-[var(--text-secondary)]">Open a file or create a new document</div>
          <div className="flex gap-2">
            <button onClick={newFile} className="px-4 py-2 rounded text-xs font-medium" style={{ background: 'var(--accent-primary)', color: 'white' }}>
              New File
            </button>
            <button onClick={() => setShowOpen(true)} className="px-4 py-2 rounded text-xs font-medium border" style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}>
              Open File
            </button>
          </div>
          {recentFiles.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] text-[var(--text-disabled)] uppercase tracking-wider mb-2 text-center">Recent Files</div>
              {recentFiles.slice(0, 5).map(rf => {
                const node = fs.nodes[rf];
                if (!node) return null;
                return (
                  <button
                    key={rf}
                    onClick={() => openFileById(rf)}
                    className="flex items-center gap-2 w-full px-3 py-1.5 rounded text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                  >
                    <FileText size={12} /> {node.name}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Status bar */}
      {activeFile && (
        <div className="flex items-center gap-4 px-3 h-6 border-t shrink-0 text-[10px]" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)', color: 'var(--text-secondary)' }}>
          <span>{activeFile.name.split('.').pop()?.toUpperCase() || 'TXT'}</span>
          <span>UTF-8</span>
          <span>Ln {activeFile.cursorLine}, Col {activeFile.cursorCol}</span>
          <span>{activeFile.content.length} chars</span>
          <span>{activeFile.content.split(/\s+/).filter(Boolean).length} words</span>
          <div className="flex-1" />
          {activeFile.isModified && <span className="text-[var(--accent-warning)]">Modified</span>}
        </div>
      )}

      {/* Open file dialog */}
      {showOpen && (
        <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="w-[480px] max-h-[400px] rounded-lg flex flex-col overflow-hidden" style={{ background: 'var(--bg-window)', boxShadow: 'var(--shadow-lg)' }}>
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Open File</h3>
              <button onClick={() => setShowOpen(false)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar p-2">
              {allFiles.map(f => (
                <button
                  key={f.id}
                  onClick={() => openFileById(f.id)}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                >
                  <FileText size={14} className="text-[var(--text-secondary)]" />
                  <span className="flex-1 text-left">{f.name}</span>
                  <span className="text-[var(--text-disabled)]">{getFilePath(f)}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TextEditor;
