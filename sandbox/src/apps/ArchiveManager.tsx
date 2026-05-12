// ============================================================
// Archive Manager — Create and extract ZIP/TAR archives
// ============================================================

import { useState, useEffect } from 'react';
import {
  Package, Plus, FileText, ChevronRight, ChevronDown,
  Trash2, Lock, Check, Folder,
  Download,
} from 'lucide-react';
import { useFileSystem } from '@/hooks/useFileSystem';

interface ArchiveEntry {
  id: string;
  name: string;
  type: 'file' | 'folder';
  size: string;
  children?: ArchiveEntry[];
}

interface ArchiveFile {
  id: string;
  name: string;
  format: 'zip' | 'tar';
  createdAt: number;
  entries: ArchiveEntry[];
  isPasswordProtected?: boolean;
}

const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const loadArchives = (): ArchiveFile[] => {
  try {
    const saved = localStorage.getItem('dulus_archives');
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  // Sample archive
  return [{
    id: generateId(),
    name: 'documents.zip',
    format: 'zip',
    createdAt: Date.now() - 86400000,
    entries: [
      { id: generateId(), name: 'README.md', type: 'file', size: '2.4 KB' },
      { id: generateId(), name: 'src', type: 'folder', size: '-', children: [
        { id: generateId(), name: 'main.js', type: 'file', size: '5.1 KB' },
        { id: generateId(), name: 'styles.css', type: 'file', size: '3.2 KB' },
      ]},
      { id: generateId(), name: 'assets', type: 'folder', size: '-', children: [
        { id: generateId(), name: 'logo.png', type: 'file', size: '45 KB' },
      ]},
    ],
  }];
};

const TreeEntry: React.FC<{
  entry: ArchiveEntry;
  level: number;
  selectedIds: string[];
  onToggle: (id: string) => void;
}> = ({ entry, level, selectedIds, onToggle }) => {
  const [expanded, setExpanded] = useState(true);
  const isSelected = selectedIds.includes(entry.id);

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1 px-2 rounded cursor-pointer transition-colors hover:bg-[var(--bg-hover)]"
        style={{ paddingLeft: 8 + level * 16 }}
        onClick={() => onToggle(entry.id)}
      >
        {entry.type === 'folder' && (
          <button onClick={e => { e.stopPropagation(); setExpanded(!expanded); }} className="text-[var(--text-secondary)]">
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
        )}
        {entry.type === 'folder' ? <Folder size={14} className="text-[var(--accent-warning)]" /> : <FileText size={14} className="text-[var(--accent-info)]" />}
        <span className="flex-1 text-xs text-[var(--text-primary)] truncate">{entry.name}</span>
        <span className="text-[10px] text-[var(--text-disabled)]">{entry.size}</span>
        {isSelected && <Check size={12} className="text-[var(--accent-primary)]" />}
      </div>
      {entry.type === 'folder' && expanded && entry.children?.map(child => (
        <TreeEntry key={child.id} entry={child} level={level + 1} selectedIds={selectedIds} onToggle={onToggle} />
      ))}
    </div>
  );
};

