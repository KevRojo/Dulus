// ============================================================
// WindowFrame v2 — Draggable, resizable window with Dulus animations
// ============================================================

import { useCallback, useRef, useState, memo, useEffect } from 'react';
import type { Window } from '@/types';
import { useOS } from '@/hooks/useOSStore';
import * as Icons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

const TOP_PANEL_HEIGHT = 28;
const RESIZE_HANDLE = 8;
const MIN_W = 320;
const MIN_H = 200;

const DynamicIcon = ({ name, ...props }: { name: string } & LucideProps) => {
  const IconComp = (Icons as unknown as unknown as Record<string, React.ComponentType<LucideProps>>)[name];
  return IconComp ? <IconComp {...props} /> : <Icons.HelpCircle {...props} />;
};

interface WindowFrameProps {
  window: Window;
  children: React.ReactNode;
}

type AnimationState = 'opening' | 'open' | 'minimizing' | 'minimized' | 'closing' | 'closed';

const WindowFrame = memo(function WindowFrame({ window: win, children }: WindowFrameProps) {
  const { dispatch } = useOS();
  const frameRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ isDragging: boolean; startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ isResizing: boolean; edge: string; startX: number; startY: number; origW: number; origH: number; origX: number; origY: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [animState, setAnimState] = useState<AnimationState>('opening');

  const isMaximized = win.state === 'maximized';
  const isMinimized = win.state === 'minimized';
  const isFocused = win.isFocused;

  // ---- Animation lifecycle ----
  useEffect(() => {
    if (animState === 'opening') {
      const t = setTimeout(() => setAnimState('open'), 350);
      return () => clearTimeout(t);
    }
    if (animState === 'minimizing') {
      const t = setTimeout(() => setAnimState('minimized'), 300);
      return () => clearTimeout(t);
    }
    if (animState === 'closing') {
      const t = setTimeout(() => setAnimState('closed'), 250);
      return () => clearTimeout(t);
    }
  }, [animState]);

  // Track state changes from OS for close/minimize
  const prevMinimized = useRef(isMinimized);
  useEffect(() => {
    if (!prevMinimized.current && isMinimized && animState === 'open') {
      setAnimState('minimizing');
    }
    prevMinimized.current = isMinimized;
  }, [isMinimized, animState]);

  const focusThis = useCallback(() => {
    if (!win.isFocused && win.state !== 'minimized') {
      dispatch({ type: 'FOCUS_WINDOW', windowId: win.id });
    }
  }, [dispatch, win.id, win.isFocused, win.state]);

  const handleMouseDown = useCallback(() => {
    focusThis();
  }, [focusThis]);

  // ---- Drag ----
  const handleTitleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (isMaximized || e.target !== e.currentTarget) return;
      e.preventDefault();
      dragRef.current = {
        isDragging: true,
        startX: e.clientX,
        startY: e.clientY,
        origX: win.position.x,
        origY: win.position.y,
      };
      setIsDragging(true);
    },
    [isMaximized, win.position.x, win.position.y]
  );

  // ---- Resize ----
  const getEdge = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    let edge = '';
    if (y < RESIZE_HANDLE) edge += 'n';
    if (y > rect.height - RESIZE_HANDLE) edge += 's';
    if (x < RESIZE_HANDLE) edge += 'w';
    if (x > rect.width - RESIZE_HANDLE) edge += 'e';
    return edge;
  }, []);

  const handleResizeMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (isMaximized) return;
      const edge = getEdge(e);
      if (!edge) return;
      e.preventDefault();
      e.stopPropagation();
      resizeRef.current = {
        isResizing: true,
        edge,
        startX: e.clientX,
        startY: e.clientY,
        origW: win.size.width,
        origH: win.size.height,
        origX: win.position.x,
        origY: win.position.y,
      };
      setIsResizing(true);
    },
    [isMaximized, getEdge, win.size, win.position]
  );

  const getCursor = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (isMaximized) return 'default';
    const edge = getEdge(e);
    const cursors: Record<string, string> = {
      n: 'n-resize', s: 's-resize', e: 'e-resize', w: 'w-resize',
      nw: 'nw-resize', ne: 'ne-resize', sw: 'sw-resize', se: 'se-resize',
    };
    return cursors[edge] || 'default';
  }, [isMaximized, getEdge]);

  // ---- Global mouse events for drag/resize ----
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (dragRef.current?.isDragging) {
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        let nx = dragRef.current.origX + dx;
        let ny = dragRef.current.origY + dy;
        const vw = window.innerWidth;
        ny = Math.max(TOP_PANEL_HEIGHT, ny);
        nx = Math.min(Math.max(nx, -(win.size.width - 100)), vw - 100);
        dispatch({ type: 'MOVE_WINDOW', windowId: win.id, position: { x: nx, y: ny } });
      }
      if (resizeRef.current?.isResizing) {
        const { edge, startX, startY, origW, origH, origX, origY } = resizeRef.current;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        let nx = origX, ny = origY, nw = origW, nh = origH;
        if (edge.includes('e')) nw = Math.max(MIN_W, origW + dx);
        if (edge.includes('s')) nh = Math.max(MIN_H, origH + dy);
        if (edge.includes('w')) {
          nw = Math.max(MIN_W, origW - dx);
          nx = origX + (origW - nw);
        }
        if (edge.includes('n')) {
          nh = Math.max(MIN_H, origH - dy);
          ny = origY + (origH - nh);
          ny = Math.max(TOP_PANEL_HEIGHT, ny);
        }
        dispatch({ type: 'MOVE_WINDOW', windowId: win.id, position: { x: nx, y: ny } });
        dispatch({ type: 'RESIZE_WINDOW', windowId: win.id, size: { width: nw, height: nh } });
      }
    };
    const onUp = () => {
      dragRef.current = null;
      resizeRef.current = null;
      setIsDragging(false);
      setIsResizing(false);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [dispatch, win.id, win.size.width, win.size.height]);

  const handleMinimize = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setAnimState('minimizing');
      setTimeout(() => {
        dispatch({ type: 'MINIMIZE_WINDOW', windowId: win.id });
      }, 280);
    },
    [dispatch, win.id]
  );

  const handleMaximize = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (isMaximized) {
        dispatch({ type: 'RESTORE_WINDOW', windowId: win.id });
      } else {
        dispatch({ type: 'MAXIMIZE_WINDOW', windowId: win.id });
      }
    },
    [dispatch, win.id, isMaximized]
  );

  const handleClose = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setAnimState('closing');
      setTimeout(() => {
        dispatch({ type: 'CLOSE_WINDOW', windowId: win.id });
      }, 240);
    },
    [dispatch, win.id]
  );

  const handleDoubleClickTitle = useCallback(() => {
    if (isMaximized) {
      dispatch({ type: 'RESTORE_WINDOW', windowId: win.id });
    } else {
      dispatch({ type: 'MAXIMIZE_WINDOW', windowId: win.id });
    }
  }, [dispatch, win.id, isMaximized]);

  if (animState === 'minimized' || animState === 'closed') return null;

  const isAnimating = animState === 'opening' || animState === 'minimizing' || animState === 'closing';

  const getAnimStyles = (): React.CSSProperties => {
    switch (animState) {
      case 'opening':
        return {
          opacity: 0,
          transform: 'scale(0.92) translateY(12px)',
          animation: 'windowOpen var(--duration-slow) var(--ease-spring) forwards',
        };
      case 'minimizing':
        return {
          opacity: 0,
          transform: 'scale(0.6) translateY(80px)',
          transition: 'all 300ms var(--ease-accelerate)',
          pointerEvents: 'none',
        };
      case 'closing':
        return {
          opacity: 0,
          transform: 'scale(0.95)',
          transition: 'all 240ms var(--ease-accelerate)',
          pointerEvents: 'none',
        };
      default:
        return {
          opacity: 1,
          transform: 'scale(1) translateY(0)',
          transition: isDragging || isResizing
            ? 'none'
            : 'box-shadow var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), transform var(--duration-normal) var(--ease-spring), opacity var(--duration-normal) var(--ease-default)',
        };
    }
  };

  return (
    <div
      ref={frameRef}
      className="absolute flex flex-col select-none"
      style={{
        left: win.position.x,
        top: win.position.y,
        width: win.size.width,
        height: win.size.height,
        zIndex: win.zIndex,
        borderRadius: isMaximized ? 0 : 12,
        border: `1px solid ${isFocused ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.06)'}`,
        boxShadow: isFocused
          ? '0 12px 40px rgba(0,0,0,0.55), 0 0 0 1px rgba(99,102,241,0.08)'
          : '0 4px 12px rgba(0,0,0,0.35)',
        overflow: 'hidden',
        ...getAnimStyles(),
      }}
      onMouseDown={handleMouseDown}
    >
      {/* Resize handles wrapper */}
      <div
        className="absolute inset-0 z-50"
        style={{
          cursor: getCursor as unknown as string,
          pointerEvents: isAnimating ? 'none' : 'none',
        }}
        onMouseDown={handleResizeMouseDown}
      >
        <div style={{ position: 'absolute', top: 0, left: RESIZE_HANDLE, right: RESIZE_HANDLE, height: RESIZE_HANDLE, cursor: 'n-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', bottom: 0, left: RESIZE_HANDLE, right: RESIZE_HANDLE, height: RESIZE_HANDLE, cursor: 's-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', left: 0, top: RESIZE_HANDLE, bottom: RESIZE_HANDLE, width: RESIZE_HANDLE, cursor: 'w-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', right: 0, top: RESIZE_HANDLE, bottom: RESIZE_HANDLE, width: RESIZE_HANDLE, cursor: 'e-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', top: 0, left: 0, width: RESIZE_HANDLE * 2, height: RESIZE_HANDLE * 2, cursor: 'nw-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', top: 0, right: 0, width: RESIZE_HANDLE * 2, height: RESIZE_HANDLE * 2, cursor: 'ne-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', bottom: 0, left: 0, width: RESIZE_HANDLE * 2, height: RESIZE_HANDLE * 2, cursor: 'sw-resize', pointerEvents: 'auto' }} />
        <div style={{ position: 'absolute', bottom: 0, right: 0, width: RESIZE_HANDLE * 2, height: RESIZE_HANDLE * 2, cursor: 'se-resize', pointerEvents: 'auto' }} />
      </div>

      {/* Title bar */}
      <div
        className="relative z-10 flex items-center justify-between shrink-0"
        style={{
          height: 36,
          background: isFocused ? 'var(--bg-titlebar)' : 'rgba(19,19,26,0.95)',
          borderRadius: isMaximized ? 0 : '12px 12px 0 0',
          transition: 'background var(--duration-fast) var(--ease-default)',
          cursor: isMaximized ? 'default' : 'grab',
        }}
        onMouseDown={handleTitleMouseDown}
        onDoubleClick={handleDoubleClickTitle}
      >
        {/* Left: icon + title */}
        <div className="flex items-center gap-2 px-3 overflow-hidden">
          <DynamicIcon name={win.icon} size={16} className="text-[var(--text-secondary)] shrink-0" />
          <span
            className="text-xs font-semibold truncate"
            style={{
              color: isFocused ? 'var(--text-primary)' : 'var(--text-secondary)',
              transition: 'color var(--duration-fast) var(--ease-default)',
            }}
          >
            {win.title}
          </span>
        </div>

        {/* Right: window controls */}
        <div className="flex items-center shrink-0">
          <button
            onClick={handleMinimize}
            className="w-9 h-9 flex items-center justify-center transition-colors"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'transparent'; }}
            title="Minimize"
          >
            <Icons.Minus size={14} />
          </button>
          <button
            onClick={handleMaximize}
            className="w-9 h-9 flex items-center justify-center transition-colors"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'transparent'; }}
            title={isMaximized ? 'Restore' : 'Maximize'}
          >
            {isMaximized ? <Icons.Copy size={12} /> : <Icons.Square size={12} />}
          </button>
          <button
            onClick={handleClose}
            className="w-9 h-9 flex items-center justify-center transition-colors"
            style={{
              borderRadius: isMaximized ? 0 : '0 12px 0 0',
              color: 'var(--text-secondary)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--accent-error)';
              e.currentTarget.style.color = 'white';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
            title="Close"
          >
            <Icons.X size={14} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div
        className="relative z-10 flex-1 overflow-hidden"
        style={{
          background: 'var(--bg-window)',
          borderRadius: isMaximized ? 0 : '0 0 12px 12px',
        }}
      >
        {children}
      </div>

      <style>{`
        @keyframes windowOpen {
          from {
            opacity: 0;
            transform: scale(0.92) translateY(12px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
      `}</style>
    </div>
  );
});

export default WindowFrame;
