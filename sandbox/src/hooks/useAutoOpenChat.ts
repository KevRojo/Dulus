// ============================================================
// useAutoOpenChat — Listens for skill injection and opens Chat
// ============================================================

import { useEffect, useCallback } from 'react';
import { useSkillBridge, type SkillInjectPayload } from './useSkillBridge';

const EVENT_OPEN_CHAT = 'dulus:open-chat';

/** Emit event to open Chat app (listened by OS store or WindowManager) */
export function emitOpenChat(skillPayload?: SkillInjectPayload) {
  window.dispatchEvent(new CustomEvent(EVENT_OPEN_CHAT, { detail: skillPayload }));
}

/** Hook to listen for open-chat events */
export function useOpenChatListener(onOpenChat: (payload?: SkillInjectPayload) => void) {
  useEffect(() => {
    const handler = (e: Event) => {
      const payload = (e as CustomEvent<SkillInjectPayload | undefined>).detail;
      onOpenChat(payload);
    };
    window.addEventListener(EVENT_OPEN_CHAT, handler);
    return () => window.removeEventListener(EVENT_OPEN_CHAT, handler);
  }, [onOpenChat]);
}

/** Combined hook: listens for skill injection and emits open-chat event */
export function useAutoOpenChat() {
  const handleInject = useCallback((payload: SkillInjectPayload) => {
    emitOpenChat(payload);
  }, []);

  useSkillBridge(handleInject);
}
