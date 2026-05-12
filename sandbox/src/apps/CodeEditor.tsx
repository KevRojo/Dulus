// ============================================================
// Code Editor — Multi-tab editor with syntax highlighting
// ============================================================

import { useState, useCallback, useMemo, useRef } from 'react';
import { useFileSystem } from '@/hooks/useFileSystem';
import {
  Code2, X, Plus, Search, Save, FolderOpen, FileText,
  ChevronRight, ChevronDown, Folder,
} from 'lucide-react';

interface EditorTab {
  id: string;
  name: string;
  content: string;
  language: string;
  isDirty: boolean;
  fileNodeId?: string;
}

const LANGUAGE_MAP: Record<string, string> = {
  js: 'javascript', ts: 'typescript', html: 'html', css: 'css',
  json: 'json', py: 'python', md: 'markdown', go: 'go',
  rs: 'rust', java: 'java', c: 'c', cpp: 'cpp', h: 'c',
  sh: 'shell', yaml: 'yaml', yml: 'yaml', xml: 'xml',
};

function getLangFromFilename(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || '';
  return LANGUAGE_MAP[ext] || 'plaintext';
}

// ---- Simple regex-based syntax highlighter ----
function highlightCode(code: string, lang: string): string {
  const escapeHtml = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const keywords: Record<string, string[]> = {
    javascript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'import', 'export', 'from', 'default', 'async', 'await', 'new', 'this', 'try', 'catch', 'throw', 'switch', 'case', 'break', 'continue', 'typeof', 'instanceof'],
    typescript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'interface', 'type', 'import', 'export', 'from', 'default', 'async', 'await', 'new', 'this', 'try', 'catch', 'throw', 'switch', 'case', 'break', 'continue', 'typeof', 'instanceof', 'extends', 'implements', 'enum', 'namespace'],
    python: ['def', 'return', 'if', 'elif', 'else', 'for', 'while', 'class', 'import', 'from', 'as', 'try', 'except', 'raise', 'with', 'lambda', 'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False', 'pass', 'break', 'continue'],
    go: ['func', 'return', 'if', 'else', 'for', 'range', 'import', 'package', 'type', 'struct', 'interface', 'map', 'chan', 'go', 'defer', 'select', 'case', 'default', 'var', 'const'],
    rust: ['fn', 'let', 'mut', 'return', 'if', 'else', 'for', 'while', 'loop', 'match', 'impl', 'struct', 'enum', 'trait', 'use', 'mod', 'pub', 'crate', 'async', 'await', 'const', 'static', 'ref', 'move'],
    java: ['public', 'private', 'protected', 'static', 'final', 'class', 'interface', 'extends', 'implements', 'return', 'if', 'else', 'for', 'while', 'new', 'this', 'void', 'int', 'String', 'import', 'package'],
    c: ['int', 'char', 'float', 'double', 'void', 'return', 'if', 'else', 'for', 'while', 'struct', 'typedef', 'include', 'define', 'const', 'static', 'extern', 'sizeof', 'break', 'continue', 'switch', 'case'],
  };

  const langKeywords = keywords[lang] || keywords.javascript || [];
  const kwPattern = new RegExp(`\\b(${langKeywords.join('|')})\\b`, 'g');
  const strPattern = /(".*?"|'.*?'|`[\s\S]*?`)/g;
  const numPattern = /\b(\d+(?:\.\d+)?)\b/g;
  const commentPattern = lang === 'python'
    ? /(#.*$)/gm
    : /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm;

  let highlighted = escapeHtml(code);

  // Comments first
  highlighted = highlighted.replace(commentPattern, '<span style="color:#6A9955">$1</span>');

  // Strings (avoid matching inside comments)
  highlighted = highlighted.replace(strPattern, '<span style="color:#CE9178">$1</span>');

  // Numbers
  highlighted = highlighted.replace(numPattern, '<span style="color:#B5CEA8">$1</span>');

  // Keywords
  highlighted = highlighted.replace(kwPattern, '<span style="color:#C586C0">$1</span>');

  if (lang === 'html' || lang === 'markdown') {
    highlighted = highlighted.replace(/(&lt;\/?)([\w-]+)/g, '<span style="color:#569CD6">$1$2</span>');
    highlighted = highlighted.replace(/(\s)([\w-]+)(=)/g, '$1<span style="color:#9CDCFE">$2</span>$3');
  }

  if (lang === 'css') {
    highlighted = highlighted.replace(/([\w-]+)(\s*:)/g, '<span style="color:#9CDCFE">$1</span>$2');
    highlighted = highlighted.replace(/(:\s*)([^;{}]+)/g, '$1<span style="color:#CE9178">$2</span>');
  }

  return highlighted;
}

