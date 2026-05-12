// ============================================================
// Memory Manager — Dulus Native App
// Disk-direct viewer: lists ~/.dulus/memory/*.md and project memories,
// mirrors the `/memory` CLI slash command. No cache layer.
// ============================================================

import { useEffect, useMemo, useState } from 'react';
import {
  Brain, Search, RefreshCw, AlertCircle, FileText, Star, MessageSquarePlus, Check,
} from 'lucide-react';
import { listMemoryFiles, type MemoryFile } from '@/lib/dulus-api';
import { emitMemoryInject } from '@/hooks/useSkillBridge';

export default function MemoryManager() {
  const [files, setFiles] = useState<MemoryFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [injectedAt, setInjectedAt] = useState<number | null>(null);

  const fetchFiles = async () => {
    setLoading(true);
    setError(null);
    const result = await listMemoryFiles('all');
    if (result.success && result.data) {
      setFiles(result.data);
      if (result.data.length > 0 && !selected) {
        setSelected(result.data[0].file_path);
      }
    } else {
      setError(result.error || 'Failed to load memory files');
      setFiles([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) =>
      f.name.toLowerCase().includes(q)
      || f.description.toLowerCase().includes(q)
      || f.content.toLowerCase().includes(q),
    );
  }, [files, query]);

  const current = useMemo(
    () => filtered.find((f) => f.file_path === selected) ?? filtered[0] ?? null,
    [filtered, selected],
  );

  if (loading && files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-secondary)]">
        <Brain size={32} className="animate-pulse" />
        <p className="text-sm">Loading memory palace...</p>
      </div>
    );
  }

  if (error && files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--accent-error)]">
        <AlertCircle size={32} />
        <p className="text-sm">{error}</p>
        <button
          onClick={fetchFiles}
          className="px-3 py-1.5 rounded-lg text-xs"
          style={{ background: 'var(--bg-hover)', border: '1px solid var(--border-default)' }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-3">
          <Brain size={18} style={{ color: 'var(--accent-secondary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Memory Palace</h2>
          <span
            className="text-[10px] px-2 py-0.5 rounded-full"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}
          >
            {files.length} files
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search..."
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs outline-none"
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-primary)',
                width: 220,
              }}
            />
          </div>
          <button
            onClick={fetchFiles}
            title="Refresh"
            className="p-1.5 rounded-lg"
            style={{ color: 'var(--text-secondary)' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Body: list + preview */}
      <div className="flex flex-1 min-h-0">
        {/* File list */}
        <div
          className="w-72 flex-shrink-0 overflow-auto border-r"
          style={{ borderColor: 'var(--border-default)' }}
        >
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-[var(--text-secondary)] p-4">
              <FileText size={20} />
              <p className="text-xs text-center">
                {files.length === 0 ? 'No memories yet.' : 'No matches.'}
              </p>
            </div>
          ) : (
            filtered.map((f) => {
              const active = current?.file_path === f.file_path;
              return (
                <button
                  key={f.file_path}
                  onClick={() => setSelected(f.file_path)}
                  className="w-full text-left px-3 py-2 border-b transition-colors"
                  style={{
                    background: active ? 'var(--bg-hover)' : 'transparent',
                    borderColor: 'var(--border-default)',
                    borderLeft: `2px solid ${active ? 'var(--accent-primary)' : 'transparent'}`,
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    {f.gold && <Star size={11} style={{ color: 'var(--accent-warning, #f5a623)' }} fill="currentColor" />}
                    <span
                      className="text-xs font-medium truncate flex-1"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {f.name}
                    </span>
                    <span
                      className="text-[9px] px-1.5 py-0.5 rounded uppercase tracking-wide"
                      style={{
                        background: 'var(--bg-input)',
                        color: f.scope === 'project' ? 'var(--accent-secondary)' : 'var(--text-secondary)',
                      }}
                    >
                      {f.scope}
                    </span>
                  </div>
                  {f.description && (
                    <p
                      className="text-[10px] mt-1 line-clamp-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {f.description}
                    </p>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Preview pane */}
        <div className="flex-1 overflow-auto p-4">
          {current ? (
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 mb-2">
                <FileText size={14} style={{ color: 'var(--accent-primary)' }} />
                <h3 className="text-sm font-semibold flex-1" style={{ color: 'var(--text-primary)' }}>
                  {current.name}
                </h3>
                {current.gold && (
                  <Star size={12} style={{ color: 'var(--accent-warning, #f5a623)' }} fill="currentColor" />
                )}
                <button
                  onClick={() => {
                    emitMemoryInject(current.name, current.content);
                    setInjectedAt(Date.now());
                    setTimeout(() => setInjectedAt(null), 2000);
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
                  style={{
                    background: injectedAt ? 'var(--accent-success, #16a34a)' : 'var(--accent-primary)',
                    color: 'white',
                  }}
                  title="Inject this memory as context into Chat"
                >
                  {injectedAt ? <Check size={12} /> : <MessageSquarePlus size={12} />}
                  {injectedAt ? 'Sent to Chat' : 'Send to Chat'}
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-3 text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                {current.type && (
                  <span className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)' }}>
                    type: {current.type}
                  </span>
                )}
                {current.hall && (
                  <span className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)' }}>
                    hall: {current.hall}
                  </span>
                )}
                {current.created && (
                  <span className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)' }}>
                    {current.created}
                  </span>
                )}
                <span className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)' }}>
                  {current.scope}
                </span>
              </div>
              {current.description && (
                <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
                  {current.description}
                </p>
              )}
              <pre
                className="text-xs whitespace-pre-wrap leading-relaxed p-3 rounded-lg"
                style={{
                  background: 'var(--bg-input)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono, monospace)',
                  border: '1px solid var(--border-default)',
                }}
              >
                {current.content || '(empty)'}
              </pre>
              <p className="text-[10px] mt-2 truncate" style={{ color: 'var(--text-secondary)' }} title={current.file_path}>
                {current.file_path}
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-[var(--text-secondary)]">
              <FileText size={24} />
              <p className="text-xs">Select a memory to preview.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
