// ============================================================
// Memory Manager — Dulus Native App (Hook-based)
// ============================================================

import { useState, useMemo } from 'react';
import {
  Brain, Search, RefreshCw, AlertCircle, Clock, Tag,
  Database, Layers, ChevronRight, ChevronDown, FileText,
  Sparkles, FolderOpen
} from 'lucide-react';
import { useDulusMemory } from '@/hooks/useDulusMemory';

export default function MemoryManager() {
  const { data, isLoading: loading, error, refresh: fetchMemory } = useDulusMemory();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedWing, setSelectedWing] = useState<string>('all');
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'entries' | 'wings' | 'compact'>('entries');

  const filteredEntries = useMemo(() => {
    return (data?.entries || []).filter((entry) => {
      const matchesWing = selectedWing === 'all' || entry.wing === selectedWing;
      const q = searchQuery.toLowerCase();
      const matchesSearch = !q ||
        (entry.content || '').toLowerCase().includes(q) ||
        (entry.wing || '').toLowerCase().includes(q) ||
        (entry.type || '').toLowerCase().includes(q);
      return matchesWing && matchesSearch;
    });
  }, [data?.entries, selectedWing, searchQuery]);

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-secondary)]">
        <Brain size={32} className="animate-pulse" />
        <p className="text-sm">Loading Dulus memory palace...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--accent-error)]">
        <AlertCircle size={32} />
        <p className="text-sm">{error}</p>
        <button onClick={fetchMemory} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border-default)' }}>
          Retry
        </button>
      </div>
    );
  }

  const stats = data?.stats || { total: data?.entries?.length || 0, wings: data?.wings?.length || 0 };

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-3">
          <Brain size={18} style={{ color: 'var(--accent-secondary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Memory Palace</h2>
          <div className="flex gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
              <Database size={10} /> {stats.total} entries
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
              <Layers size={10} /> {stats.wings} wings
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search memories..."
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', width: 200 }}
            />
          </div>
          <button onClick={fetchMemory} className="p-1.5 rounded-lg" style={{ color: 'var(--text-secondary)' }}>
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b" style={{ borderColor: 'var(--border-default)' }}>
        {(['entries', 'wings', 'compact'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-4 py-2 text-xs font-medium capitalize transition-colors border-b-2"
            style={{
              color: activeTab === tab ? 'var(--accent-primary)' : 'var(--text-secondary)',
              borderColor: activeTab === tab ? 'var(--accent-primary)' : 'transparent',
              background: activeTab === tab ? 'var(--bg-hover)' : 'transparent',
            }}
          >
            {tab === 'compact' ? 'Compact View' : tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'entries' && (
          <div className="flex gap-3 h-full">
            {/* Wing filter sidebar */}
            <div className="w-44 flex-shrink-0 space-y-1">
              <button
                onClick={() => setSelectedWing('all')}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors ${selectedWing === 'all' ? 'font-medium' : ''}`}
                style={{ background: selectedWing === 'all' ? 'var(--accent-primary)' : 'var(--bg-hover)', color: selectedWing === 'all' ? 'white' : 'var(--text-primary)' }}
              >
                <FolderOpen size={14} /> All Wings
              </button>
              {(data?.wings || []).map((wing) => (
                <button
                  key={wing.name}
                  onClick={() => setSelectedWing(wing.name)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors ${selectedWing === wing.name ? 'font-medium' : ''}`}
                  style={{ background: selectedWing === wing.name ? 'var(--accent-primary)' : 'var(--bg-hover)', color: selectedWing === wing.name ? 'white' : 'var(--text-primary)' }}
                >
                  <span className="flex items-center gap-2">
                    <Layers size={14} /> {wing.name}
                  </span>
                  <span className="text-[10px] opacity-70">{wing.count}</span>
                </button>
              ))}
            </div>

            {/* Entries grid */}
            <div className="flex-1 overflow-auto">
              {filteredEntries.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-2">
                  <Search size={24} />
                  <p className="text-xs">No memories found</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
                  {filteredEntries.map((entry) => (
                    <div
                      key={entry.id}
                      className="rounded-lg border transition-all cursor-pointer"
                      style={{
                        background: 'var(--bg-hover)',
                        borderColor: expandedEntry === entry.id ? 'var(--accent-primary)' : 'var(--border-default)',
                      }}
                      onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id ?? null)}
                    >
                      <div className="px-3 py-2.5 flex items-start gap-2">
                        <Sparkles size={14} className="mt-0.5 flex-shrink-0" style={{ color: 'var(--accent-secondary)' }} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium line-clamp-2" style={{ color: 'var(--text-primary)' }}>
                            {entry.content}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5">
                            {entry.wing && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-input)', color: 'var(--accent-primary)' }}>
                                {entry.wing}
                              </span>
                            )}
                            {entry.type && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)' }}>
                                {entry.type}
                              </span>
                            )}
                            {entry.confidence !== undefined && (
                              <span className="text-[10px] text-[var(--text-secondary)]">
                                {Math.round(entry.confidence * 100)}% confidence
                              </span>
                            )}
                          </div>
                        </div>
                        {expandedEntry === entry.id ? <ChevronDown size={14} style={{ color: 'var(--text-secondary)' }} /> : <ChevronRight size={14} style={{ color: 'var(--text-secondary)' }} />}
                      </div>

                      {expandedEntry === entry.id && (
                        <div className="px-3 pb-3 pt-1 border-t text-[11px] space-y-1.5" style={{ borderColor: 'var(--border-default)', color: 'var(--text-secondary)' }}>
                          {entry.source && <p><span className="opacity-60">Source:</span> {entry.source}</p>}
                          {entry.created_at && <p><span className="opacity-60">Created:</span> {new Date(entry.created_at).toLocaleString()}</p>}
                          {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                            <div className="pt-1">
                              <p className="opacity-60 mb-1">Metadata:</p>
                              <pre className="p-2 rounded text-[10px] overflow-auto" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)' }}>
                                {JSON.stringify(entry.metadata, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'wings' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(data?.wings || []).map((wing) => (
              <div
                key={wing.name}
                className="p-4 rounded-xl border transition-all hover:shadow-md cursor-pointer"
                style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}
                onClick={() => { setSelectedWing(wing.name); setActiveTab('entries'); }}
              >
                <div className="flex items-center justify-between mb-2">
                  <FolderOpen size={18} style={{ color: 'var(--accent-primary)' }} />
                  <span className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{wing.count}</span>
                </div>
                <h3 className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>{wing.name}</h3>
                {wing.last_updated && (
                  <p className="text-[10px] text-[var(--text-secondary)] flex items-center gap-1">
                    <Clock size={10} /> Last updated: {new Date(wing.last_updated).toLocaleDateString()}
                  </p>
                )}
              </div>
            ))}
            {(data?.wings || []).length === 0 && (
              <div className="col-span-full flex flex-col items-center justify-center py-12 text-[var(--text-secondary)] gap-2">
                <Layers size={24} />
                <p className="text-xs">No wings found</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'compact' && (
          <div className="max-w-3xl mx-auto">
            <div className="p-4 rounded-xl border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
              <div className="flex items-center gap-2 mb-3">
                <FileText size={14} style={{ color: 'var(--accent-primary)' }} />
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Compact Context</span>
              </div>
              <pre className="text-xs whitespace-pre-wrap leading-relaxed overflow-auto max-h-[60vh] p-3 rounded-lg" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono, monospace)' }}>
                {data?.compact_text || 'No compact context available.'}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