// ---- File tree component ----
function FileTree({
  nodeId,
  fs,
  onOpen,
  depth = 0,
}: {
  nodeId: string;
  fs: ReturnType<typeof useFileSystem>;
  onOpen: (id: string, name: string) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const children = fs.getChildren(nodeId).filter((c) => !c.name.startsWith('.'));

  const toggleFolder = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div>
      {children.map((child) => (
        <div key={child.id}>
          <div
            className="flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-[var(--bg-hover)] transition-colors"
            style={{ paddingLeft: 8 + depth * 12 }}
            onClick={() => {
              if (child.type === 'folder') toggleFolder(child.id);
              else onOpen(child.id, child.name);
            }}
          >
            {child.type === 'folder' ? (
              <>
                {expanded.has(child.id) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <Folder size={14} className="text-[var(--accent-warning)]" />
              </>
            ) : (
              <>
                <span className="w-3" />
                <FileText size={14} className="text-[var(--text-secondary)]" />
              </>
            )}
            <span className="text-xs truncate" style={{ color: 'var(--text-primary)' }}>
              {child.name}
            </span>
          </div>
          {child.type === 'folder' && expanded.has(child.id) && (
            <FileTree nodeId={child.id} fs={fs} onOpen={onOpen} depth={depth + 1} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function CodeEditor() {
  const fs = useFileSystem();
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showFindBar, setShowFindBar] = useState(false);
  const [findQuery, setFindQuery] = useState('');
  const [lineCount, setLineCount] = useState(1);
  const [cursorPos, setCursorPos] = useState({ line: 1, col: 1 });
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineNumbersRef = useRef<HTMLDivElement>(null);

  const activeTab = tabs.find((t) => t.id === activeTabId);

  const userNodeId = useMemo(() => {
    const rootChildren = Object.values(fs.fs.nodes).filter((n) => n.parentId === null);
    const homeNode = rootChildren.find((n) => n.name === 'home');
    const userNode = homeNode
      ? Object.values(fs.fs.nodes).find((n) => n.parentId === homeNode.id && n.name === 'user')
      : undefined;
    return userNode?.id || '';
  }, [fs.fs.nodes]);

  const openFile = useCallback(
    (nodeId: string, name: string) => {
      const content = fs.readFile(nodeId) || '';
      const existing = tabs.find((t) => t.fileNodeId === nodeId);
      if (existing) {
        setActiveTabId(existing.id);
        return;
      }
      const newTab: EditorTab = {
        id: Date.now().toString() + Math.random().toString(36).slice(2),
        name,
        content,
        language: getLangFromFilename(name),
        isDirty: false,
        fileNodeId: nodeId,
      };
      setTabs((prev) => [...prev, newTab]);
      setActiveTabId(newTab.id);
    },
    [fs, tabs]
  );

  const newFile = useCallback(() => {
    const newTab: EditorTab = {
      id: Date.now().toString() + Math.random().toString(36).slice(2),
      name: 'untitled.txt',
      content: '',
      language: 'plaintext',
      isDirty: false,
    };
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);
  }, []);

  const closeTab = useCallback(
    (tabId: string) => {
      const idx = tabs.findIndex((t) => t.id === tabId);
      setTabs((prev) => prev.filter((t) => t.id !== tabId));
      if (activeTabId === tabId) {
        const remaining = tabs.filter((t) => t.id !== tabId);
        if (remaining.length > 0) {
          const nextIdx = Math.min(idx, remaining.length - 1);
          setActiveTabId(remaining[nextIdx].id);
        } else {
          setActiveTabId(null);
        }
      }
    },
    [tabs, activeTabId]
  );

  const saveFile = useCallback(() => {
    if (!activeTab) return;
    if (activeTab.fileNodeId) {
      fs.writeFile(activeTab.fileNodeId, activeTab.content);
      setTabs((prev) =>
        prev.map((t) => (t.id === activeTab.id ? { ...t, isDirty: false } : t))
      );
    } else {
      // Save to documents
      const docs = Object.values(fs.fs.nodes).find(
        (n) => n.name === 'Documents' && n.parentId === userNodeId
      );
      if (docs) {
        const newId = fs.createFile(docs.id, activeTab.name, activeTab.content);
        setTabs((prev) =>
          prev.map((t) => (t.id === activeTab.id ? { ...t, fileNodeId: newId, isDirty: false } : t))
        );
      }
    }
  }, [activeTab, fs, userNodeId]);

  const updateContent = useCallback(
    (tabId: string, content: string) => {
      setTabs((prev) =>
        prev.map((t) => (t.id === tabId ? { ...t, content, isDirty: true } : t))
      );
      const lines = content.split('\n').length;
      setLineCount(lines);
    },
    []
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveFile();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        setShowFindBar((v) => !v);
      }
      if (e.key === 'Tab') {
        e.preventDefault();
        const ta = textareaRef.current;
        if (!ta) return;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const val = ta.value;
        ta.value = val.substring(0, start) + '  ' + val.substring(end);
        ta.selectionStart = ta.selectionEnd = start + 2;
        if (activeTab) updateContent(activeTab.id, ta.value);
      }
    },
    [saveFile, activeTab, updateContent]
  );

  const handleCursor = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    const textBefore = ta.value.substring(0, ta.selectionStart);
    const lines = textBefore.split('\n');
    setCursorPos({ line: lines.length, col: lines[lines.length - 1].length + 1 });
  }, []);

  const handleScroll = useCallback(() => {
    if (textareaRef.current && lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }, []);

  // Line numbers
  const lineNumbers = useMemo(() => {
    return Array.from({ length: Math.max(lineCount, 1) }, (_, i) => i + 1);
  }, [lineCount]);

  // Find highlights
  const findMatches = useMemo(() => {
    if (!showFindBar || !findQuery || !activeTab) return [] as number[];
    const matches: number[] = [];
    let idx = activeTab.content.indexOf(findQuery);
    while (idx !== -1) {
      matches.push(idx);
      idx = activeTab.content.indexOf(findQuery, idx + 1);
    }
    return matches;
  }, [showFindBar, findQuery, activeTab]);

  const highlightedHtml = useMemo(() => {
    if (!activeTab) return '';
    return highlightCode(activeTab.content, activeTab.language);
  }, [activeTab]);

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-window)' }}>
      {/* Menu Bar */}
      <div className="flex items-center gap-1 px-2 shrink-0" style={{ height: 32, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
        <button onClick={newFile} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--bg-hover)] transition-colors" title="New File">
          <Plus size={14} /><span className="text-xs">New</span>
        </button>
        <button onClick={() => setShowSidebar((v) => !v)} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--bg-hover)] transition-colors" title="Toggle Sidebar">
          <FolderOpen size={14} /><span className="text-xs">Explorer</span>
        </button>
        <button onClick={() => setShowFindBar((v) => !v)} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--bg-hover)] transition-colors" title="Find (Ctrl+F)">
          <Search size={14} /><span className="text-xs">Find</span>
        </button>
        <button onClick={saveFile} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--bg-hover)] transition-colors" title="Save (Ctrl+S)">
          <Save size={14} /><span className="text-xs">Save</span>
        </button>
        <div className="ml-auto flex items-center gap-2">
          {activeTab && (
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--bg-hover)' }}>
              {activeTab.language}
            </span>
          )}
        </div>
      </div>

      {/* Find Bar */}
      {showFindBar && (
        <div className="flex items-center gap-2 px-3 py-1 shrink-0" style={{ background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
          <Search size={14} className="text-[var(--text-secondary)]" />
          <input
            value={findQuery}
            onChange={(e) => setFindQuery(e.target.value)}
            placeholder="Find in file..."
            className="flex-1 text-xs px-2 py-1 rounded outline-none"
            style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-default)' }}
            autoFocus
          />
          <button onClick={() => setShowFindBar(false)} className="text-xs px-2 py-0.5 rounded hover:bg-[var(--bg-hover)]">Esc</button>
          {findQuery && (
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {findMatches.length} matches
            </span>
          )}
        </div>
      )}

      {/* Tab Bar */}
      {tabs.length > 0 && (
        <div className="flex items-center gap-0 overflow-x-auto shrink-0" style={{ height: 32, background: 'var(--bg-titlebar)', borderBottom: '1px solid var(--border-subtle)' }}>
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className="flex items-center gap-1 px-3 py-1 cursor-pointer text-xs border-b-2 transition-colors"
              style={{
                borderColor: tab.id === activeTabId ? 'var(--accent-primary)' : 'transparent',
                background: tab.id === activeTabId ? 'var(--bg-window)' : 'transparent',
                color: 'var(--text-primary)',
              }}
              onClick={() => setActiveTabId(tab.id)}
            >
              <Code2 size={12} />
              {tab.isDirty && <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)]" />}
              <span className="truncate max-w-[120px]">{tab.name}</span>
              <button
                onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}
                className="ml-1 p-0.5 rounded hover:bg-[var(--bg-hover)]"
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        {showSidebar && (
          <div className="shrink-0 overflow-y-auto custom-scrollbar" style={{ width: 180, background: 'var(--bg-window)', borderRight: '1px solid var(--border-subtle)' }}>
            <div className="px-2 py-1 text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>EXPLORER</div>
            {userNodeId && <FileTree nodeId={userNodeId} fs={fs} onOpen={openFile} />}
          </div>
        )}

        {/* Editor */}
        <div className="flex-1 flex flex-col overflow-hidden relative" style={{ background: 'var(--bg-window)' }}>
          {activeTab ? (
            <>
              <div className="flex-1 flex overflow-hidden relative">
                {/* Line numbers */}
                <div
                  ref={lineNumbersRef}
                  className="shrink-0 overflow-hidden text-right py-2 select-none"
                  style={{ width: 48, background: 'var(--bg-window)', color: 'var(--text-disabled)', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", lineHeight: '20px' }}
                >
                  {lineNumbers.map((n) => (
                    <div key={n} className="pr-3" style={{ height: 20 }}>{n}</div>
                  ))}
                </div>

                {/* Code area with highlighting */}
                <div className="flex-1 relative overflow-auto">
                  {/* Syntax highlight layer */}
                  <div
                    className="absolute inset-0 py-2 px-1 pointer-events-none whitespace-pre"
                    style={{ fontSize: 13, fontFamily: "'JetBrains Mono', monospace", lineHeight: '20px', color: 'var(--text-primary)' }}
                    dangerouslySetInnerHTML={{ __html: highlightedHtml + '\n' }}
                  />
                  {/* Input textarea */}
                  <textarea
                    ref={textareaRef}
                    value={activeTab.content}
                    onChange={(e) => updateContent(activeTab.id, e.target.value)}
                    onKeyDown={handleKeyDown}
                    onClick={handleCursor}
                    onKeyUp={handleCursor}
                    onScroll={handleScroll}
                    spellCheck={false}
                    className="absolute inset-0 w-full h-full py-2 px-1 resize-none outline-none bg-transparent whitespace-pre"
                    style={{
                      fontSize: 13,
                      fontFamily: "'JetBrains Mono', monospace",
                      lineHeight: '20px',
                      color: 'transparent',
                      caretColor: 'var(--text-primary)',
                    }}
                  />
                </div>
              </div>

              {/* Status Bar */}
              <div className="flex items-center justify-between px-3 py-0.5 shrink-0" style={{ background: 'var(--bg-titlebar)', borderTop: '1px solid var(--border-subtle)' }}>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Ln {cursorPos.line}, Col {cursorPos.col}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {activeTab.language} | UTF-8 | {activeTab.content.length} chars
                </span>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-4">
              <Code2 size={48} className="text-[var(--text-disabled)]" />
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                Open a file from the explorer or create a new file
              </p>
              <div className="flex gap-2">
                <button onClick={newFile} className="flex items-center gap-1 px-3 py-1.5 rounded text-xs" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                  <Plus size={14} /> New File
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
