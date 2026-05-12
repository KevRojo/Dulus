import { useState, useEffect, useMemo } from 'react';
import {
  Lock, Unlock, Plus, X, Search, Eye, EyeOff, Copy, Trash2, Edit2,
  RefreshCw, ArrowLeft, Shield, KeyRound
} from 'lucide-react';

interface PasswordEntry {
  id: string;
  title: string;
  username: string;
  password: string;
  url: string;
  notes: string;
  createdAt: number;
}

const STORAGE_KEY = 'dulus_passwords';
const MASTER_PIN = '1234';

const b64e = (s: string) => { try { return btoa(s); } catch { return s; } };
const b64d = (s: string) => { try { return atob(s); } catch { return s; } };

const loadEntries = (): PasswordEntry[] => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved).map((e: PasswordEntry) => ({ ...e, password: b64d(e.password) }));
  } catch { /* ignore */ }
  return [];
};

const saveEntries = (entries: PasswordEntry[]) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.map(e => ({ ...e, password: b64e(e.password) })))); } catch { /* ignore */ }
};

const generatePassword = (len: number, useNums: boolean, useSyms: boolean) => {
  const lower = 'abcdefghijklmnopqrstuvwxyz';
  const upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const nums = '0123456789';
  const syms = '!@#$%^&*()_+-=[]{}|;:,.<>?';
  let chars = lower + upper;
  if (useNums) chars += nums;
  if (useSyms) chars += syms;
  let pass = '';
  for (let i = 0; i < len; i++) pass += chars[Math.floor(Math.random() * chars.length)];
  return pass;
};

