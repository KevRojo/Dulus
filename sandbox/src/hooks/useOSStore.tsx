// ============================================================
// OS State Management — React Context + useReducer
// ============================================================

import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type { OSState, OSAction, Window, DesktopIcon, Notification, DockItem, WindowState } from '@/types';
import { APP_REGISTRY, getAppById, getDefaultDockApps } from '@/apps/registry';
import { getAssetPath } from '@/utils/assets';

// ---- Helpers ----
const generateId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const TOP_PANEL_HEIGHT = 28;

const createWindow = (state: OSState, appId: string, title?: string): Window => {
  const app = getAppById(appId);
  if (!app) throw new Error(`Unknown app: ${appId}`);
  const id = generateId();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const offset = (state.windows.filter((w) => w.appId === appId && w.state !== 'minimized').length) * 30;
  const x = Math.max(20, Math.min(vw - app.defaultSize.width - 20, 60 + offset));
  const y = Math.max(TOP_PANEL_HEIGHT + 10, Math.min(vh - app.defaultSize.height - 60, 40 + offset));
  return {
    id,
    appId,
    title: title || app.name,
    position: { x, y },
    size: { ...app.defaultSize },
    state: 'normal',
    isFocused: true,
    zIndex: state.nextZIndex,
    icon: app.icon,
    createdAt: Date.now(),
  };
};

// ---- Initial State ----
const defaultDesktopIcons: DesktopIcon[] = [
  { id: 'desk-home', name: 'Home', icon: 'Home', appId: 'filemanager', position: { x: 16, y: 16 }, isSelected: false },
  { id: 'desk-trash', name: 'Trash', icon: 'Trash2', appId: 'filemanager', position: { x: 16, y: 106 }, isSelected: false },
  { id: 'desk-text', name: 'Text Editor', icon: 'FileText', appId: 'texteditor', position: { x: 16, y: 196 }, isSelected: false },
  { id: 'desk-terminal', name: 'Terminal', icon: 'Terminal', appId: 'terminal', position: { x: 16, y: 286 }, isSelected: false },
  { id: 'desk-settings', name: 'Settings', icon: 'Settings', appId: 'settings', position: { x: 96, y: 16 }, isSelected: false },
  { id: 'desk-browser', name: 'Web Browser', icon: 'Globe', appId: 'browser', position: { x: 96, y: 106 }, isSelected: false },
  { id: 'desk-calendar', name: 'Calendar', icon: 'Calendar', appId: 'calendar', position: { x: 96, y: 196 }, isSelected: false },
];

const createInitialDockItems = (): DockItem[] => {
  const pinned = getDefaultDockApps();
  return APP_REGISTRY.map((app) => ({
    appId: app.id,
    isPinned: pinned.includes(app.id),
    isOpen: false,
    isFocused: false,
    bounce: false,
  }));
};

const loadDesktopIcons = (): DesktopIcon[] => {
  try {
    const saved = localStorage.getItem('dulus_desktop_icons');
    if (saved) return JSON.parse(saved) as DesktopIcon[];
  } catch { /* ignore */ }
  return defaultDesktopIcons;
};

const initialState: OSState = {
  bootPhase: 'off',
  auth: { isAuthenticated: false, isGuest: false, userName: 'KevRojo' },
  windows: [],
  apps: APP_REGISTRY,
  desktopIcons: loadDesktopIcons(),
  theme: {
    mode: 'dark',
    accent: '#6366F1',
    wallpaper: getAssetPath('/wallpapers/default.png'),
  },
  notifications: [],
  dockItems: createInitialDockItems(),
  contextMenu: {
    visible: false,
    x: 0,
    y: 0,
    type: 'desktop',
    items: [],
  },
  appLauncherOpen: false,
  notificationCenterOpen: false,
  activeWindowId: null,
  nextZIndex: 100,
  isAltTabbing: false,
  altTabIndex: 0,
};

