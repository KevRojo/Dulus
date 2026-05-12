// ============================================================
// useDulusMemory — Hook for Dulus memory system (MemPalace)
// ============================================================

import { useState, useCallback, useEffect } from 'react';
import {
  fetchMemPalace,
  searchMemory,
  listWings,
  type MemoryEntry,
  type WingInfo,
  type MemPalaceData,
} from '@/lib/dulus-api';

export interface UseDulusMemoryReturn {
  data: MemPalaceData | null;
  entries: MemoryEntry[];
  wings: WingInfo[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  search: (query: string, limit?: number, wing?: string) => Promise<void>;
  clear: () => void;
}

export function useDulusMemory(): UseDulusMemoryReturn {
  const [data, setData] = useState<MemPalaceData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await fetchMemPalace();
    if (result.success && result.data) {
      setData(result.data);
    } else {
      setError(result.error || 'Failed to load memory palace');
      setData(null);
    }
    setIsLoading(false);
  }, []);

  const search = useCallback(async (query: string, limit = 10, wing?: string) => {
    setIsLoading(true);
    setError(null);
    const result = await searchMemory(query, limit, wing);
    if (result.success && result.data) {
      setData((prev) => ({
        ...(prev || { wings: [], stats: { total: 0, wings: 0 } }),
        entries: result.data!,
      }));
    } else {
      setError(result.error || 'Memory search failed');
    }
    setIsLoading(false);
  }, []);

  const clear = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    data,
    entries: data?.entries || [],
    wings: data?.wings || [],
    isLoading,
    error,
    refresh,
    search,
    clear,
  };
}
