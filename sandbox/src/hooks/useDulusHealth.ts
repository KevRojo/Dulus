// ============================================================
// useDulusHealth — Backend connectivity + reconnection logic
// ============================================================

import { useState, useEffect, useRef, useCallback } from 'react';
import { checkHealth, type HealthStatus } from '@/lib/dulus-api';

export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'degraded';

export interface UseDulusHealthReturn {
  status: ConnectionState;
  health: HealthStatus | null;
  lastChecked: number;
  checkNow: () => Promise<void>;
}

export function useDulusHealth(pollIntervalMs = 10000): UseDulusHealthReturn {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [status, setStatus] = useState<ConnectionState>('connecting');
  const [lastChecked, setLastChecked] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const consecutiveFailures = useRef(0);

  const checkNow = useCallback(async () => {
    setStatus((prev) => (prev === 'disconnected' ? 'connecting' : prev));
    const result = await checkHealth(3000);
    setHealth(result);
    setLastChecked(Date.now());

    if (result.ok) {
      consecutiveFailures.current = 0;
      setStatus(result.latency > 800 ? 'degraded' : 'connected');
    } else {
      consecutiveFailures.current += 1;
      if (consecutiveFailures.current >= 3) {
        setStatus('disconnected');
      } else {
        setStatus('degraded');
      }
    }
  }, []);

  useEffect(() => {
    checkNow();
    intervalRef.current = setInterval(checkNow, pollIntervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [checkNow, pollIntervalMs]);

  return { status, health, lastChecked, checkNow };
}
