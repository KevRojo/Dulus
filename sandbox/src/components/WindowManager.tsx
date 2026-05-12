// ============================================================
// WindowManager — Renders all open windows, manages z-index
// ============================================================

import { memo } from 'react';
import { useOS } from '@/hooks/useOSStore';
import WindowFrame from './WindowFrame';
import AppRouter from '@/apps/AppRouter';

const WindowManager = memo(function WindowManager() {
  const { state } = useOS();
  const visibleWindows = state.windows.filter((w) => w.state !== 'minimized');

  return (
    <>
      {visibleWindows.map((win) => (
        <WindowFrame key={win.id} window={win}>
          <AppRouter appId={win.appId} windowId={win.id} />
        </WindowFrame>
      ))}
    </>
  );
});

export default WindowManager;
