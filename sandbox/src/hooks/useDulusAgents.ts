// ============================================================
// useDulusAgents — Hook for Dulus agents (REST + polling)
// ============================================================

import { useState, useCallback, useEffect, useRef } from 'react';
import { listAgents, type AgentInfo } from '@/lib/dulus-api';

export interface UseDulusAgentsReturn {
  agents: AgentInfo[];
  runningCount: number;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  liveMode: boolean;
  setLiveMode: (v: boolean) => void;
}

export function useDulusAgents(pollInterval = 3000): UseDulusAgentsReturn {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveMode, setLiveMode] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await listAgents();
    if (result.success && result.data) {
      setAgents(result.data);
    } else {
      setError(result.error || 'Failed to load agents');
      setAgents([]);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    if (liveMode) {
      intervalRef.current = setInterval(refresh, pollInterval);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh, liveMode, pollInterval]);

  const runningCount = agents.filter((a) => a.status === 'running').length;

  return { agents, runningCount, isLoading, error, refresh, liveMode, setLiveMode };
}