// ---- Reducer ----
function osReducer(state: OSState, action: OSAction): OSState {
  switch (action.type) {
    case 'SET_BOOT_PHASE': {
      return { ...state, bootPhase: action.phase };
    }

    case 'LOGIN': {
      return {
        ...state,
        auth: { isAuthenticated: true, isGuest: action.isGuest, userName: action.isGuest ? 'Guest' : 'KevRojo' },
        bootPhase: 'desktop',
      };
    }

    case 'LOGOUT': {
      return {
        ...state,
        auth: { isAuthenticated: false, isGuest: false, userName: 'KevRojo' },
        windows: [],
        bootPhase: 'login',
        activeWindowId: null,
      };
    }

    case 'OPEN_WINDOW': {
      const win = createWindow(state, action.appId, action.title);
      const newWindows = state.windows.map((w) => ({ ...w, isFocused: false }));
      const updatedDock = state.dockItems.map((d) =>
        d.appId === action.appId ? { ...d, isOpen: true, isFocused: true, bounce: true } : { ...d, isFocused: false }
      );
      return {
        ...state,
        windows: [...newWindows, win],
        activeWindowId: win.id,
        nextZIndex: state.nextZIndex + 1,
        dockItems: updatedDock,
      };
    }

    case 'CLOSE_WINDOW': {
      const appId = state.windows.find((w) => w.id === action.windowId)?.appId;
      const remaining = state.windows.filter((w) => w.id !== action.windowId);
      const hasOtherWindows = remaining.some((w) => w.appId === appId && w.state !== 'minimized');
      let updatedDock = state.dockItems;
      if (appId && !hasOtherWindows) {
        updatedDock = state.dockItems.map((d) =>
          d.appId === appId ? { ...d, isOpen: false, isFocused: false } : d
        );
      }
      const newActiveId = remaining.length > 0
        ? remaining.reduce((a, b) => (a.zIndex > b.zIndex ? a : b)).id
        : null;
      return {
        ...state,
        windows: remaining,
        activeWindowId: newActiveId,
        dockItems: updatedDock,
      };
    }

    case 'MINIMIZE_WINDOW': {
      const win = state.windows.find((w) => w.id === action.windowId);
      if (!win) return state;
      const updated = state.windows.map((w) =>
        w.id === action.windowId
          ? { ...w, state: 'minimized' as WindowState, isFocused: false, prevPosition: { ...w.position }, prevSize: { ...w.size } }
          : w
      );
      const appId = win.appId;
      const hasVisible = updated.some((w) => w.appId === appId && w.state !== 'minimized');
      const updatedDock = state.dockItems.map((d) =>
        d.appId === appId ? { ...d, isFocused: hasVisible, isOpen: hasVisible || d.isPinned } : d
      );
      const newActiveId = updated
        .filter((w) => w.state !== 'minimized')
        .reduce((a, b) => (a && a.zIndex > b.zIndex ? a : b), null as Window | null);
      return { ...state, windows: updated, activeWindowId: newActiveId?.id ?? null, dockItems: updatedDock };
    }

    case 'MAXIMIZE_WINDOW': {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      return {
        ...state,
        windows: state.windows.map((w) =>
          w.id === action.windowId
            ? {
              ...w,
              state: 'maximized' as WindowState,
              prevPosition: { ...w.position },
              prevSize: { ...w.size },
              position: { x: 0, y: TOP_PANEL_HEIGHT },
              size: { width: vw, height: vh - TOP_PANEL_HEIGHT - 48 },
            }
            : w
        ),
      };
    }

    case 'RESTORE_WINDOW': {
      const win = state.windows.find((w) => w.id === action.windowId);
      if (!win) return state;
      return {
        ...state,
        windows: state.windows.map((w) =>
          w.id === action.windowId
            ? {
              ...w,
              state: 'normal' as WindowState,
              position: win.prevPosition || w.position,
              size: win.prevSize || w.size,
              prevPosition: undefined,
              prevSize: undefined,
            }
            : w
        ),
      };
    }

    case 'FOCUS_WINDOW': {
      const nextZ = state.nextZIndex + 1;
      return {
        ...state,
        windows: state.windows.map((w) =>
          w.id === action.windowId
            ? { ...w, isFocused: true, zIndex: nextZ }
            : { ...w, isFocused: false }
        ),
        activeWindowId: action.windowId,
        nextZIndex: nextZ,
        dockItems: state.dockItems.map((d) => {
          const isThisApp = state.windows.some((w) => w.id === action.windowId && w.appId === d.appId);
          return { ...d, isFocused: isThisApp };
        }),
      };
    }

    case 'MOVE_WINDOW': {
      return {
        ...state,
        windows: state.windows.map((w) =>
          w.id === action.windowId ? { ...w, position: action.position } : w
        ),
      };
    }

    case 'RESIZE_WINDOW': {
      return {
        ...state,
        windows: state.windows.map((w) =>
          w.id === action.windowId ? { ...w, size: action.size } : w
        ),
      };
    }

    case 'SET_ACTIVE_WINDOW': {
      return {
        ...state,
        activeWindowId: action.windowId,
        windows: state.windows.map((w) => ({ ...w, isFocused: w.id === action.windowId })),
      };
    }

    case 'TOGGLE_APP_LAUNCHER': {
      return { ...state, appLauncherOpen: !state.appLauncherOpen };
    }

    case 'SET_APP_LAUNCHER': {
      return { ...state, appLauncherOpen: action.open };
    }

    case 'TOGGLE_NOTIFICATION_CENTER': {
      return { ...state, notificationCenterOpen: !state.notificationCenterOpen };
    }

    case 'ADD_NOTIFICATION': {
      const notif: Notification = {
        ...action.notification,
        id: generateId(),
        timestamp: Date.now(),
        isRead: false,
      };
      return { ...state, notifications: [notif, ...state.notifications].slice(0, 50) };
    }

    case 'REMOVE_NOTIFICATION': {
      return { ...state, notifications: state.notifications.filter((n) => n.id !== action.id) };
    }

    case 'CLEAR_NOTIFICATIONS': {
      return { ...state, notifications: [] };
    }

    case 'MARK_NOTIFICATION_READ': {
      return {
        ...state,
        notifications: state.notifications.map((n) =>
          n.id === action.id ? { ...n, isRead: true } : n
        ),
      };
    }

    case 'ADD_DESKTOP_ICON': {
      const icon: DesktopIcon = { ...action.icon, id: generateId() };
      const next = [...state.desktopIcons, icon];
      localStorage.setItem('dulus_desktop_icons', JSON.stringify(next));
      return { ...state, desktopIcons: next };
    }

    case 'REMOVE_DESKTOP_ICON': {
      const next = state.desktopIcons.filter((i) => i.id !== action.id);
      localStorage.setItem('dulus_desktop_icons', JSON.stringify(next));
      return { ...state, desktopIcons: next };
    }

    case 'UPDATE_DESKTOP_ICON_POSITION': {
      const next = state.desktopIcons.map((i) =>
        i.id === action.id ? { ...i, position: action.position } : i
      );
      localStorage.setItem('dulus_desktop_icons', JSON.stringify(next));
      return { ...state, desktopIcons: next };
    }

    case 'SELECT_DESKTOP_ICON': {
      return {
        ...state,
        desktopIcons: state.desktopIcons.map((i) =>
          ({ ...i, isSelected: i.id === action.id })
        ),
      };
    }

    case 'RENAME_DESKTOP_ICON': {
      const next = state.desktopIcons.map((i) =>
        i.id === action.id ? { ...i, name: action.name } : i
      );
      localStorage.setItem('dulus_desktop_icons', JSON.stringify(next));
      return { ...state, desktopIcons: next };
    }

    case 'SET_THEME': {
      return { ...state, theme: { ...state.theme, ...action.theme } };
    }

    case 'TOGGLE_THEME': {
      const mode = state.theme.mode === 'dark' ? 'light' : 'dark';
      return { ...state, theme: { ...state.theme, mode } };
    }

    case 'PIN_DOCK_ITEM': {
      return {
        ...state,
        dockItems: state.dockItems.map((d) =>
          d.appId === action.appId ? { ...d, isPinned: true } : d
        ),
      };
    }

    case 'UNPIN_DOCK_ITEM': {
      return {
        ...state,
        dockItems: state.dockItems.map((d) =>
          d.appId === action.appId ? { ...d, isPinned: false } : d
        ),
      };
    }

    case 'BOUNCE_DOCK_ITEM': {
      return {
        ...state,
        dockItems: state.dockItems.map((d) =>
          d.appId === action.appId ? { ...d, bounce: true } : { ...d, bounce: false }
        ),
      };
    }

    case 'SHOW_CONTEXT_MENU': {
      return {
        ...state,
        contextMenu: {
          visible: true,
          x: action.x,
          y: action.y,
          type: action.menuType,
          items: action.items,
          contextData: action.contextData,
        },
      };
    }

    case 'HIDE_CONTEXT_MENU': {
      return { ...state, contextMenu: { ...state.contextMenu, visible: false } };
    }

    case 'START_ALT_TAB': {
      const visibleWins = state.windows.filter((w) => w.state !== 'minimized');
      return {
        ...state,
        isAltTabbing: true,
        altTabIndex: visibleWins.length > 0 ? visibleWins.length - 1 : 0,
      };
    }

    case 'CYCLE_ALT_TAB': {
      const visibleWins = state.windows.filter((w) => w.state !== 'minimized');
      return {
        ...state,
        altTabIndex: visibleWins.length > 0
          ? (state.altTabIndex + 1) % visibleWins.length
          : 0,
      };
    }

    case 'END_ALT_TAB': {
      const visibleWins = state.windows.filter((w) => w.state !== 'minimized');
      const target = visibleWins[state.altTabIndex];
      return {
        ...state,
        isAltTabbing: false,
        altTabIndex: 0,
        ...(target ? {
          activeWindowId: target.id,
          windows: state.windows.map((w) =>
            w.id === target.id ? { ...w, isFocused: true, zIndex: state.nextZIndex } : { ...w, isFocused: false }
          ),
          nextZIndex: state.nextZIndex + 1,
        } : {}),
      };
    }

    case 'CASCADE_WINDOWS': {
      let z = state.nextZIndex;
      const updated = state.windows.map((w, i) => ({
        ...w,
        position: { x: 40 + i * 30, y: TOP_PANEL_HEIGHT + 20 + i * 30 },
        zIndex: z++,
        isFocused: i === state.windows.length - 1,
      }));
      return {
        ...state,
        windows: updated,
        activeWindowId: updated.length > 0 ? updated[updated.length - 1].id : null,
        nextZIndex: z,
      };
    }

    case 'MINIMIZE_ALL': {
      return {
        ...state,
        windows: state.windows.map((w) =>
          w.state !== 'minimized'
            ? { ...w, state: 'minimized' as WindowState, isFocused: false }
            : w
        ),
        activeWindowId: null,
        dockItems: state.dockItems.map((d) => ({ ...d, isFocused: false })),
      };
    }

    default:
      return state;
  }
}

