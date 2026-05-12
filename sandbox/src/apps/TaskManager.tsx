// ============================================================
// Task Manager — Dulus Native App (Hook-based)
// ============================================================

import { useState, useCallback } from 'react';
import {
  CheckCircle2, Circle, Clock, AlertCircle, Plus, RefreshCw,
  Trash2, Edit3, X, Save, Search, Filter, LayoutList, KanbanSquare,
  Tag, Calendar, User
} from 'lucide-react';
import { useDulusTasks } from '@/hooks/useDulusTasks';
import type { DulusTask } from '@/lib/dulus-api';

type ViewMode = 'list' | 'kanban';
type FilterStatus = 'all' | DulusTask['status'];

const STATUS_CONFIG: Record<DulusTask['status'], { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: 'Pending', color: 'var(--text-secondary)', icon: <Circle size={14} /> },
  in_progress: { label: 'In Progress', color: 'var(--accent-primary)', icon: <Clock size={14} /> },
  completed: { label: 'Completed', color: 'var(--accent-success)', icon: <CheckCircle2 size={14} /> },
  cancelled: { label: 'Cancelled', color: 'var(--accent-warning)', icon: <AlertCircle size={14} /> },
  deleted: { label: 'Deleted', color: 'var(--accent-error)', icon: <Trash2 size={14} /> },
};

const COLUMNS: DulusTask['status'][] = ['pending', 'in_progress', 'completed', 'cancelled'];