const ArchiveManager: React.FC = () => {
  useFileSystem(); // hook available for future file system integration
  const [archives, setArchives] = useState<ArchiveFile[]>(loadArchives);
  const [selectedArchive, setSelectedArchive] = useState<string | null>(null);
  const [selectedEntries, setSelectedEntries] = useState<string[]>([]);
  const [view, setView] = useState<'recent' | 'create' | 'view'>('recent');
  const [showCreate, setShowCreate] = useState(false);

  // Create form state
  const [createName, setCreateName] = useState('');
  const [createFormat, setCreateFormat] = useState<'zip' | 'tar'>('zip');
  const [createPassword, setCreatePassword] = useState('');

  const activeArchive = archives.find(a => a.id === selectedArchive) || null;

  useEffect(() => {
    localStorage.setItem('dulus_archives', JSON.stringify(archives));
  }, [archives]);

  const toggleEntry = (id: string) => {
    setSelectedEntries(prev =>
      prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id]
    );
  };

  const createArchive = () => {
    if (!createName.trim()) return;
    const name = createName.endsWith(`.${createFormat}`) ? createName : `${createName}.${createFormat}`;
    const archive: ArchiveFile = {
      id: generateId(),
      name,
      format: createFormat,
      createdAt: Date.now(),
      isPasswordProtected: !!createPassword,
      entries: [
        { id: generateId(), name: 'README.txt', type: 'file', size: '1.2 KB' },
        { id: generateId(), name: 'data', type: 'folder', size: '-', children: [
          { id: generateId(), name: 'file1.txt', type: 'file', size: '456 B' },
          { id: generateId(), name: 'file2.txt', type: 'file', size: '789 B' },
        ]},
      ],
    };
    setArchives(prev => [archive, ...prev]);
    setShowCreate(false);
    setCreateName('');
    setCreatePassword('');
    setSelectedArchive(archive.id);
    setView('view');
  };

  const deleteArchive = (id: string) => {
    setArchives(prev => prev.filter(a => a.id !== id));
    if (selectedArchive === id) { setSelectedArchive(null); setView('recent'); }
  };

  const extractArchive = (archive: ArchiveFile) => {
    // Simulated extraction
    alert(`Extracted "${archive.name}" (${archive.entries.length} entries)`);
  };

  const allEntries = (entries: ArchiveEntry[]): ArchiveEntry[] => {
    let result: ArchiveEntry[] = [];
    for (const e of entries) {
      result.push(e);
      if (e.children) result = result.concat(allEntries(e.children));
    }
    return result;
  };

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Sidebar - Archive list */}
      <div className="w-56 shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <div className="p-2">
          <button
            onClick={() => { setShowCreate(true); setView('create'); }}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-xs font-medium text-white"
            style={{ background: 'var(--accent-primary)' }}
          >
            <Plus size={14} /> New Archive
          </button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="text-[10px] text-[var(--text-disabled)] uppercase tracking-wider px-3 py-1">Recent Archives</div>
          {archives.map(archive => (
            <div key={archive.id} className="group flex items-center px-2">
              <button
                onClick={() => { setSelectedArchive(archive.id); setView('view'); setSelectedEntries([]); }}
                className="flex items-center gap-2 flex-1 px-2 py-2 rounded-lg text-xs transition-colors"
                style={{
                  background: selectedArchive === archive.id ? 'var(--bg-selected)' : 'transparent',
                  color: selectedArchive === archive.id ? 'var(--accent-primary)' : 'var(--text-primary)',
                }}
              >
                <Package size={14} />
                <span className="flex-1 text-left truncate">{archive.name}</span>
                {archive.isPasswordProtected && <Lock size={10} className="text-[var(--accent-warning)]" />}
              </button>
              <button
                onClick={() => deleteArchive(archive.id)}
                className="hidden group-hover:block p-1 text-[var(--text-secondary)] hover:text-[var(--accent-error)]"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {view === 'create' || showCreate ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
            <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-6">Create Archive</h2>
            <div className="max-w-md space-y-4">
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">Archive Name</label>
                <input
                  value={createName}
                  onChange={e => setCreateName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') createArchive(); }}
                  placeholder="my-archive"
                  className="w-full h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">Format</label>
                <div className="flex gap-2">
                  {(['zip', 'tar'] as const).map(f => (
                    <button
                      key={f}
                      onClick={() => setCreateFormat(f)}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs capitalize transition-colors"
                      style={{
                        background: createFormat === f ? 'var(--bg-selected)' : 'var(--bg-input)',
                        color: createFormat === f ? 'var(--accent-primary)' : 'var(--text-primary)',
                        border: `1px solid ${createFormat === f ? 'var(--accent-primary)' : 'var(--border-default)'}`,
                      }}
                    >
                      <Package size={14} /> {f}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1">Password (optional)</label>
                <input
                  type="password"
                  value={createPassword}
                  onChange={e => setCreatePassword(e.target.value)}
                  placeholder="Leave blank for no password"
                  className="w-full h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => { setShowCreate(false); setView('recent'); }} className="px-4 py-2 rounded-lg text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">
                  Cancel
                </button>
                <button
                  onClick={createArchive}
                  disabled={!createName.trim()}
                  className="px-6 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40"
                  style={{ background: 'var(--accent-primary)' }}
                >
                  Create Archive
                </button>
              </div>
            </div>
          </div>
        ) : view === 'view' && activeArchive ? (
          <>
            {/* Archive view toolbar */}
            <div className="flex items-center justify-between px-4 py-2 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
              <div className="flex items-center gap-2">
                <Package size={16} className="text-[var(--accent-primary)]" />
                <span className="text-sm font-semibold text-[var(--text-primary)]">{activeArchive.name}</span>
                {activeArchive.isPasswordProtected && (
                  <span className="flex items-center gap-1 text-[10px] text-[var(--accent-warning)] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,152,0,0.15)' }}>
                    <Lock size={10} /> Protected
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--text-secondary)]">{allEntries(activeArchive.entries).length} items</span>
                <button
                  onClick={() => extractArchive(activeArchive)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white"
                  style={{ background: 'var(--accent-success)' }}
                >
                  <Download size={12} /> Extract
                </button>
                <button onClick={() => deleteArchive(activeArchive.id)} className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--accent-error)]">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>

            {/* Archive contents tree */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
              <div className="flex items-center gap-4 px-2 py-1 border-b text-[10px] text-[var(--text-secondary)] uppercase tracking-wider" style={{ borderColor: 'var(--border-subtle)' }}>
                <span className="flex-1">Name</span>
                <span className="w-16 text-right">Size</span>
                <span className="w-8">Select</span>
              </div>
              {activeArchive.entries.map(entry => (
                <TreeEntry
                  key={entry.id}
                  entry={entry}
                  level={0}
                  selectedIds={selectedEntries}
                  onToggle={toggleEntry}
                />
              ))}
            </div>

            {/* Selected entries info */}
            {selectedEntries.length > 0 && (
              <div className="px-4 py-2 border-t shrink-0 text-xs text-[var(--text-secondary)]" style={{ borderColor: 'var(--border-subtle)' }}>
                {selectedEntries.length} item(s) selected
              </div>
            )}
          </>
        ) : (
          /* Recent view */
          <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
            <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-4">Archive Manager</h2>
            {archives.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 gap-3">
                <Package size={48} className="text-[var(--text-disabled)] opacity-30" />
                <div className="text-sm text-[var(--text-secondary)]">No archives yet</div>
                <button
                  onClick={() => { setShowCreate(true); setView('create'); }}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                  style={{ background: 'var(--accent-primary)' }}
                >
                  Create Your First Archive
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {archives.map(archive => (
                  <button
                    key={archive.id}
                    onClick={() => { setSelectedArchive(archive.id); setView('view'); setSelectedEntries([]); }}
                    className="flex items-center gap-3 p-4 rounded-lg text-left transition-all hover:scale-[1.01]"
                    style={{ background: 'var(--bg-titlebar)', border: '1px solid var(--border-subtle)' }}
                  >
                    <Package size={24} className="text-[var(--accent-primary)]" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-[var(--text-primary)] truncate">{archive.name}</div>
                      <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                        {archive.format.toUpperCase()} • {allEntries(archive.entries).length} items • {archive.isPasswordProtected ? 'Password Protected' : 'No Password'}
                      </div>
                      <div className="text-[10px] text-[var(--text-disabled)]">
                        {new Date(archive.createdAt).toLocaleDateString()}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ArchiveManager;
