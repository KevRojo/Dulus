import React, { useEffect, useState } from 'react';
import { Bot, Cpu, Terminal, Users, Lightbulb, Mic, Image as ImageIcon, Settings, Layers, MessageSquare, RefreshCw, Search } from 'lucide-react';
import { ViewMode, WebchatSession } from '../types.ts';
import { cn } from '../utils.ts';
// Imported (not a raw string path) so Vite bundles/inlines it — a hardcoded
// "./assets/mark.png" 404s in the single-file build (dist/assets is empty).
import markLogo from '../assets/mark.png';

interface SidebarProps {
  currentView: ViewMode;
  webchatUrl: string;
  activeSessionId: string | null;
  onViewChange: (view: ViewMode) => void;
  onSessionSelect: (session: WebchatSession) => void;
}

const formatSessionDate = (value?: string) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: '2-digit' });
};

export const Sidebar: React.FC<SidebarProps> = ({ currentView, webchatUrl, activeSessionId, onViewChange, onSessionSelect }) => {
  const [sessions, setSessions] = useState<WebchatSession[]>([]);
  const [query, setQuery] = useState('');
  const [loadingSessions, setLoadingSessions] = useState(false);

  const navItems = [
    { id: 'chat' as ViewMode, icon: Terminal, label: 'WebChat' },
    { id: 'core' as ViewMode, icon: Cpu, label: 'Core' },
    { id: 'roundtable' as ViewMode, icon: Layers, label: 'Round Table' },
    { id: 'agents' as ViewMode, icon: Users, label: 'Agents' },
    { id: 'brainstorm' as ViewMode, icon: Lightbulb, label: 'Brainstorm' },
    { id: 'vision' as ViewMode, icon: ImageIcon, label: 'Vision Forge' },
    { id: 'voice' as ViewMode, icon: Mic, label: 'Astral Voice' },
  ];

  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      const api = window.pywebview?.api;
      const data = api?.get_webchat_sessions
        ? await api.get_webchat_sessions(webchatUrl)
        : await fetch(`${webchatUrl.replace(/\/$/, '')}/api/sessions`).then(res => res.ok ? res.json() : []);
      setSessions(Array.isArray(data) ? data : []);
    } catch {
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    if (currentView === 'chat') {
      loadSessions();
    }
  }, [currentView, webchatUrl]);

  const visibleSessions = sessions.filter(session =>
    (session.title || 'Chat').toLowerCase().includes(query.toLowerCase())
  );

  const openPet = async () => {
    try {
      const result = await window.pywebview?.api?.open_pet_window?.();
      if (result && !result.ok) {
        window.alert(result.message || 'Could not open Dulus pet');
        console.warn(result.message || 'Could not open Dulus pet');
      } else if (!result) {
        window.alert('Dulus pet bridge is not available in this window.');
      }
    } catch (error) {
      window.alert(`Could not open Dulus pet: ${(error as Error).message}`);
      console.warn('Could not open Dulus pet', error);
    }
  };

  return (
    <div className="w-16 lg:w-64 h-full glass-panel border-r-dulus-border flex flex-col transition-all duration-300 z-20">
      <div className="h-16 flex items-center justify-center lg:justify-start lg:px-6 border-b border-dulus-border">
        <div className="relative flex-shrink-0 w-9 h-9 flex items-center justify-center">
          <div className="absolute -inset-1 bg-dulus-accent blur-md opacity-30 rounded-full"></div>
          <img 
            src={markLogo}
            alt="Dulus"
            className="relative z-10 w-full h-full object-cover rounded-xl border border-dulus-accent/50 shadow-[0_0_18px_rgba(251,191,36,0.28)]"
          />
        </div>
        <h1 className="hidden lg:block ml-3 text-xl font-bold tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-white to-dulus-accent">
          DULUS
        </h1>
      </div>

      <nav className="flex-1 w-full py-4 space-y-2 px-2 lg:px-3 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                "w-full flex items-center justify-center lg:justify-start p-3 rounded-xl transition-all duration-200 group relative",
                isActive 
                  ? "bg-dulus-primary/40 text-dulus-accent shadow-[0_0_15px_rgba(251,191,36,0.1)] border border-dulus-accent/20" 
                  : "text-dulus-muted hover:bg-white/5 hover:text-white border border-transparent"
              )}
              title={item.label}
            >
              {isActive && (
                <div className="absolute left-0 top-2 bottom-2 w-1 bg-dulus-accent rounded-r-full shadow-[0_0_10px_rgba(251,191,36,0.8)]"></div>
              )}
              <Icon className={cn("w-5 h-5 flex-shrink-0", isActive ? "text-dulus-accent" : "group-hover:text-white")} />
              <span className="hidden lg:block ml-3 font-medium text-sm tracking-wide truncate">{item.label}</span>
            </button>
          );
        })}

        {currentView === 'chat' && (
          <div className="hidden lg:block pt-4 mt-4 border-t border-white/10">
            <div className="flex items-center justify-between px-2 mb-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-dulus-muted">Chats</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => onSessionSelect({ id: `local-${Date.now()}`, title: 'New Chat', messages: [] })}
                  className="px-2 py-1 rounded-md text-[10px] text-dulus-accent hover:bg-dulus-accent/10"
                  title="New chat"
                >
                  New
                </button>
                <button
                  onClick={loadSessions}
                  className="p-1.5 rounded-md text-dulus-muted hover:text-white hover:bg-white/10"
                  title="Refresh chats"
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", loadingSessions && "animate-spin")} />
                </button>
              </div>
            </div>

            <div className="relative mb-2">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dulus-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full glass-input rounded-lg pl-9 pr-3 py-2 text-xs"
                placeholder="Search chats..."
              />
            </div>

            <div className="space-y-1 max-h-[42vh] overflow-y-auto pr-1">
              {visibleSessions.map(session => {
                const active = activeSessionId === session.id;
                return (
                  <button
                    key={session.id}
                    onClick={() => onSessionSelect(session)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-lg px-2 py-2 text-left border transition-colors",
                      active
                        ? "bg-dulus-accent/15 border-dulus-accent/40 text-white"
                        : "bg-black/20 border-transparent text-slate-400 hover:text-white hover:bg-white/5"
                    )}
                    title={session.title || 'Chat'}
                  >
                    <MessageSquare className={cn("w-4 h-4 flex-shrink-0", active ? "text-dulus-accent" : "text-dulus-muted")} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-semibold truncate">{session.title || 'Chat'}</span>
                      <span className="block text-[10px] text-dulus-muted">{formatSessionDate(session.saved_at)}</span>
                    </span>
                  </button>
                );
              })}

              {!loadingSessions && visibleSessions.length === 0 && (
                <div className="px-2 py-3 text-xs text-dulus-muted">
                  No chats found.
                </div>
              )}
            </div>
          </div>
        )}
      </nav>
      
      <div className="p-2 lg:p-4 border-t border-dulus-border space-y-2">
        <button
          onClick={openPet}
          className="w-full flex items-center justify-center lg:justify-start p-3 rounded-xl text-dulus-muted hover:bg-dulus-accent/10 hover:text-dulus-accent transition-colors"
          title="Open desktop pet"
        >
          <Bot className="w-5 h-5 flex-shrink-0" />
          <span className="hidden lg:block ml-3 font-medium text-sm">Pet</span>
        </button>
        <button className="w-full flex items-center justify-center lg:justify-start p-3 rounded-xl text-dulus-muted hover:bg-white/5 hover:text-white transition-colors">
          <Settings className="w-5 h-5 flex-shrink-0" />
          <span className="hidden lg:block ml-3 font-medium text-sm">Settings</span>
        </button>
      </div>
    </div>
  );
};

