// ============================================================
// Agent Monitor — Dulus Native App (Hook-based)
// ============================================================

import { useState } from 'react';
import {
  Bot, Activity, Clock, RefreshCw, AlertCircle, Terminal,
  Cpu, Radio, Circle, Pause, Play, Square, Zap, Eye
} from 'lucide-react';
import { useDulusAgents } from '@/hooks/useDulusAgents';
import type { AgentInfo } from '@/lib/dulus-api';

const STATUS_STYLES: Record<AgentInfo['status'], { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  idle: { color: 'var(--text-secondary)', bg: 'var(--text-secondary)15', icon: <Circle size={12} />, label: 'Idle' },
  running: { color: 'var(--accent-primary)', bg: 'var(--accent-primary)15', icon: <Activity size={12} className="animate-pulse" />, label: 'Running' },
  paused: { color: 'var(--accent-warning)', bg: 'var(--accent-warning)15', icon: <Pause size={12} />, label: 'Paused' },
  completed: { color: 'var(--accent-success)', bg: 'var(--accent-success)15', icon: <Square size={12} />, label: 'Completed' },
  error: { color: 'var(--accent-error)', bg: 'var(--accent-error)15', icon: <AlertCircle size={12} />, label: 'Error' },
};

export default function AgentMonitor() {
  const { agents, isLoading: loading, error, refresh: fetchAgents, liveMode, setLiveMode } = useDulusAgents();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<AgentInfo['status'] | 'all'>('all');

  const filtered = agents.filter((a) => filterStatus === 'all' || a.status === filterStatus);
  const activeAgent = agents.find((a) => a.id === selectedAgent);

  const statusCounts = agents.reduce((acc, a) => {
    acc[a.status] = (acc[a.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  if (loading && agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-secondary)]">
        <Bot size={32} className="animate-bounce" />
        <p className="text-sm">Scanning Dulus agents...</p>
      </div>
    );
  }

  if (error && agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--accent-error)]">
        <AlertCircle size={32} />
        <p className="text-sm">{error}</p>
        <button onClick={fetchAgents} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border-default)' }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-3">
          <Bot size={18} style={{ color: 'var(--accent-primary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Agent Monitor</h2>
          <div className="flex gap-2">
            {(['running', 'idle', 'paused', 'error'] as const).map((s) => (
              <span key={s} className="text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1" style={{ background: STATUS_STYLES[s].bg, color: STATUS_STYLES[s].color }}>
                {STATUS_STYLES[s].icon} {statusCounts[s] || 0}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLiveMode(!liveMode)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${liveMode ? 'text-white' : ''}`}
            style={{ background: liveMode ? 'var(--accent-success)' : 'var(--bg-hover)', color: liveMode ? 'white' : 'var(--text-secondary)' }}
          >
            <Radio size={12} className={liveMode ? 'animate-pulse' : ''} /> {liveMode ? 'Live' : 'Paused'}
          </button>
          <button onClick={fetchAgents} className="p-1.5 rounded-lg" style={{ color: 'var(--text-secondary)' }}>
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex gap-1 px-4 py-2 border-b" style={{ borderColor: 'var(--border-default)' }}>
        {(['all', 'running', 'idle', 'paused', 'completed', 'error'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className="px-3 py-1 rounded-md text-[11px] font-medium capitalize transition-colors"
            style={{
              background: filterStatus === s ? STATUS_STYLES[s === 'all' ? 'idle' : s].color + '20' : 'transparent',
              color: filterStatus === s ? (s === 'all' ? 'var(--text-primary)' : STATUS_STYLES[s].color) : 'var(--text-secondary)',
            }}
          >
            {s} {s !== 'all' && `(${statusCounts[s] || 0})`}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Agent list */}
        <div className="w-72 flex-shrink-0 overflow-auto border-r" style={{ borderColor: 'var(--border-default)' }}>
          {agents.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-2 p-4">
              <Bot size={32} opacity={0.4} />
              <p className="text-xs text-center font-medium">No agents running</p>
              <p className="text-[10px] text-center opacity-70">Agents will appear here when started</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-2 p-4">
              <Bot size={24} />
              <p className="text-xs text-center">No agents match this filter</p>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {filtered.map((agent) => {
                const style = STATUS_STYLES[agent.status];
                const isSelected = selectedAgent === agent.id;
                return (
                  <button
                    key={agent.id}
                    onClick={() => setSelectedAgent(agent.id)}
                    className="w-full text-left p-2.5 rounded-lg transition-all border"
                    style={{
                      background: isSelected ? 'var(--bg-hover)' : 'transparent',
                      borderColor: isSelected ? 'var(--accent-primary)' : 'transparent',
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>{agent.name || agent.id}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1" style={{ background: style.bg, color: style.color }}>
                        {style.icon} {style.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-[var(--text-secondary)]">
                      {agent.model && <span className="flex items-center gap-1"><Cpu size={10} /> {agent.model}</span>}
                      {agent.type && <span className="flex items-center gap-1"><Zap size={10} /> {agent.type}</span>}
                    </div>
                    {agent.progress !== undefined && agent.status === 'running' && (
                      <div className="mt-1.5 h-1 rounded-full overflow-hidden" style={{ background: 'var(--bg-input)' }}>
                        <div className="h-full rounded-full transition-all" style={{ width: `${agent.progress}%`, background: 'var(--accent-primary)' }} />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="flex-1 overflow-auto p-4">
          {activeAgent ? (
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{activeAgent.name || activeAgent.id}</h3>
                  <div className="flex items-center gap-2 mt-1 text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                    <span className="flex items-center gap-1"><Eye size={10} /> ID: {activeAgent.id}</span>
                    {activeAgent.model && <span className="flex items-center gap-1"><Cpu size={10} /> {activeAgent.model}</span>}
                    {activeAgent.type && <span className="flex items-center gap-1"><Zap size={10} /> {activeAgent.type}</span>}
                  </div>
                </div>
                <span className="text-[10px] px-2 py-1 rounded flex items-center gap-1" style={{ background: STATUS_STYLES[activeAgent.status].bg, color: STATUS_STYLES[activeAgent.status].color }}>
                  {STATUS_STYLES[activeAgent.status].icon} {STATUS_STYLES[activeAgent.status].label}
                </span>
              </div>

              {/* Progress */}
              {activeAgent.progress !== undefined && (
                <div className="p-3 rounded-lg border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Progress</span>
                    <span className="text-xs" style={{ color: 'var(--accent-primary)' }}>{activeAgent.progress}%</span>
                  </div>
                  <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-input)' }}>
                    <div className="h-full rounded-full transition-all" style={{ width: `${activeAgent.progress}%`, background: 'var(--accent-primary)' }} />
                  </div>
                </div>
              )}

              {/* Timeline */}
              <div className="grid grid-cols-2 gap-3">
                {activeAgent.start_time && (
                  <div className="p-3 rounded-lg border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
                    <div className="flex items-center gap-1.5 text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>
                      <Clock size={10} /> Started
                    </div>
                    <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{new Date(activeAgent.start_time).toLocaleString()}</p>
                  </div>
                )}
                {activeAgent.last_activity && (
                  <div className="p-3 rounded-lg border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
                    <div className="flex items-center gap-1.5 text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>
                      <Activity size={10} /> Last Activity
                    </div>
                    <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{new Date(activeAgent.last_activity).toLocaleString()}</p>
                  </div>
                )}
                {activeAgent.task_count !== undefined && (
                  <div className="p-3 rounded-lg border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
                    <div className="flex items-center gap-1.5 text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>
                      <Terminal size={10} /> Tasks
                    </div>
                    <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{activeAgent.task_count}</p>
                  </div>
                )}
              </div>

              {/* Metadata */}
              {activeAgent.metadata && Object.keys(activeAgent.metadata).length > 0 && (
                <div className="p-3 rounded-lg border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
                  <h4 className="text-xs font-medium mb-2" style={{ color: 'var(--text-primary)' }}>Metadata</h4>
                  <pre className="text-[11px] p-2 rounded overflow-auto" style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                    {JSON.stringify(activeAgent.metadata, null, 2)}
                  </pre>
                </div>
              )}

              {/* Logs */}
              {activeAgent.logs && activeAgent.logs.length > 0 && (
                <div className="p-3 rounded-lg border" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}>
                  <h4 className="text-xs font-medium mb-2 flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
                    <Terminal size={14} /> Agent Logs
                  </h4>
                  <div className="space-y-1 max-h-64 overflow-auto">
                    {activeAgent.logs.map((log, i) => (
                      <div key={i} className="text-[11px] font-mono px-2 py-1 rounded" style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)' }}>
                        <span className="opacity-50 mr-2">{i + 1}</span>{log}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-3">
              <Bot size={40} opacity={0.3} />
              <p className="text-sm">Select an agent to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
