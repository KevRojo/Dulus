// ============================================================
// useDulusSkills — Hook for Dulus skills system (REST)
// ============================================================

import { useState, useCallback, useEffect } from 'react';
import { listSkills, invokeSkill, type SkillInfo } from '@/lib/dulus-api';

export interface UseDulusSkillsReturn {
  skills: SkillInfo[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  search: (query: string) => SkillInfo[];
  invoke: (skillName: string, args?: Record<string, unknown>) => Promise<unknown | null>;
}

export function useDulusSkills(): UseDulusSkillsReturn {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await listSkills();
    if (result.success && result.data) {
      setSkills(result.data);
    } else {
      setError(result.error || 'Failed to load skills');
      setSkills([]);
    }
    setIsLoading(false);
  }, []);

  const search = useCallback(
    (query: string) => {
      const q = query.toLowerCase();
      return skills.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          (s.description || '').toLowerCase().includes(q) ||
          (s.category || '').toLowerCase().includes(q)
      );
    },
    [skills]
  );

  const invoke = useCallback(async (skillName: string, args?: Record<string, unknown>) => {
    const result = await invokeSkill(skillName, args);
    if (result.success) return result.data ?? null;
    setError(result.error || `Failed to invoke skill: ${skillName}`);
    return null;
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { skills, isLoading, error, refresh, search, invoke };
}