export default function PasswordManager() {
  const [authenticated, setAuthenticated] = useState(false);
  const [pin, setPin] = useState('');
  const [pinError, setPinError] = useState(false);
  const [entries, setEntries] = useState<PasswordEntry[]>(loadEntries);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [url, setUrl] = useState('');
  const [notes, setNotes] = useState('');
  const [showGen, setShowGen] = useState(false);
  const [genLen, setGenLen] = useState(16);
  const [genNums, setGenNums] = useState(true);
  const [genSyms, setGenSyms] = useState(true);
  const [visibleIds, setVisibleIds] = useState<Set<string>>(new Set());

  useEffect(() => { if (authenticated) saveEntries(entries); }, [entries, authenticated]);

  const checkPin = () => {
    if (pin === MASTER_PIN) { setAuthenticated(true); setPinError(false); }
    else { setPinError(true); setPin(''); }
  };

  const filtered = useMemo(() => {
    if (!search) return entries;
    const q = search.toLowerCase();
    return entries.filter(e => e.title.toLowerCase().includes(q) || e.username.toLowerCase().includes(q) || e.url.toLowerCase().includes(q));
  }, [entries, search]);

  const resetForm = () => { setTitle(''); setUsername(''); setPassword(''); setUrl(''); setNotes(''); setEditingId(null); };

  const saveEntry = () => {
    if (!title.trim() || !password) return;
    if (editingId) {
      setEntries(prev => prev.map(e => e.id === editingId ? { ...e, title: title.trim(), username, password, url, notes } : e));
    } else {
      setEntries(prev => [...prev, { id: Date.now().toString(36) + Math.random().toString(36).slice(2), title: title.trim(), username, password, url, notes, createdAt: Date.now() }]);
    }
    setShowForm(false); resetForm();
  };

  const startEdit = (e: PasswordEntry) => {
    setEditingId(e.id); setTitle(e.title); setUsername(e.username); setPassword(e.password); setUrl(e.url); setNotes(e.notes); setShowForm(true);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const toggleVisibility = (id: string) => {
    setVisibleIds(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  };

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" style={{ background: 'var(--bg-window)' }}>
        <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-primary)' }}>
          <Lock size={28} color="#fff" />
        </div>
        <div className="text-center">
          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>Password Manager</h3>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>Enter PIN to unlock (demo: 1234)</p>
        </div>
        <div className="flex flex-col items-center gap-2">
          <input type="password" value={pin} onChange={e => { setPin(e.target.value); setPinError(false); }} onKeyDown={e => e.key === 'Enter' && checkPin()} maxLength={4} placeholder="****" className="w-32 px-3 py-2 rounded-md text-center text-sm tracking-widest outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: pinError ? '1px solid var(--accent-error)' : '1px solid var(--border-subtle)' }} />
          {pinError && <p className="text-xs" style={{ color: 'var(--accent-error)' }}>Incorrect PIN</p>}
          <button onClick={checkPin} className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium" style={{ background: 'var(--accent-primary)', color: '#fff' }}>
            <Unlock size={14} /> Unlock
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <Shield size={16} style={{ color: 'var(--accent-primary)' }} />
        <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>Passwords</span>
        <button onClick={() => setAuthenticated(false)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><Lock size={12} /></button>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs" style={{ background: 'var(--accent-primary)', color: '#fff' }}><Plus size={12} /> Add</button>
      </div>
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md" style={{ background: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
          <Search size={12} style={{ color: 'var(--text-disabled)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search passwords..." className="flex-1 bg-transparent text-sm outline-none" style={{ color: 'var(--text-primary)' }} />
        </div>
      </div>
      {showForm && (
        <div className="p-3 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{editingId ? 'Edit' : 'New'} Entry</span>
            <button onClick={() => { setShowForm(false); resetForm(); }} className="p-1 rounded"><X size={14} style={{ color: 'var(--text-secondary)' }} /></button>
          </div>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title / Service name" className="w-full px-2 py-1 rounded-md text-xs outline-none mb-1.5" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Username / Email" className="w-full px-2 py-1 rounded-md text-xs outline-none mb-1.5" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <div className="flex gap-1.5 mb-1.5">
            <input value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" className="flex-1 px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <button onClick={() => setShowGen(!showGen)} className="px-2 py-1 rounded-md" style={{ background: 'var(--bg-hover)', color: 'var(--accent-secondary)' }}><KeyRound size={12} /></button>
          </div>
          {showGen && (
            <div className="p-2 rounded-md mb-1.5" style={{ background: 'var(--bg-window)' }}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Length: {genLen}</span>
                <input type="range" min={6} max={32} value={genLen} onChange={e => setGenLen(Number(e.target.value))} className="flex-1" />
              </div>
              <div className="flex gap-2 mb-1">
                <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}><input type="checkbox" checked={genNums} onChange={e => setGenNums(e.target.checked)} /> Numbers</label>
                <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}><input type="checkbox" checked={genSyms} onChange={e => setGenSyms(e.target.checked)} /> Symbols</label>
              </div>
              <button onClick={() => setPassword(generatePassword(genLen, genNums, genSyms))} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ background: 'var(--accent-primary)', color: '#fff' }}><RefreshCw size={10} /> Generate</button>
            </div>
          )}
          <input value={url} onChange={e => setUrl(e.target.value)} placeholder="Website URL (optional)" className="w-full px-2 py-1 rounded-md text-xs outline-none mb-1.5" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes (optional)" className="w-full px-2 py-1 rounded-md text-xs outline-none mb-2" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <button onClick={saveEntry} className="w-full py-1.5 rounded-md text-xs font-medium" style={{ background: 'var(--accent-primary)', color: '#fff' }}>Save Entry</button>
        </div>
      )}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: 'var(--text-secondary)' }}>
            <Lock size={32} strokeWidth={1} />
            <p className="text-xs">{search ? 'No matches' : 'No passwords stored'}</p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {filtered.map(e => {
              const isVisible = visibleIds.has(e.id);
              return (
                <div key={e.id} className="p-2.5 rounded-md group" style={{ background: 'var(--bg-panel)' }}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{e.title}</span>
                      {e.url && <span className="text-xs truncate max-w-[120px]" style={{ color: 'var(--text-disabled)' }}>{e.url}</span>}
                    </div>
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => startEdit(e)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><Edit2 size={11} /></button>
                      <button onClick={() => copyToClipboard(e.password)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><Copy size={11} /></button>
                      <button onClick={() => setEntries(prev => prev.filter(x => x.id !== e.id))} className="p-1 rounded" style={{ color: 'var(--accent-error)' }}><Trash2 size={11} /></button>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{e.username}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 flex items-center gap-1 px-2 py-1 rounded text-xs font-mono" style={{ background: 'var(--bg-window)', color: 'var(--text-primary)' }}>
                      {isVisible ? e.password : '•'.repeat(Math.min(e.password.length, 20))}
                    </div>
                    <button onClick={() => toggleVisibility(e.id)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}>
                      {isVisible ? <EyeOff size={12} /> : <Eye size={12} />}
                    </button>
                    <button onClick={() => copyToClipboard(e.password)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><Copy size={12} /></button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
