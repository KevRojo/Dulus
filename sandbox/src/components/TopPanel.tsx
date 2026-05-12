// ============================================================
// TopPanel — Activities button, clock, system tray
// ============================================================

import { useState, useEffect, useCallback, memo, useRef } from 'react';
import { format } from 'date-fns';
import {
  Wifi, Volume2, VolumeX, Battery, BatteryCharging,
  BatteryLow, BatteryMedium, BatteryFull, BatteryWarning,
  Power, Keyboard, Accessibility, Activity, Bot, CheckCircle2, Clock,
  WifiOff, Signal, SignalHigh, SignalMedium, SignalLow,
} from 'lucide-react';
import { useOS } from '@/hooks/useOSStore';
import { useDulusHealth } from '@/hooks/useDulusHealth';
import { useDulusAgents } from '@/hooks/useDulusAgents';
import { useDulusTasks } from '@/hooks/useDulusTasks';
import { useSystemBattery } from '@/hooks/useSystemBattery';
import { useSystemNetwork } from '@/hooks/useSystemNetwork';
import { useSystemVolume } from '@/hooks/useSystemVolume';

const TopPanel = memo(function TopPanel() {
  const { state, dispatch } = useOS();
  const [time, setTime] = useState(new Date());
  const [sysMenuOpen, setSysMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { status: healthStatus } = useDulusHealth(15000);
  const { runningCount: activeAgents, refresh: refreshAgents } = useDulusAgents();
  const { getByStatus, refresh: refreshTasks } = useDulusTasks();
  const battery = useSystemBattery();
  const network = useSystemNetwork();
  const { level: volLevel, muted: volMuted, toggleMute: volToggle } = useSystemVolume();

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Refresh Dulus stats when system menu opens
  useEffect(() => {
    if (sysMenuOpen) {
      refreshAgents();
      refreshTasks();
    }
  }, [sysMenuOpen, refreshAgents, refreshTasks]);

  useEffect(() => {
    if (!sysMenuOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setSysMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [sysMenuOpen]);

  const handleActivities = useCallback(() => {
    dispatch({ type: 'TOGGLE_APP_LAUNCHER' });
  }, [dispatch]);

  const handleClockClick = useCallback(() => {
    dispatch({ type: 'TOGGLE_NOTIFICATION_CENTER' });
  }, [dispatch]);

  const formattedTime = format(time, 'EEE h:mm a');
  const formattedDate = format(time, 'EEEE, MMMM d, yyyy');

  return (
    <div
      className="fixed top-0 left-0 right-0 z-[200] flex items-center justify-between px-3 text-xs font-medium select-none"
      style={{
        height: 32,
        background: 'var(--bg-panel)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
        color: 'var(--text-primary)',
      }}
    >
      {/* Left: Activities / Dulus */}
      <div className="flex items-center gap-1 min-w-0 shrink-0">
        <button
          onClick={handleActivities}
          className="h-7 px-3 rounded-md hover:bg-[var(--bg-hover)] transition-colors text-xs font-semibold tracking-wide"
        >
          Dulus
        </button>
      </div>

      {/* Center: Clock */}
      <button
        onClick={handleClockClick}
        className="h-7 px-3 rounded-md hover:bg-[var(--bg-hover)] transition-colors text-xs font-medium group relative mx-auto"
      >
        <span className="whitespace-nowrap">{formattedTime}</span>
        {/* Tooltip */}
        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 px-2.5 py-1 rounded-md bg-[var(--bg-tooltip)] text-[var(--text-primary)] text-[11px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[5000]">
          {formattedDate}
        </div>
      </button>

      {/* Right: System tray */}
      <div className="flex items-center gap-0.5 shrink-0">
        <button className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-hover)] transition-colors">
          <Accessibility size={14} />
        </button>
        <button className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-hover)] transition-colors">
          <Keyboard size={14} />
        </button>
        <button
          className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-hover)] transition-colors relative"
          title={`Backend: ${healthStatus}`}
        >
          <Activity
            size={14}
            className={
              healthStatus === 'connected'
                ? 'text-green-400'
                : healthStatus === 'degraded'
                ? 'text-yellow-400'
                : 'text-red-400'
            }
          />
          <span
            className={`absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full ${
              healthStatus === 'connected'
                ? 'bg-green-400'
                : healthStatus === 'degraded'
                ? 'bg-yellow-400'
                : 'bg-red-400'
            }`}
          />
        </button>
        {/* Network */}
        <button
          className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-hover)] transition-colors group relative"
          title={network.online ? `Network: ${network.effectiveType.toUpperCase()} (${network.downlink} Mbps)` : 'Offline'}
        >
          {network.online ? (
            network.effectiveType === '4g' ? <SignalHigh size={14} /> :
            network.effectiveType === '3g' ? <SignalMedium size={14} /> :
            network.effectiveType === '2g' ? <SignalLow size={14} /> :
            <Signal size={14} />
          ) : (
            <WifiOff size={14} className="text-red-400" />
          )}
          <div className="absolute top-full right-0 mt-1 px-2.5 py-1 rounded-md bg-[var(--bg-tooltip)] text-[var(--text-primary)] text-[11px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[5000]">
            {network.online
              ? `${network.type.toUpperCase()} • ${network.downlink} Mbps • ${network.rtt}ms RTT`
              : 'No network connection'}
          </div>
        </button>

        {/* Volume */}
        <button
          onClick={volToggle}
          className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-hover)] transition-colors group relative"
          title={volMuted ? 'Unmute' : `Volume: ${volLevel}%`}
        >
          {volMuted ? <VolumeX size={14} className="text-red-400" /> : <Volume2 size={14} />}
          <div className="absolute top-full right-0 mt-1 px-2.5 py-1 rounded-md bg-[var(--bg-tooltip)] text-[var(--text-primary)] text-[11px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[5000]">
            {volMuted ? 'Muted' : `Volume: ${volLevel}%`}
          </div>
        </button>

        {/* Battery */}
        <button
          className="h-7 px-1.5 rounded-md hover:bg-[var(--bg-hover)] transition-colors flex items-center gap-1 group relative"
          title={battery.supported
            ? `Battery: ${Math.round(battery.level * 100)}%${battery.charging ? ' (charging)' : ''}`
            : 'Battery status unavailable'}
        >
          {battery.charging ? (
            <BatteryCharging size={14} className="text-green-400" />
          ) : battery.level <= 0.2 ? (
            <BatteryWarning size={14} className="text-red-400" />
          ) : battery.level <= 0.4 ? (
            <BatteryLow size={14} />
          ) : battery.level <= 0.7 ? (
            <BatteryMedium size={14} />
          ) : (
            <BatteryFull size={14} />
          )}
          <span className="text-[11px] tabular-nums">
            {battery.supported ? `${Math.round(battery.level * 100)}%` : '—'}
          </span>
          <div className="absolute top-full right-0 mt-1 px-2.5 py-1 rounded-md bg-[var(--bg-tooltip)] text-[var(--text-primary)] text-[11px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[5000]">
            {battery.supported
              ? `${Math.round(battery.level * 100)}%${battery.charging ? ' • Charging' : ' • On battery'}`
              : 'Battery status unavailable'}
          </div>
        </button>
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setSysMenuOpen(!sysMenuOpen)}
            className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-hover)] transition-colors"
          >
            <Power size={14} />
          </button>

          {sysMenuOpen && (
            <div
              className="absolute top-full right-0 mt-1 py-2 rounded-xl z-[5000]"
              style={{
                background: 'var(--bg-context-menu)',
                boxShadow: 'var(--shadow-lg)',
                border: '1px solid var(--border-default)',
                width: 260,
                animation: 'menuAppear 120ms cubic-bezier(0, 0, 0.2, 1)',
              }}
            >
              {/* User row */}
              <div className="flex items-center gap-2.5 px-3 py-2.5 mb-1">
                <div className="w-9 h-9 rounded-full flex items-center justify-center shrink-0" style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-primary-active))' }}>
                  <span className="text-white text-sm font-bold">{state.auth.userName.charAt(0).toUpperCase()}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium block truncate">{state.auth.userName}</span>
                  <span className="text-[10px] text-[var(--text-secondary)]">Dulus OS</span>
                </div>
                <button
                  className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-[var(--bg-hover)] shrink-0"
                  onClick={() => {
                    setSysMenuOpen(false);
                    dispatch({ type: 'OPEN_WINDOW', appId: 'settings' });
                  }}
                >
                  <span className="text-sm">⚙</span>
                </button>
              </div>

              {/* Dulus Status Dashboard */}
              <div className="px-3 py-2">
                <div className="text-[10px] font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>
                  Dulus Status
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Activity size={12} style={{ color: 'var(--text-secondary)' }} />
                      <span className="text-xs">Backend</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${healthStatus === 'connected' ? 'bg-emerald-400' : healthStatus === 'degraded' ? 'bg-amber-400' : 'bg-rose-400'}`} />
                      <span className="text-[10px] capitalize" style={{ color: 'var(--text-secondary)' }}>{healthStatus}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Bot size={12} style={{ color: 'var(--text-secondary)' }} />
                      <span className="text-xs">Active Agents</span>
                    </div>
                    <span className="text-xs font-semibold px-1.5 py-0.5 rounded-md" style={{ background: 'var(--accent-primary)22', color: 'var(--accent-primary)' }}>
                      {activeAgents}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Clock size={12} style={{ color: 'var(--text-secondary)' }} />
                      <span className="text-xs">Pending Tasks</span>
                    </div>
                    <span className="text-xs font-semibold px-1.5 py-0.5 rounded-md" style={{ background: 'var(--accent-warning)22', color: 'var(--accent-warning)' }}>
                      {getByStatus('pending').length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={12} style={{ color: 'var(--text-secondary)' }} />
                      <span className="text-xs">In Progress</span>
                    </div>
                    <span className="text-xs font-semibold px-1.5 py-0.5 rounded-md" style={{ background: 'var(--accent-success)22', color: 'var(--accent-success)' }}>
                      {getByStatus('in_progress').length}
                    </span>
                  </div>
                </div>
              </div>

              <div className="my-1.5 mx-3" style={{ height: 1, background: 'var(--border-subtle)' }} />

              {[
                { label: 'Wired Connection', icon: '🌐', toggle: true },
                { label: 'Wi-Fi', icon: '📶', toggle: true },
                { label: 'Bluetooth', icon: '🔵', toggle: true },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2.5 px-3 py-2 hover:bg-[var(--bg-hover)] cursor-pointer">
                  <span className="text-sm">{item.icon}</span>
                  <span className="text-sm flex-1">{item.label}</span>
                  {item.toggle && (
                    <div className="w-8 h-5 rounded-full relative shrink-0" style={{ background: 'var(--accent-primary)' }}>
                      <div className="absolute right-0.5 top-0.5 w-4 h-4 rounded-full bg-white" />
                    </div>
                  )}
                </div>
              ))}

              <div className="my-1.5 mx-3" style={{ height: 1, background: 'var(--border-subtle)' }} />

              <button
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-[var(--bg-hover)] transition-colors text-left"
                onClick={() => { setSysMenuOpen(false); dispatch({ type: 'LOGOUT' }); }}
              >
                <span>🔒</span>
                Lock
              </button>
              <button
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-[var(--bg-hover)] transition-colors text-left"
                onClick={() => { setSysMenuOpen(false); dispatch({ type: 'LOGOUT' }); }}
              >
                <span>🚪</span>
                Log Out
              </button>
              <button
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-[var(--bg-hover)] transition-colors text-left"
                onClick={() => setSysMenuOpen(false)}
              >
                <span>⏻</span>
                Power Off / Restart
              </button>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes menuAppear {
          from { opacity: 0; transform: scale(0.95) translateY(-4px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
});

export default TopPanel;
