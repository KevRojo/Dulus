// ============================================================
// useDulusTasks — Hook for Dulus task system (REST + SSE)
// ============================================================

import { useState, useCallback, useEffect, useRef } from 'react';
import {
  listTasks,
  createTask,
  updateTask,
  createTasksEventSource,
  type DulusTask,
} from '@/lib/dulus-api';

export interface UseDulusTasksReturn {
  tasks: DulusTask[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  getByStatus: (status: DulusTask['status']) => DulusTask[];
  create: (task: Omit<DulusTask, 'id'>) => Promise<DulusTask | null>;
  update: (taskId: string, updates: Partial<DulusTask>) => Promise<DulusTask | null>;
  moveStatus: (taskId: string, status: DulusTask['status']) => Promise<boolean>;
}

export function useDulusTasks(): UseDulusTasksReturn {
  const [tasks, setTasks] = useState<DulusTask[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await listTasks();
    if (result.success && result.data) {
      setTasks(result.data);
    } else {
      setError(result.error || 'Failed to load tasks');
      setTasks([]);
    }
    setIsLoading(false);
  }, []);

  // SSE live updates
  useEffect(() => {
    refresh();
    const es = createTasksEventSource();
    esRef.current = es;
    es.addEventListener('task_created', () => refresh());
    es.addEventListener('task_updated', () => refresh());
    es.onerror = () => { /* silently retry */ };
    return () => es.close();
  }, [refresh]);

  const create = useCallback(async (task: Omit<DulusTask, 'id'>) => {
    const result = await createTask(task);
    if (result.success && result.data) {
      setTasks((prev) => [...prev, result.data!]);
      return result.data;
    }
    setError(result.error || 'Failed to create task');
    return null;
  }, []);

  const update = useCallback(async (taskId: string, updates: Partial<DulusTask>) => {
    const result = await updateTask(taskId, updates);
    if (result.success && result.data) {
      setTasks((prev) => prev.map((t) => (t.id === taskId ? result.data! : t)));
      return result.data;
    }
    setError(result.error || 'Failed to update task');
    return null;
  }, []);

  const moveStatus = useCallback(async (taskId: string, status: DulusTask['status']) => {
    const result = await updateTask(taskId, { status });
    if (result.success && result.data) {
      setTasks((prev) => prev.map((t) => (t.id === taskId ? result.data! : t)));
      return true;
    }
    return false;
  }, []);

  const getByStatus = useCallback(
    (status: DulusTask['status']) => tasks.filter((t) => t.status === status),
    [tasks]
  );

  return { tasks, isLoading, error, refresh, getByStatus, create, update, moveStatus };
}
