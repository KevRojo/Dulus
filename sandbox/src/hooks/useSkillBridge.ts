// ============================================================
// useSkillBridge — Inter-app communication for skill injection
// ============================================================

import { useEffect, useCallback } from 'react';

export interface SkillInjectPayload {
  skillName: string;
  args?: Record<string, unknown>;
  timestamp: number;
}

const EVENT_NAME = 'dulus:skill-inject';

/** Emit a skill injection event that Chat (or any app) can listen to */
export function emitSkillInject(skillName: string, args?: Record<string, unknown>) {
  const payload: SkillInjectPayload = {
    skillName,
    args,
    timestamp: Date.now(),
  };
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: payload }));
}

/** Hook to listen for skill injection events */
export function useSkillBridge(onInject: (payload: SkillInjectPayload) => void) {
  useEffect(() => {
    const handler = (e: Event) => {
      const payload = (e as CustomEvent<SkillInjectPayload>).detail;
      if (payload) onInject(payload);
    };
    window.addEventListener(EVENT_NAME, handler);
    return () => window.removeEventListener(EVENT_NAME, handler);
  }, [onInject]);
}

/** Check if a skill should be sent to chat (Chat category or explicit flag) */
export function shouldSendToChat(skillName: string, category?: string): boolean {
  // Always send Chat category skills to chat
  if (category === 'Chat') return true;
  // Also send skills that have 'chat' in the name
  if (skillName.toLowerCase().includes('chat')) return true;
  // Default: don't auto-send to chat, let user decide
  return false;
}
