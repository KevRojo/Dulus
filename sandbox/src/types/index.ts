// ============================================================
// Dulus OS — Core Type Definitions
// ============================================================

export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export type WindowState = 'normal' | 'minimized' | 'maximized';

export interface Window {
  id: string;
  appId: string;
  title: string;
  position: Position;
  size: Size;
  state: WindowState;
  prevPosition?: Position;
  prevSize?: Size;
  isFocused: boolean;
  zIndex: number;
  icon: string;
  createdAt: number;
}

export type AppCategory =
  | 'System'
  | 'Productivity'
  | 'Internet'
  | 'Media'
  | 'Games'
  | 'DevTools'
  | 'Creative';

export interface AppDefinition {
  id: string;
  name: string;
  icon: string;
  category: AppCategory;
  description: string;
  defaultSize: Size;
  minSize: Size;
  component?: string;
}

// --------------------------------------------------------
// Virtual File System
// --------------------------------------------------------

export type FileNodeType = 'file' | 'folder';

export interface FileSystemNode {
  id: string;
  name: string;
  type: FileNodeType;
  parentId: string | null;
  createdAt: number;
  modifiedAt: number;
  content?: string;
  size?: number;
  isHidden?: boolean;
}

export interface TrashItemMetadata {
  originalPath: string;
  deletedAt: number;
}

export interface FileSystemState {
  nodes: Record<string, FileSystemNode>;
  trashMetadata: Record<string, TrashItemMetadata>;
}

// --------------------------------------------------------
// Desktop
// --------------------------------------------------------

export interface DesktopIcon {
  id: string;
  name: string;
  icon: string;
  appId?: string;
  fileSystemNodeId?: string;
  position: Position;
  isSelected: boolean;
}

// --------------------------------------------------------
// Theme
// --------------------------------------------------------

export type ThemeMode = 'dark' | 'light';

export interface Theme {
  mode: ThemeMode;
  accent: string;
  wallpaper: string;
}

// --------------------------------------------------------
// Notifications
// --------------------------------------------------------

export interface Notification {
  id: string;
  appId: string;
  appName: string;
  appIcon: string;
  title: string;
  message: string;
  timestamp: number;
  isRead: boolean;
  actions?: NotificationAction[];
}

export interface NotificationAction {
  label: string;
  action: string;
}

// --------------------------------------------------------
// Dock
// --------------------------------------------------------

export interface DockItem {
  appId: string;
  isPinned: boolean;
  isOpen: boolean;
  isFocused: boolean;
  bounce: boolean;
}

// --------------------------------------------------------
// Context Menu
// --------------------------------------------------------

export type ContextMenuType = 'desktop' | 'file' | 'dockIcon' | 'windowTitle' | 'text';

export interface ContextMenuItem {
  id: string;
  label: string;
  icon?: string;
  shortcut?: string;
  action: string;
  disabled?: boolean;
  divider?: boolean;
  submenu?: ContextMenuItem[];
  toggle?: boolean;
  toggled?: boolean;
}

export interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  type: ContextMenuType;
  items: ContextMenuItem[];
  contextData?: Record<string, unknown>;
}

// --------------------------------------------------------
// Boot / Auth
// --------------------------------------------------------

export type BootPhase = 'off' | 'logo' | 'loading' | 'transition' | 'desktop' | 'login' | 'complete';

export interface AuthState {
  isAuthenticated: boolean;
  isGuest: boolean;
  userName: string;
}

// --------------------------------------------------------
// OS Store State
// --------------------------------------------------------

export interface OSState {
  bootPhase: BootPhase;
  auth: AuthState;
  windows: Window[];
  apps: AppDefinition[];
  desktopIcons: DesktopIcon[];
  theme: Theme;
  notifications: Notification[];
  dockItems: DockItem[];
  contextMenu: ContextMenuState;
  appLauncherOpen: boolean;
  notificationCenterOpen: boolean;
  activeWindowId: string | null;
  nextZIndex: number;
  isAltTabbing: boolean;
  altTabIndex: number;
}

// --------------------------------------------------------
// Actions
// --------------------------------------------------------

export type OSAction =
  | { type: 'SET_BOOT_PHASE'; phase: BootPhase }
  | { type: 'LOGIN'; isGuest: boolean }
  | { type: 'LOGOUT' }
  | { type: 'OPEN_WINDOW'; appId: string; title?: string }
  | { type: 'CLOSE_WINDOW'; windowId: string }
  | { type: 'MINIMIZE_WINDOW'; windowId: string }
  | { type: 'MAXIMIZE_WINDOW'; windowId: string }
  | { type: 'RESTORE_WINDOW'; windowId: string }
  | { type: 'FOCUS_WINDOW'; windowId: string }
  | { type: 'MOVE_WINDOW'; windowId: string; position: Position }
  | { type: 'RESIZE_WINDOW'; windowId: string; size: Size }
  | { type: 'SET_ACTIVE_WINDOW'; windowId: string | null }
  | { type: 'TOGGLE_APP_LAUNCHER' }
  | { type: 'SET_APP_LAUNCHER'; open: boolean }
  | { type: 'TOGGLE_NOTIFICATION_CENTER' }
  | { type: 'ADD_NOTIFICATION'; notification: Omit<Notification, 'id' | 'timestamp'> }
  | { type: 'REMOVE_NOTIFICATION'; id: string }
  | { type: 'CLEAR_NOTIFICATIONS' }
  | { type: 'MARK_NOTIFICATION_READ'; id: string }
  | { type: 'ADD_DESKTOP_ICON'; icon: Omit<DesktopIcon, 'id'> }
  | { type: 'REMOVE_DESKTOP_ICON'; id: string }
  | { type: 'UPDATE_DESKTOP_ICON_POSITION'; id: string; position: Position }
  | { type: 'SELECT_DESKTOP_ICON'; id: string | null }
  | { type: 'RENAME_DESKTOP_ICON'; id: string; name: string }
  | { type: 'SET_THEME'; theme: Partial<Theme> }
  | { type: 'TOGGLE_THEME' }
  | { type: 'PIN_DOCK_ITEM'; appId: string }
  | { type: 'UNPIN_DOCK_ITEM'; appId: string }
  | { type: 'BOUNCE_DOCK_ITEM'; appId: string }
  | { type: 'SHOW_CONTEXT_MENU'; x: number; y: number; menuType: ContextMenuType; items: ContextMenuItem[]; contextData?: Record<string, unknown> }
  | { type: 'HIDE_CONTEXT_MENU' }
  | { type: 'START_ALT_TAB' }
  | { type: 'CYCLE_ALT_TAB' }
  | { type: 'END_ALT_TAB' }
  | { type: 'CASCADE_WINDOWS' }
  | { type: 'MINIMIZE_ALL' };

// --------------------------------------------------------
// File Associations
// --------------------------------------------------------

export interface FileAssociation {
  extension: string;
  appId: string;
  icon: string;
  mimeType: string;
}
