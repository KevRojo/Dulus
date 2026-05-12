// ============================================================
// Todo List — Task management with projects, priorities, filters
// ============================================================

import { useState, useEffect, useMemo } from 'react';
import {
  CheckSquare, Plus, Calendar,
  Trash2, Edit2, Check,
} from 'lucide-react';

interface Task {
  id: string;
  title: string;
  completed: boolean;
  dueDate: string;
  priority: 'none' | 'low' | 'medium' | 'high';
  tags: string[];
  projectId: string;
  createdAt: number;
}

interface Project {
  id: string;
  name: string;
  isSystem: boolean;
  icon: string;
}

const DEFAULT_PROJECTS: Project[] = [
  { id: 'inbox', name: 'Inbox', isSystem: true, icon: 'inbox' },
  { id: 'today', name: 'Today', isSystem: true, icon: 'today' },
  { id: 'upcoming', name: 'Upcoming', isSystem: true, icon: 'upcoming' },
  { id: 'completed', name: 'Completed', isSystem: true, icon: 'completed' },
];

const PRIORITY_COLORS: Record<string, string> = {
  none: 'var(--text-disabled)',
  low: 'var(--accent-info)',
  medium: 'var(--accent-warning)',
  high: 'var(--accent-error)',
};

const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const loadTasks = (): Task[] => {
  try {
    const saved = localStorage.getItem('dulus_todos');
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  const today = new Date().toISOString().split('T')[0];
  return [
    { id: generateId(), title: 'Explore the Dulus OS desktop', completed: false, dueDate: today, priority: 'high', tags: ['welcome'], projectId: 'inbox', createdAt: Date.now() },
    { id: generateId(), title: 'Try the terminal app', completed: false, dueDate: today, priority: 'medium', tags: ['welcome'], projectId: 'inbox', createdAt: Date.now() - 10000 },
    { id: generateId(), title: 'Customize your settings', completed: true, dueDate: today, priority: 'low', tags: [], projectId: 'inbox', createdAt: Date.now() - 20000 },
  ];
};

const loadCustomProjects = (): Project[] => {
  try {
    const saved = localStorage.getItem('dulus_todo_projects');
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return [];
};

const Todo: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>(loadTasks);
  const [customProjects, setCustomProjects] = useState<Project[]>(loadCustomProjects);
  const [selectedProject, setSelectedProject] = useState('inbox');
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all');
  const [showAddTask, setShowAddTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDate, setNewTaskDate] = useState(new Date().toISOString().split('T')[0]);
  const [newTaskPriority, setNewTaskPriority] = useState<Task['priority']>('none');
  const [editingTask, setEditingTask] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [sortBy, setSortBy] = useState<'date' | 'priority'>('date');

  useEffect(() => {
    localStorage.setItem('dulus_todos', JSON.stringify(tasks));
  }, [tasks]);

  useEffect(() => {
    localStorage.setItem('dulus_todo_projects', JSON.stringify(customProjects));
  }, [customProjects]);

  const today = new Date().toISOString().split('T')[0];

  const filteredTasks = useMemo(() => {
    let filtered = tasks;

    // Project filter
    if (selectedProject === 'today') filtered = tasks.filter(t => t.dueDate === today && !t.completed);
    else if (selectedProject === 'upcoming') filtered = tasks.filter(t => t.dueDate > today && !t.completed);
    else if (selectedProject === 'completed') filtered = tasks.filter(t => t.completed);
    else if (selectedProject !== 'all') filtered = tasks.filter(t => t.projectId === selectedProject);
    else filtered = tasks.filter(t => !t.completed);

    // Status filter
    if (filter === 'active') filtered = filtered.filter(t => !t.completed);
    if (filter === 'completed') filtered = filtered.filter(t => t.completed);

    // Sort
    filtered.sort((a, b) => {
      if (sortBy === 'priority') {
        const pMap = { high: 3, medium: 2, low: 1, none: 0 };
        return pMap[b.priority] - pMap[a.priority];
      }
      return a.dueDate.localeCompare(b.dueDate);
    });

    return filtered;
  }, [tasks, selectedProject, filter, sortBy, today]);

  const stats = useMemo(() => {
    const total = tasks.length;
    const completed = tasks.filter(t => t.completed).length;
    return { total, completed, percent: total === 0 ? 0 : Math.round((completed / total) * 100) };
  }, [tasks]);

  const addTask = () => {
    if (!newTaskTitle.trim()) return;
    const task: Task = {
      id: generateId(),
      title: newTaskTitle,
      completed: false,
      dueDate: newTaskDate,
      priority: newTaskPriority,
      tags: [],
      projectId: selectedProject === 'today' || selectedProject === 'upcoming' || selectedProject === 'completed' ? 'inbox' : selectedProject,
      createdAt: Date.now(),
    };
    setTasks(prev => [...prev, task]);
    setNewTaskTitle('');
    setShowAddTask(false);
  };

  const toggleTask = (id: string) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
  };

  const deleteTask = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id));
  };

  const saveEdit = (id: string) => {
    if (!editTitle.trim()) { setEditingTask(null); return; }
    setTasks(prev => prev.map(t => t.id === id ? { ...t, title: editTitle } : t));
    setEditingTask(null);
  };

  const createProject = () => {
    if (!newProjectName.trim()) return;
    const project: Project = { id: generateId(), name: newProjectName, isSystem: false, icon: 'custom' };
    setCustomProjects(prev => [...prev, project]);
    setNewProjectName('');
    setShowNewProject(false);
  };

  const projectCount = (projectId: string) => {
    if (projectId === 'today') return tasks.filter(t => t.dueDate === today && !t.completed).length;
    if (projectId === 'upcoming') return tasks.filter(t => t.dueDate > today && !t.completed).length;
    if (projectId === 'completed') return tasks.filter(t => t.completed).length;
    return tasks.filter(t => t.projectId === projectId && !t.completed).length;
  };

  const allProjects = [...DEFAULT_PROJECTS, ...customProjects];

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Sidebar */}
      <div className="w-48 shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-titlebar)' }}>
        <div className="p-2 space-y-0.5 flex-1 overflow-y-auto custom-scrollbar">
          {allProjects.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedProject(p.id)}
              className="flex items-center gap-2 w-full px-2.5 py-2 rounded-lg text-xs transition-colors"
              style={{
                background: selectedProject === p.id ? 'var(--bg-selected)' : 'transparent',
                color: selectedProject === p.id ? 'var(--accent-primary)' : 'var(--text-primary)',
              }}
            >
              <CheckSquare size={14} />
              <span className="flex-1 text-left">{p.name}</span>
              <span className="text-[10px] text-[var(--text-disabled)]">{projectCount(p.id)}</span>
            </button>
          ))}

          <div className="pt-2 border-t mt-2" style={{ borderColor: 'var(--border-subtle)' }}>
            <button
              onClick={() => setShowNewProject(!showNewProject)}
              className="flex items-center gap-2 w-full px-2.5 py-2 rounded-lg text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            >
              <Plus size={14} /> New List
            </button>
            {showNewProject && (
              <div className="flex items-center gap-1 px-2 mt-1">
                <input
                  value={newProjectName}
                  onChange={e => setNewProjectName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') createProject(); if (e.key === 'Escape') setShowNewProject(false); }}
                  placeholder="List name"
                  className="flex-1 h-7 px-2 rounded text-xs text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                  autoFocus
                />
                <button onClick={createProject} className="text-[var(--accent-primary)]"><Check size={14} /></button>
              </div>
            )}
          </div>
        </div>

        {/* Progress */}
        <div className="p-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-[var(--text-secondary)]">{stats.completed} / {stats.total} done</span>
            <span className="text-[10px] text-[var(--accent-primary)] font-semibold">{stats.percent}%</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border-subtle)' }}>
            <div className="h-full rounded-full transition-all" style={{ width: `${stats.percent}%`, background: 'var(--accent-primary)' }} />
          </div>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)' }}>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {allProjects.find(p => p.id === selectedProject)?.name}
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSortBy(s => s === 'date' ? 'priority' : 'date')}
              className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] px-2 py-1 rounded hover:bg-[var(--bg-hover)]"
            >
              Sort: {sortBy}
            </button>
            {(['all', 'active', 'completed'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="text-xs capitalize px-2 py-1 rounded transition-colors"
                style={{
                  background: filter === f ? 'var(--bg-selected)' : 'transparent',
                  color: filter === f ? 'var(--accent-primary)' : 'var(--text-secondary)',
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Add task */}
        <div className="px-4 py-2 border-b shrink-0" style={{ borderColor: 'var(--border-subtle)' }}>
          {!showAddTask ? (
            <button
              onClick={() => setShowAddTask(true)}
              className="flex items-center gap-2 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <Plus size={14} /> Add Task
            </button>
          ) : (
            <div className="space-y-2">
              <input
                value={newTaskTitle}
                onChange={e => setNewTaskTitle(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') addTask(); if (e.key === 'Escape') setShowAddTask(false); }}
                placeholder="What needs to be done?"
                className="w-full h-9 px-3 rounded-lg text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                autoFocus
              />
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={newTaskDate}
                  onChange={e => setNewTaskDate(e.target.value)}
                  className="h-7 px-2 rounded text-xs text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                />
                <select
                  value={newTaskPriority}
                  onChange={e => setNewTaskPriority(e.target.value as Task['priority'])}
                  className="h-7 px-2 rounded text-xs text-[var(--text-primary)] outline-none"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                >
                  <option value="none">No Priority</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                <div className="flex-1" />
                <button onClick={() => setShowAddTask(false)} className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] px-2 py-1">Cancel</button>
                <button onClick={addTask} className="text-xs font-medium text-white px-3 py-1.5 rounded" style={{ background: 'var(--accent-primary)' }}>Add</button>
              </div>
            </div>
          )}
        </div>

        {/* Task list */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {filteredTasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-2">
              <CheckSquare size={32} className="text-[var(--text-disabled)] opacity-30" />
              <div className="text-xs text-[var(--text-secondary)]">No tasks here</div>
            </div>
          ) : (
            filteredTasks.map(task => (
              <div
                key={task.id}
                className="flex items-center gap-3 px-4 py-2.5 border-b transition-colors group"
                style={{ borderColor: 'var(--border-subtle)' }}
              >
                {/* Priority indicator */}
                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: PRIORITY_COLORS[task.priority] }} />

                {/* Checkbox */}
                <button
                  onClick={() => toggleTask(task.id)}
                  className="w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors"
                  style={{
                    borderColor: task.completed ? 'var(--accent-success)' : 'var(--border-default)',
                    background: task.completed ? 'var(--accent-success)' : 'transparent',
                  }}
                >
                  {task.completed && <Check size={12} className="text-white" />}
                </button>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {editingTask === task.id ? (
                    <div className="flex items-center gap-2">
                      <input
                        value={editTitle}
                        onChange={e => setEditTitle(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') saveEdit(task.id); if (e.key === 'Escape') setEditingTask(null); }}
                        className="flex-1 h-7 px-2 rounded text-sm text-[var(--text-primary)] outline-none"
                        style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)' }}
                        autoFocus
                      />
                      <button onClick={() => saveEdit(task.id)} className="text-[var(--accent-primary)]"><Check size={14} /></button>
                    </div>
                  ) : (
                    <div
                      className="text-sm cursor-pointer"
                      style={{
                        color: task.completed ? 'var(--text-disabled)' : 'var(--text-primary)',
                        textDecoration: task.completed ? 'line-through' : 'none',
                      }}
                      onClick={() => { setEditingTask(task.id); setEditTitle(task.title); }}
                    >
                      {task.title}
                    </div>
                  )}
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[10px] flex items-center gap-0.5 ${task.dueDate < today && !task.completed ? 'text-[var(--accent-error)]' : 'text-[var(--text-disabled)]'}`}>
                      <Calendar size={10} /> {task.dueDate}
                    </span>
                    {task.priority !== 'none' && (
                      <span className="text-[10px] capitalize" style={{ color: PRIORITY_COLORS[task.priority] }}>{task.priority}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="hidden group-hover:flex items-center gap-1">
                  <button
                    onClick={() => { setEditingTask(task.id); setEditTitle(task.title); }}
                    className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]"
                  >
                    <Edit2 size={12} />
                  </button>
                  <button
                    onClick={() => deleteTask(task.id)}
                    className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--accent-error)]"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default Todo;
