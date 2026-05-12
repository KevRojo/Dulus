// ============================================================
// useSystemBattery — Real battery status via Navigator API
// ============================================================

import { useState, useEffect } from 'react';

// Minimal BatteryManager type for environments without full DOM typings
type BatteryManager = EventTarget & {
  level: number;
  charging: boolean;
  chargingTime: number;
  dischargingTime: number;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
};

export interface BatteryInfo {
  level: number;        // 0.0 - 1.0
  charging: boolean;
  chargingTime: number; // seconds
  dischargingTime: number; // seconds
  supported: boolean;
}

export function useSystemBattery(): BatteryInfo {
  const [battery, setBattery] = useState<BatteryInfo>({
    level: 1,
    charging: true,
    chargingTime: Infinity,
    dischargingTime: Infinity,
    supported: false,
  });

  useEffect(() => {
    let bat: BatteryManager | null = null;

    const updateBattery = () => {
      if (!bat) return;
      setBattery({
        level: bat.level,
        charging: bat.charging,
        chargingTime: bat.chargingTime,
        dischargingTime: bat.dischargingTime,
        supported: true,
      });
    };

    const init = async () => {
      try {
        // @ts-expect-error — getBattery is not in all TS DOM typings
        bat = await navigator.getBattery?.();
        if (bat) {
          updateBattery();
          bat.addEventListener('levelchange', updateBattery);
          bat.addEventListener('chargingchange', updateBattery);
          bat.addEventListener('chargingtimechange', updateBattery);
          bat.addEventListener('dischargingtimechange', updateBattery);
        }
      } catch {
        // silently fail — battery API not supported
      }
    };

    init();

    return () => {
      if (bat) {
        bat.removeEventListener('levelchange', updateBattery);
        bat.removeEventListener('chargingchange', updateBattery);
        bat.removeEventListener('chargingtimechange', updateBattery);
        bat.removeEventListener('dischargingtimechange', updateBattery);
      }
    };
  }, []);

  return battery;
}