export default function TaskManager() {
  const { tasks, isLoading: loading, error, refresh: fetchTasks, create, update, moveStatus } = useDulusTasks();
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');
  const [filter, setFilter] = useState<FilterStatus>('all');
  const [search, setSearch] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);
  const [newSubject, setNewSubject] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editSubject, setEditSubject] = useState('');
  const [editDesc, setEditDesc] = useState('');

  const filtered = tasks.filter((t) => {
    if (filter !== 'all' && t.status !== filter) return false;
    const q = search.toLowerCase();
    if (q && !t.subject.toLowerCase().includes(q) && !(t.description || '').toLowerCase().includes(q)) return false;
    return true;
  });

  const handleCreate = async () => {
    if (!newSubject.trim()) return;
    await create({ subject: newSubject.trim(), description: newDesc.trim(), status: 'pending' });
    setNewSubject('');
    setNewDesc('');
    setShowNewForm(false);
  };

  const startEdit = (t: DulusTask) => {
    setEditingId(t.id);
    setEditSubject(t.subject);
    setEditDesc(t.description || '');
  };

  const saveEdit = async (id: string) => {
    await update(id, { subject: editSubject, description: editDesc });
    setEditingId(null);
  };

  const handleMoveStatus = async (id: string, status: DulusTask['status']) => {
    await moveStatus(id, status);
  };

  if (loading && tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-secondary)]">
        <RefreshCw size={32} className="animate-spin" />
        <p className="text-sm">Loading Dulus tasks...</p>
      </div>
    );
  }

  if (error && tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--accent-error)]">
        <AlertCircle size={32} />
        <p className="text-sm">{error}</p>
        <button onClick={fetchTasks} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border-default)' }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Task Manager</h2>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
            {tasks.length} tasks
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tasks..."
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', width: 180 }}
            />
          </div>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterStatus)}
            className="px-2 py-1.5 rounded-lg text-xs outline-none cursor-pointer"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="deleted">Deleted</option>
          </select>
          <div className="flex items-center border rounded-lg overflow-hidden" style={{ borderColor: 'var(--border-default)' }}>
            <button
              onClick={() => setViewMode('kanban')}
              className="px-2 py-1.5 text-xs flex items-center gap-1 transition-colors"
              style={{ background: viewMode === 'kanban' ? 'var(--accent-primary)' : 'var(--bg-input)', color: viewMode === 'kanban' ? 'white' : 'var(--text-secondary)' }}
            >
              <KanbanSquare size={14} /> Board
            </button>
            <button
              onClick={() => setViewMode('list')}
              className="px-2 py-1.5 text-xs flex items-center gap-1 transition-colors"
              style={{ background: viewMode === 'list' ? 'var(--accent-primary)' : 'var(--bg-input)', color: viewMode === 'list' ? 'white' : 'var(--text-secondary)' }}
            >
              <LayoutList size={14} /> List
            </button>
          </div>
          <button
            onClick={() => setShowNewForm(true)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white"
            style={{ background: 'var(--accent-primary)' }}
          >
            <Plus size={14} /> New
          </button>
          <button onClick={fetchTasks} className="p-1.5 rounded-lg" style={{ background: 'var(--bg-hover)' }}>
            <RefreshCw size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>
        </div>
      </div>

      {/* New task form */}
      {showNewForm && (
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)', background: 'var(--bg-hover)' }}>
          <div className="flex items-start gap-2">
            <div className="flex-1 space-y-2">
              <input
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                placeholder="Task subject..."
                autoFocus
                className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
              />
              <input
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Description (optional)..."
                className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <button onClick={handleCreate} className="p-2 rounded-lg text-white" style={{ background: 'var(--accent-success)' }}>
                <Save size={14} />
              </button>
              <button onClick={() => setShowNewForm(false)} className="p-2 rounded-lg" style={{ background: 'var(--bg-input)' }}>
                <X size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {viewMode === 'kanban' ? (
          <div className="flex gap-3 h-full min-w-max">
            {COLUMNS.map((col) => (
              <div key={col} className="w-64 flex flex-col">
                <div className="flex items-center justify-between mb-2 px-1">
                  <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: STATUS_CONFIG[col].color }}>
                    {STATUS_CONFIG[col].icon}
                    {STATUS_CONFIG[col].label}
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
                    {filtered.filter((t) => t.status === col).length}
                  </span>
                </div>
                <div className="flex-1 space-y-2">
                  {filtered
                    .filter((t) => t.status === col)
                    .map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        isEditing={editingId === task.id}
                        editSubject={editSubject}
                        editDesc={editDesc}
                        onEditSubjectChange={setEditSubject}
                        onEditDescChange={setEditDesc}
                        onStartEdit={() => startEdit(task)}
                        onSaveEdit={() => saveEdit(task.id)}
                        onCancelEdit={() => setEditingId(null)}
                        onMove={(status) => handleMoveStatus(task.id, status)}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            {filtered.map((task) => (
              <div
                key={task.id}
                className="flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors hover:bg-[var(--bg-hover)]"
                style={{ borderColor: 'var(--border-default)' }}
              >
                <div style={{ color: STATUS_CONFIG[task.status].color }}>{STATUS_CONFIG[task.status].icon}</div>
                {editingId === task.id ? (
                  <div className="flex-1 flex items-center gap-2">
                    <input
                      value={editSubject}
                      onChange={(e) => setEditSubject(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && saveEdit(task.id)}
                      autoFocus
                      className="flex-1 px-2 py-1 rounded text-xs outline-none"
                      style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
                    />
                    <button onClick={() => saveEdit(task.id)} className="p-1 rounded" style={{ color: 'var(--accent-success)' }}><Save size={12} /></button>
                    <button onClick={() => setEditingId(null)} className="p-1 rounded" style={{ color: 'var(--text-secondary)' }}><X size={12} /></button>
                  </div>
                ) : (
                  <>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>{task.subject}</p>
                      {task.description && <p className="text-[10px] truncate" style={{ color: 'var(--text-secondary)' }}>{task.description}</p>}
                    </div>
                    <div className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                      {task.owner && <span className="flex items-center gap-1"><User size={10} /> {task.owner}</span>}
                      <span className="flex items-center gap-1"><Calendar size={10} /> {new Date(task.created_at || task.createdAt || Date.now()).toLocaleDateString()}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => startEdit(task)} className="p-1 rounded hover:bg-[var(--bg-hover)]" style={{ color: 'var(--text-secondary)' }}><Edit3 size={12} /></button>
                      {task.status !== 'deleted' && (
                        <button onClick={() => handleMoveStatus(task.id, 'deleted')} className="p-1 rounded hover:bg-[var(--bg-hover)]" style={{ color: 'var(--accent-error)' }}><Trash2 size={12} /></button>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Task Card ──
function TaskCard({
  task,
  isEditing,
  editSubject,
  editDesc,
  onEditSubjectChange,
  onEditDescChange,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onMove,
}: {
  task: DulusTask;
  isEditing: boolean;
  editSubject: string;
  editDesc: string;
  onEditSubjectChange: (v: string) => void;
  onEditDescChange: (v: string) => void;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onMove: (status: DulusTask['status']) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);

  if (isEditing) {
    return (
      <div className="p-3 rounded-lg border space-y-2" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
        <input
          value={editSubject}
          onChange={(e) => onEditSubjectChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSaveEdit()}
          autoFocus
          className="w-full px-2 py-1.5 rounded text-xs outline-none"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
        />
        <input
          value={editDesc}
          onChange={(e) => onEditDescChange(e.target.value)}
          placeholder="Description..."
          className="w-full px-2 py-1.5 rounded text-xs outline-none"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
        />
        <div className="flex justify-end gap-1">
          <button onClick={onSaveEdit} className="px-2 py-1 rounded text-[10px] text-white" style={{ background: 'var(--accent-success)' }}>Save</button>
          <button onClick={onCancelEdit} className="px-2 py-1 rounded text-[10px]" style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)' }}>Cancel</button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="group p-3 rounded-lg border transition-all hover:shadow-sm cursor-pointer"
      style={{ background: 'var(--bg-panel)', borderColor: 'var(--border-default)' }}
      onClick={() => setShowMenu((v) => !v)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium leading-snug" style={{ color: 'var(--text-primary)' }}>{task.subject}</p>
          {task.description && (
            <p className="text-[10px] mt-1 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{task.description}</p>
          )}
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={(e) => { e.stopPropagation(); onStartEdit(); }} className="p-1 rounded hover:bg-[var(--bg-hover)]" style={{ color: 'var(--text-secondary)' }}><Edit3 size={12} /></button>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-2 text-[10px]" style={{ color: 'var(--text-secondary)' }}>
        {task.owner && <span className="flex items-center gap-1"><User size={10} /> {task.owner}</span>}
        <span className="flex items-center gap-1"><Calendar size={10} /> {new Date(task.created_at || task.createdAt || Date.now()).toLocaleDateString()}</span>
      </div>

      {showMenu && (
        <div className="mt-2 pt-2 border-t flex flex-wrap gap-1" style={{ borderColor: 'var(--border-default)' }}>
          {COLUMNS.filter((s) => s !== task.status).map((s) => (
            <button
              key={s}
              onClick={(e) => { e.stopPropagation(); onMove(s); setShowMenu(false); }}
              className="text-[10px] px-2 py-1 rounded transition-colors hover:opacity-90"
              style={{ background: STATUS_CONFIG[s].color + '22', color: STATUS_CONFIG[s].color, border: `1px solid ${STATUS_CONFIG[s].color}44` }}
            >
              Move to {STATUS_CONFIG[s].label}
            </button>
          ))}
          {task.status !== 'deleted' && (
            <button
              onClick={(e) => { e.stopPropagation(); onMove('deleted'); setShowMenu(false); }}
              className="text-[10px] px-2 py-1 rounded transition-colors hover:opacity-90"
              style={{ background: 'var(--accent-error)22', color: 'var(--accent-error)', border: '1px solid var(--accent-error)44' }}
            >
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  );
}
