import { useState, useEffect, useMemo } from 'react';
import {
  Bell, Plus, X, Check, Calendar, Clock, Trash2, Edit2,
  ChevronDown, AlertCircle, Flag
} from 'lucide-react';

interface Reminder {
  id: string;
  title: string;
  date: string;
  time: string;
  priority: 'low' | 'medium' | 'high';
  completed: boolean;
  createdAt: number;
}

type FilterType = 'all' | 'today' | 'upcoming' | 'overdue' | 'completed';

const STORAGE_KEY = 'dulus_reminders';

const loadReminders = (): Reminder[] => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return [];
};

const saveReminders = (reminders: Reminder[]) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(reminders)); } catch { /* ignore */ }
};

const PRIORITY_COLORS = {
  low: { bg: 'rgba(76,175,80,0.15)', text: '#4CAF50', border: 'rgba(76,175,80,0.3)' },
  medium: { bg: 'rgba(255,152,0,0.15)', text: '#FF9800', border: 'rgba(255,152,0,0.3)' },
  high: { bg: 'rgba(244,67,54,0.15)', text: '#F44336', border: 'rgba(244,67,54,0.3)' },
};

export default function Reminders() {
  const [reminders, setReminders] = useState<Reminder[]>(loadReminders);
  const [filter, setFilter] = useState<FilterType>('all');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => { saveReminders(reminders); }, [reminders]);

  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];

  const filtered = useMemo(() => {
    let list = reminders;
    switch (filter) {
      case 'today':
        return list.filter(r => r.date === todayStr && !r.completed);
      case 'upcoming':
        return list.filter(r => r.date > todayStr && !r.completed);
      case 'overdue':
        return list.filter(r => r.date < todayStr && !r.completed);
      case 'completed':
        return list.filter(r => r.completed);
      default:
        return list.sort((a, b) => {
          if (a.completed !== b.completed) return a.completed ? 1 : -1;
          return a.date.localeCompare(b.date) || a.time.localeCompare(b.time);
        });
    }
  }, [reminders, filter, todayStr]);

  const counts = useMemo(() => ({
    all: reminders.filter(r => !r.completed).length,
    today: reminders.filter(r => r.date === todayStr && !r.completed).length,
    upcoming: reminders.filter(r => r.date > todayStr && !r.completed).length,
    overdue: reminders.filter(r => r.date < todayStr && !r.completed).length,
    completed: reminders.filter(r => r.completed).length,
  }), [reminders, todayStr]);

  const resetForm = () => {
    setTitle('');
    setDate(todayStr);
    setTime('12:00');
    setPriority('medium');
    setEditingId(null);
  };

  const openNew = () => {
    resetForm();
    setDate(todayStr);
    setTime(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
    setShowForm(true);
  };

  const startEdit = (r: Reminder) => {
    setEditingId(r.id);
    setTitle(r.title);
    setDate(r.date);
    setTime(r.time);
    setPriority(r.priority);
    setShowForm(true);
  };

  const saveReminder = () => {
    if (!title.trim()) return;
    if (editingId) {
      setReminders(prev => prev.map(r => r.id === editingId ? { ...r, title: title.trim(), date, time, priority } : r));
    } else {
      const newR: Reminder = {
        id: Date.now().toString(36) + Math.random().toString(36).slice(2),
        title: title.trim(), date, time, priority,
        completed: false, createdAt: Date.now(),
      };
      setReminders(prev => [...prev, newR]);
    }
    setShowForm(false);
    resetForm();
  };

  const toggleComplete = (id: string) => {
    setReminders(prev => prev.map(r => r.id === id ? { ...r, completed: !r.completed } : r));
  };

  const deleteReminder = (id: string) => {
    setReminders(prev => prev.filter(r => r.id !== id));
  };

  const filters: FilterType[] = ['all', 'today', 'upcoming', 'overdue', 'completed'];
  const filterLabels: Record<FilterType, string> = {
    all: 'All', today: 'Today', upcoming: 'Upcoming', overdue: 'Overdue', completed: 'Completed',
  };

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
        <Bell size={16} style={{ color: 'var(--accent-primary)' }} />
        <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>Reminders</span>
        <div className="relative">
          <button onClick={() => setShowFilters(!showFilters)} className="flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors" style={{ color: 'var(--text-secondary)', background: 'var(--bg-hover)' }}>
            {filterLabels[filter]} <ChevronDown size={12} />
          </button>
          {showFilters && (
            <div className="absolute right-0 top-7 z-20 rounded-md shadow-lg py-1 overflow-hidden" style={{ background: 'var(--bg-panel)', minWidth: '120px', border: '1px solid var(--border-subtle)' }}>
              {filters.map(f => (
                <button key={f} onClick={() => { setFilter(f); setShowFilters(false); }} className="flex items-center justify-between w-full px-3 py-1.5 text-xs transition-colors" style={{ color: filter === f ? 'var(--accent-primary)' : 'var(--text-primary)' }} onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  {filterLabels[f]} <span className="ml-2" style={{ color: 'var(--text-disabled)' }}>{counts[f]}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button onClick={openNew} className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs transition-colors" style={{ background: 'var(--accent-primary)', color: '#fff' }}>
          <Plus size={12} /> New
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="p-3 border-b" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-panel)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{editingId ? 'Edit' : 'New'} Reminder</span>
            <button onClick={() => { setShowForm(false); resetForm(); }} className="p-1 rounded"><X size={14} style={{ color: 'var(--text-secondary)' }} /></button>
          </div>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Reminder title..." className="w-full px-2.5 py-1.5 rounded-md text-sm mb-2 outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          <div className="flex gap-2 mb-2">
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className="flex-1 px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
            <input type="time" value={time} onChange={e => setTime(e.target.value)} className="px-2 py-1 rounded-md text-xs outline-none" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }} />
          </div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Priority:</span>
            {(['low', 'medium', 'high'] as const).map(p => (
              <button key={p} onClick={() => setPriority(p)} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs capitalize transition-colors" style={{ background: priority === p ? PRIORITY_COLORS[p].bg : 'transparent', color: priority === p ? PRIORITY_COLORS[p].text : 'var(--text-secondary)', border: `1px solid ${priority === p ? PRIORITY_COLORS[p].border : 'transparent'}` }}>
                <Flag size={10} /> {p}
              </button>
            ))}
          </div>
          <button onClick={saveReminder} className="w-full py-1.5 rounded-md text-xs font-medium" style={{ background: 'var(--accent-primary)', color: '#fff' }}>
            {editingId ? 'Update' : 'Add'} Reminder
          </button>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: 'var(--text-secondary)' }}>
            <Bell size={32} strokeWidth={1} />
            <p className="text-xs">No reminders</p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {filtered.map(r => {
              const isOverdue = !r.completed && r.date < todayStr;
              const pc = PRIORITY_COLORS[r.priority];
              return (
                <div key={r.id} className="flex items-start gap-2 p-2 rounded-md group transition-colors" style={{ background: r.completed ? 'transparent' : 'var(--bg-panel)', borderLeft: `3px solid ${r.completed ? 'var(--border-subtle)' : pc.text}`, opacity: r.completed ? 0.6 : 1 }}>
                  <button onClick={() => toggleComplete(r.id)} className="mt-0.5 p-0.5 rounded-full flex-shrink-0" style={{ border: `2px solid ${r.completed ? 'var(--accent-success)' : 'var(--border-default)'}`, background: r.completed ? 'var(--accent-success)' : 'transparent' }}>
                    {r.completed && <Check size={10} color="#fff" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)', textDecoration: r.completed ? 'line-through' : 'none' }}>{r.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="flex items-center gap-0.5 text-xs" style={{ color: isOverdue ? 'var(--accent-error)' : 'var(--text-secondary)' }}>
                        <Calendar size={10} /> {r.date}
                      </span>
                      <span className="flex items-center gap-0.5 text-xs" style={{ color: 'var(--text-disabled)' }}>
                        <Clock size={10} /> {r.time}
                      </span>
                      <span className="text-xs px-1 rounded" style={{ background: pc.bg, color: pc.text }}>{r.priority}</span>
                      {isOverdue && <AlertCircle size={10} style={{ color: 'var(--accent-error)' }} />}
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => startEdit(r)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><Edit2 size={12} /></button>
                    <button onClick={() => deleteReminder(r.id)} className="p-1 rounded" style={{ color: 'var(--accent-error)' }}><Trash2 size={12} /></button>
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
