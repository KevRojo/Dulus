// ============================================================
// AppContainer — Consistent shell for native Dulus apps
// ============================================================

import React from 'react';

interface AppContainerProps {
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}

const AppContainer: React.FC<AppContainerProps> = ({ children, className = '', noPadding = false }) => {
  return (
    <div
      className={`flex flex-col h-full w-full overflow-hidden ${className}`}
      style={{ background: 'var(--bg-window)' }}
    >
      <div className={`flex-1 overflow-auto custom-scrollbar ${noPadding ? '' : 'p-4'}`}>
        {children}
      </div>
    </div>
  );
};

export default AppContainer;
