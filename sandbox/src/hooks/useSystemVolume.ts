// ============================================================
// useSystemVolume — System volume control (persisted in localStorage)
// ============================================================

import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'dulus-system-volume';

export interface VolumeInfo {
  level: number;   // 0 - 100
  muted: boolean;
}

export function useSystemVolume(): VolumeInfo & {
  setLevel: (v: number) => void;
  toggleMute: () => void;
} {
  const [volume, setVolumeState] = useState<VolumeInfo>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch { /* ignore */ }
    return { level: 80, muted: false };
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(volume));
  }, [volume]);

  const setLevel = useCallback((v: number) => {
    setVolumeState((prev) => ({ ...prev, level: Math.max(0, Math.min(100, v)) }));
  }, []);

  const toggleMute = useCallback(() => {
    setVolumeState((prev) => ({ ...prev, muted: !prev.muted }));
  }, []);

  return { ...volume, setLevel, toggleMute };
}