// ---- Context ----
interface OSContextType {
  state: OSState;
  dispatch: React.Dispatch<OSAction>;
}

const OSContext = createContext<OSContextType | null>(null);

export const OSProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(osReducer, initialState);
  return (
    <OSContext.Provider value={{ state, dispatch }}>
      {children}
    </OSContext.Provider>
  );
};

export const useOS = () => {
  const ctx = useContext(OSContext);
  if (!ctx) throw new Error('useOS must be used within OSProvider');
  return ctx;
};

// ---- Convenience hooks ----
export const useWindows = () => {
  const { state, dispatch } = useOS();
  return {
    windows: state.windows,
    openWindow: useCallback((appId: string, title?: string) => dispatch({ type: 'OPEN_WINDOW', appId, title }), [dispatch]),
    closeWindow: useCallback((windowId: string) => dispatch({ type: 'CLOSE_WINDOW', windowId }), [dispatch]),
    minimizeWindow: useCallback((windowId: string) => dispatch({ type: 'MINIMIZE_WINDOW', windowId }), [dispatch]),
    maximizeWindow: useCallback((windowId: string) => dispatch({ type: 'MAXIMIZE_WINDOW', windowId }), [dispatch]),
    restoreWindow: useCallback((windowId: string) => dispatch({ type: 'RESTORE_WINDOW', windowId }), [dispatch]),
    focusWindow: useCallback((windowId: string) => dispatch({ type: 'FOCUS_WINDOW', windowId }), [dispatch]),
    moveWindow: useCallback((windowId: string, position: { x: number; y: number }) => dispatch({ type: 'MOVE_WINDOW', windowId, position }), [dispatch]),
    resizeWindow: useCallback((windowId: string, size: { width: number; height: number }) => dispatch({ type: 'RESIZE_WINDOW', windowId, size }), [dispatch]),
    activeWindowId: state.activeWindowId,
  };
};

export const useNotifications = () => {
  const { state, dispatch } = useOS();
  return {
    notifications: state.notifications,
    addNotification: useCallback(
      (n: Omit<Notification, 'id' | 'timestamp'>) => dispatch({ type: 'ADD_NOTIFICATION', notification: n }),
      [dispatch]
    ),
    removeNotification: useCallback((id: string) => dispatch({ type: 'REMOVE_NOTIFICATION', id }), [dispatch]),
    clearNotifications: useCallback(() => dispatch({ type: 'CLEAR_NOTIFICATIONS' }), [dispatch]),
  };
};
