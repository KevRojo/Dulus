// ============================================================
// useDulusEvents — SSE Bridge to OS Notifications
// Connects /api/events to the OS notification system
// ============================================================

import { useEffect, useRef, useCallback } from 'react';
import { useOS } from './useOSStore';

interface SSEEvent {
  type: string;
  payload: Record<string, unknown>;
}

const EVENT_ICONS: Record<string, string> = {
  task_created: 'ListChecks',
  task_updated: 'ListChecks',
  persona_created: 'User',
  persona_activated: 'UserCircle',
  plugin_reloaded: 'Plug',
  plugins_reloaded: 'Plug',
  marketplace_install: 'Download',
  marketplace_uninstall: 'Trash2',
  connected: 'Wifi',
  ping: 'Activity',
};

const EVENT_TITLES: Record<string, string> = {
  task_created: 'New Task',
  task_updated: 'Task Updated',
  persona_created: 'Persona Created',
  persona_activated: 'Persona Activated',
  plugin_reloaded: 'Plugin Reloaded',
  plugins_reloaded: 'Plugins Reloaded',
  marketplace_install: 'Plugin Installed',
  marketplace_uninstall: 'Plugin Uninstalled',
  connected: 'Connected',
  ping: 'Heartbeat',
};

export function useDulusEvents(enabled = true) {
  const { dispatch } = useOS();
  const esRef = useRef<EventSource | null>(null);

  const handleEvent = useCallback(
    (eventType: string, payload: Record<string, unknown>) => {
      // Skip low-noise events
      if (eventType === 'ping' || eventType === 'connected') return;

      const title = EVENT_TITLES[eventType] || eventType;
      const message =
        (payload.subject as string) ||
        (payload.name as string) ||
        (payload.message as string) ||
        JSON.stringify(payload).slice(0, 100);

      dispatch({
        type: 'ADD_NOTIFICATION',
        notification: {
          appId: 'dulus-core',
          appName: 'Dulus Core',
          appIcon: EVENT_ICONS[eventType] || 'Bell',
          title,
          message,
          isRead: false,
        },
      });
    },
    [dispatch]
  );

  useEffect(() => {
    if (!enabled) return;

    const es = new EventSource('/api/events');
    esRef.current = es;

    es.addEventListener('task_created', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        handleEvent('task_created', data);
      } catch { /* skip malformed */ }
    });

    es.addEventListener('task_updated', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        handleEvent('task_updated', data);
      } catch { /* skip malformed */ }
    });

    es.addEventListener('plugin_reloaded', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        handleEvent('plugin_reloaded', data);
      } catch { /* skip malformed */ }
    });

    es.addEventListener('plugins_reloaded', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        handleEvent('plugins_reloaded', data);
      } catch { /* skip malformed */ }
    });

    es.onerror = () => {
      // Silently reconnect — EventSource handles auto-reconnect
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [enabled, handleEvent]);

  return { connected: !!esRef.current };
}
