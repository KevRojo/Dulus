// ============================================================
// AppLauncher — Full-screen overlay with search + app grid
// ============================================================

import { useState, useCallback, useRef, useEffect, memo } from 'react';
import { useOS } from '@/hooks/useOSStore';
import { getAppById } from '@/apps/registry';
import { Search, X } from 'lucide-react';
import * as Icons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

const DynamicIcon = ({ name, ...props }: { name: string } & LucideProps) => {
  const IconComp = (Icons as unknown as Record<string, React.ComponentType<LucideProps>>)[name];
  return IconComp ? <IconComp {...props} /> : null;
};

const CATEGORIES = ['Favorites', 'All', 'System', 'Productivity', 'Internet', 'Media', 'Games', 'DevTools', 'Creative'];

const AppLauncher = memo(function AppLauncher() {
  const { state, dispatch } = useOS();
  const { appLauncherOpen, apps, dockItems } = state;
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (appLauncherOpen) {
      setSearchQuery('');
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [appLauncherOpen]);

  // Close on Escape
  useEffect(() => {
    if (!appLauncherOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        dispatch({ type: 'SET_APP_LAUNCHER', open: false });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [appLauncherOpen, dispatch]);

  const handleLaunch = useCallback(
    (appId: string) => {
      dispatch({ type: 'SET_APP_LAUNCHER', open: false });
      // Small delay so launcher closes first
      setTimeout(() => {
        dispatch({ type: 'OPEN_WINDOW', appId });
      }, 150);
    },
    [dispatch]
  );

  const filteredApps = apps.filter((app) => {
    const matchesSearch = !searchQuery ||
      app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = activeCategory === 'All' || activeCategory === 'Favorites'
      ? true
      : app.category === activeCategory;
    const matchesFavorites = activeCategory !== 'Favorites' || dockItems.some((d) => d.appId === app.id && d.isPinned);
    return matchesSearch && matchesCategory && matchesFavorites;
  });

  const frequentApps = dockItems
    .filter((d) => d.isPinned)
    .map((d) => getAppById(d.appId))
    .filter(Boolean);

  if (!appLauncherOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[3000] flex flex-col items-center"
      style={{
        background: 'var(--bg-app-grid)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        animation: 'launcherFade 300ms ease',
        paddingTop: 32,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) dispatch({ type: 'SET_APP_LAUNCHER', open: false });
      }}
    >
      {/* Search bar */}
      <div
        className="relative w-[480px] max-w-[90vw]"
        style={{
          animation: 'searchSlideDown 400ms cubic-bezier(0, 0, 0.2, 1) 100ms both',
        }}
      >
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
        <input
          ref={inputRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Type to search applications..."
          className="w-full h-11 rounded-full pl-11 pr-10 text-sm outline-none transition-all"
          style={{
            background: 'var(--bg-input)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-primary)',
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--accent-primary)';
            e.currentTarget.style.boxShadow = '0 0 0 3px rgba(124,77,255,0.15)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-default)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        />
        {searchQuery && (
          <button
            onClick={() => { setSearchQuery(''); inputRef.current?.focus(); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Frequent apps (only when not searching) */}
      {!searchQuery && frequentApps.length > 0 && (
        <div className="mt-6 w-[480px] max-w-[90vw]"
          style={{ animation: 'searchSlideDown 300ms ease 200ms both' }}
        >
          <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-[0.1em] mb-3">Frequently Used</p>
          <div className="flex gap-4">
            {frequentApps.slice(0, 6).map((app) => (
              <button
                key={app!.id}
                onClick={() => handleLaunch(app!.id)}
                className="flex flex-col items-center gap-1 w-16 group"
              >
                <div className="w-12 h-12 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform"
                  style={{ background: 'var(--bg-hover)' }}>
                  <DynamicIcon name={app!.icon} size={24} className="text-[var(--text-primary)]" />
                </div>
                <span className="text-[10px] text-[var(--text-primary)] text-center truncate max-w-[64px]">{app!.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Category tabs */}
      {!searchQuery && (
        <div
          className="flex items-center gap-0 mt-6 overflow-x-auto max-w-[90vw]"
          style={{ animation: 'searchSlideDown 300ms ease 250ms both' }}
        >
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className="px-4 py-1.5 text-xs font-medium whitespace-nowrap transition-colors relative"
              style={{
                color: activeCategory === cat ? 'var(--accent-primary)' : 'var(--text-secondary)',
                borderBottom: activeCategory === cat ? '2px solid var(--accent-primary)' : '2px solid transparent',
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* App grid */}
      <div
        className="mt-6 w-[720px] max-w-[90vw] overflow-y-auto"
        style={{
          maxHeight: 'calc(100vh - 220px)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))',
          gap: 16,
          animation: 'gridAppear 300ms cubic-bezier(0.34, 1.56, 0.64, 1) 200ms both',
        }}
      >
        {filteredApps.map((app, index) => (
          <button
            key={app.id}
            onClick={() => handleLaunch(app.id)}
            className="flex flex-col items-center gap-1.5 p-2 rounded-2xl group transition-all"
            style={{
              animation: `iconPop 250ms cubic-bezier(0.34, 1.56, 0.64, 1) ${200 + index * 15}ms both`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-hover)';
              e.currentTarget.style.transform = 'scale(1.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
              style={{ background: 'var(--bg-hover)' }}>
              <DynamicIcon name={app.icon} size={32} className="text-[var(--text-primary)]" />
            </div>
            <span className="text-[10px] text-[var(--text-primary)] text-center truncate max-w-[72px]">
              {app.name}
            </span>
          </button>
        ))}

        {filteredApps.length === 0 && (
          <div className="col-span-full flex flex-col items-center justify-center py-12 text-[var(--text-secondary)]">
            <Search size={48} className="mb-4 opacity-30" />
            <p className="text-sm">No applications found</p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes launcherFade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes searchSlideDown {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes gridAppear {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes iconPop {
          from { opacity: 0; transform: scale(0.8); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
});

export default AppLauncher;
