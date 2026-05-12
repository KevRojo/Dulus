// ============================================================
// ContextMenu — Dynamic right-click menu with edge detection
// ============================================================

import { useEffect, useRef, memo } from 'react';
import { useOS } from '@/hooks/useOSStore';
import { getAssetPath } from '@/utils/assets';
import { fsWrite } from '@/lib/dulus-api';
import * as Icons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

const DynamicIcon = ({ name, ...props }: { name: string } & LucideProps) => {
  const IconComp = (Icons as unknown as Record<string, React.ComponentType<LucideProps>>)[name];
  return IconComp ? <IconComp {...props} /> : null;
};

const WALLPAPERS = [
  getAssetPath('/wallpapers/default.jpeg'),
  getAssetPath('/wallpapers/light.jpeg'),
  getAssetPath('/wallpapers/nature.jpeg'),
  getAssetPath('/wallpapers/tech.jpeg')
];

const GRID_X = 80;
const GRID_Y = 90;

function findEmptyPosition(icons: { position: { x: number; y: number } }[]) {
  const taken = new Set(icons.map((i) => `${i.position.x},${i.position.y}`));
  let x = 16;
  let y = 16;
  while (taken.has(`${x},${y}`)) {
    y += GRID_Y;
    if (y > 400) {
      y = 16;
      x += GRID_X;
    }
  }
  return { x, y };
}

const ContextMenu = memo(function ContextMenu() {
  const { state, dispatch } = useOS();
  const menuRef = useRef<HTMLDivElement>(null);
  const { contextMenu, desktopIcons, theme } = state;

  useEffect(() => {
    if (!contextMenu.visible) return;
    const handleClick = () => dispatch({ type: 'HIDE_CONTEXT_MENU' });
    const timer = setTimeout(() => {
      window.addEventListener('click', handleClick, { once: true });
    }, 50);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('click', handleClick);
    };
  }, [contextMenu.visible, dispatch]);

  // Edge detection
  let x = contextMenu.x;
  let y = contextMenu.y;
  if (menuRef.current) {
    const rect = menuRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (x + rect.width > vw) x = vw - rect.width - 8;
    if (y + rect.height > vh) y = vh - rect.height - 8;
    if (x < 8) x = 8;
    if (y < 8) y = 8;
  }

  if (!contextMenu.visible) return null;

  const handleItemClick = (action: string) => {
    dispatch({ type: 'HIDE_CONTEXT_MENU' });

    if (action.startsWith('OPEN_APP:')) {
      const appId = action.slice(9);
      if (appId) dispatch({ type: 'OPEN_WINDOW', appId });
      return;
    }

    if (action === 'NEW_FOLDER') {
      const pos = findEmptyPosition(desktopIcons);
      dispatch({
        type: 'ADD_DESKTOP_ICON',
        icon: { name: 'New Folder', icon: 'Folder', appId: 'filemanager', position: pos, isSelected: false },
      });
      return;
    }

    if (action === 'NEW_DOCUMENT') {
      const pos = findEmptyPosition(desktopIcons);
      dispatch({
        type: 'ADD_DESKTOP_ICON',
        icon: { name: 'New Document', icon: 'FileText', appId: 'texteditor', position: pos, isSelected: false },
      });
      // Also create real file on backend FS
      fsWrite('/home/user/Desktop/New Document.txt', '').catch(() => {});
      return;
    }

    if (action === 'OPEN_TERMINAL') {
      const path = contextMenu.contextData?.path as string | undefined;
      if (path) sessionStorage.setItem('dulus_terminal_cwd', path);
      dispatch({ type: 'OPEN_WINDOW', appId: 'terminal' });
      return;
    }

    if (action === 'CHANGE_BG') {
      const currentWp = theme.wallpaper || WALLPAPERS[0];
      const idx = WALLPAPERS.indexOf(currentWp);
      const nextWp = WALLPAPERS[(idx + 1) % WALLPAPERS.length];
      dispatch({ type: 'SET_THEME', theme: { wallpaper: nextWp } });
      return;
    }

    if (action === 'ARRANGE_ICONS') {
      const cols = Math.floor((window.innerWidth - 32) / GRID_X);
      desktopIcons.forEach((icon, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        dispatch({
          type: 'UPDATE_DESKTOP_ICON_POSITION',
          id: icon.id,
          position: { x: 16 + col * GRID_X, y: 16 + row * GRID_Y },
        });
      });
      return;
    }

    if (action === 'SHOW_SETTINGS') {
      dispatch({ type: 'OPEN_WINDOW', appId: 'settings' });
      return;
    }

    if (action === 'CUT') {
      // Placeholder for clipboard cut
      return;
    }

    if (action === 'COPY') {
      const iconId = contextMenu.contextData?.iconId as string | undefined;
      const icon = iconId ? desktopIcons.find((i) => i.id === iconId) : undefined;
      const textToCopy = icon?.name || 'Dulus OS';
      navigator.clipboard.writeText(textToCopy).catch(() => {});
      return;
    }

    if (action === 'COPY_PATH') {
      const iconId = contextMenu.contextData?.iconId as string | undefined;
      const icon = desktopIcons.find((i) => i.id === iconId);
      const path = icon ? `/home/user/Desktop/${icon.name}` : '/home/user/Desktop';
      navigator.clipboard.writeText(path).catch(() => {});
      return;
    }

    if (action === 'RENAME') {
      const iconId = contextMenu.contextData?.iconId as string | undefined;
      if (!iconId) return;
      const icon = desktopIcons.find((i) => i.id === iconId);
      if (!icon) return;
      const newName = window.prompt('Rename:', icon.name);
      if (newName && newName.trim() && newName !== icon.name) {
        dispatch({ type: 'RENAME_DESKTOP_ICON', id: iconId, name: newName.trim() });
      }
      return;
    }

    if (action === 'TRASH') {
      const iconId = contextMenu.contextData?.iconId as string | undefined;
      if (iconId) dispatch({ type: 'REMOVE_DESKTOP_ICON', id: iconId });
      return;
    }

    if (action === 'MINIMIZE_ALL') {
      dispatch({ type: 'MINIMIZE_ALL' });
      return;
    }
  };

  return (
    <div
      ref={menuRef}
      className="fixed z-[4000] py-1.5 select-none"
      style={{
        left: x,
        top: y,
        minWidth: 180,
        maxWidth: 280,
        background: 'var(--bg-context-menu)',
        borderRadius: 8,
        border: '1px solid var(--border-default)',
        boxShadow: 'var(--shadow-lg)',
        animation: 'ctxAppear 120ms cubic-bezier(0, 0, 0.2, 1)',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {contextMenu.items.map((item) => {
        if (item.divider) {
          return (
            <div
              key={item.id}
              className="my-1 mx-2"
              style={{ height: 1, background: 'var(--border-subtle)' }}
            />
          );
        }
        return (
          <button
            key={item.id}
            className="w-full flex items-center gap-2.5 px-3 h-8 text-sm transition-colors"
            style={{
              color: item.disabled ? 'var(--text-disabled)' : 'var(--text-primary)',
              borderRadius: 4,
              margin: '0 4px',
              width: 'calc(100% - 8px)',
              cursor: item.disabled ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!item.disabled) e.currentTarget.style.background = 'var(--bg-hover)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
            onClick={() => {
              if (item.disabled) return;
              handleItemClick(item.action);
            }}
          >
            {item.icon && (
              <DynamicIcon name={item.icon} size={16} className="shrink-0" />
            )}
            <span className="flex-1 text-left truncate">{item.label}</span>
            {item.shortcut && (
              <span className="text-[10px] text-[var(--text-disabled)] ml-2">{item.shortcut}</span>
            )}
          </button>
        );
      })}

      <style>{`
        @keyframes ctxAppear {
          from { opacity: 0; transform: scale(0.95) translateY(-4px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
});

export default ContextMenu;
