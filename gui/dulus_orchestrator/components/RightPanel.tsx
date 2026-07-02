import React, { useState } from 'react';
import { FilePlus2, Files, Puzzle, Sparkles, TextCursorInput } from 'lucide-react';
import { AppState } from '../types.ts';
import { cn } from '../utils.ts';

interface RightPanelProps {
  state: AppState;
  setState: React.Dispatch<React.SetStateAction<AppState>>;
}

const compactPath = (path: string) => {
  const parts = path.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) return path;
  return parts.slice(-2).join('/');
};

export const RightPanel: React.FC<RightPanelProps> = ({ state, setState }) => {
  const [activeTab, setActiveTab] = useState<'plugins' | 'skills' | 'context'>('plugins');
  const [draftContext, setDraftContext] = useState('');
  const plugins = state.pluginsByProfile[state.profile] || [];
  const skills = state.skillsByProfile[state.profile] || [];

  const togglePlugin = async (pluginId: string, enabled: boolean) => {
    setState(prev => ({
      ...prev,
      pluginsByProfile: {
        ...prev.pluginsByProfile,
        [prev.profile]: (prev.pluginsByProfile[prev.profile] || []).map(plugin =>
          plugin.id === pluginId ? { ...plugin, enabled } : plugin
        ),
      },
    }));

    try {
      await window.pywebview?.api?.set_plugin_enabled?.(state.profile, pluginId, enabled);
    } catch {
      setState(prev => ({
        ...prev,
        pluginsByProfile: {
          ...prev.pluginsByProfile,
          [prev.profile]: (prev.pluginsByProfile[prev.profile] || []).map(plugin =>
            plugin.id === pluginId ? { ...plugin, enabled: !enabled } : plugin
          ),
        },
      }));
    }
  };

  const addTextContext = () => {
    const text = draftContext.trim();
    if (!text) return;
    setState(prev => ({
      ...prev,
      contextItems: [
        ...prev.contextItems,
        {
          id: `text-${Date.now()}`,
          name: text.slice(0, 42) || 'Session note',
          kind: 'text',
          text,
        },
      ],
    }));
    setDraftContext('');
  };

  const addFiles = (files: FileList | null) => {
    if (!files?.length) return;
    const items = Array.from(files).map(file => ({
      id: `file-${file.name}-${Date.now()}`,
      name: file.name,
      kind: 'file' as const,
      source: 'session upload',
    }));
    setState(prev => ({ ...prev, contextItems: [...prev.contextItems, ...items] }));
  };

  if (!state.rightPanelOpen) return null;

  return (
    <div className="w-80 h-full glass-panel border-l-dulus-border flex flex-col flex-shrink-0 z-20">
      <div className="flex border-b border-dulus-border">
        {[
          { id: 'plugins', icon: Puzzle, label: 'Plugins' },
          { id: 'skills', icon: Sparkles, label: 'Skills' },
          { id: 'context', icon: Files, label: 'Context' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              "flex-1 py-3 flex justify-center items-center border-b-2 transition-colors",
              activeTab === tab.id 
                ? "border-dulus-accent text-dulus-accent bg-white/5" 
                : "border-transparent text-dulus-muted hover:text-white hover:bg-white/5"
            )}
            title={tab.label}
          >
            <tab.icon className="w-4 h-4" />
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {activeTab === 'plugins' && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="flex justify-between items-center">
              <label className="text-xs font-semibold text-dulus-muted uppercase tracking-wider">Active Plugins</label>
              <span className="text-[10px] text-dulus-accent font-mono">{state.profile}</span>
            </div>
            
            <div className="space-y-2">
              {plugins.length ? plugins.map(plugin => (
                <div key={plugin.id} className="bg-black/30 border border-white/5 rounded-lg p-3 flex items-center justify-between group hover:border-white/10 transition-colors">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-slate-200 truncate">{plugin.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-slate-400 uppercase">{plugin.type}</span>
                    </div>
                    <p className="text-xs text-dulus-muted truncate mt-1" title={plugin.source}>{compactPath(plugin.source)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => togglePlugin(plugin.id, !plugin.enabled)}
                    className="ml-3"
                    title={plugin.enabled ? `Disable ${plugin.name}` : `Enable ${plugin.name}`}
                  >
                    <div className={cn("w-8 h-4 rounded-full relative transition-colors", plugin.enabled ? "bg-dulus-accent" : "bg-zinc-700")}>
                      <div className={cn("absolute top-0.5 w-3 h-3 rounded-full bg-black transition-transform", plugin.enabled ? "left-4" : "left-0.5")}></div>
                    </div>
                  </button>
                </div>
              )) : (
                <div className="bg-black/30 border border-white/5 rounded-lg p-3 text-sm text-dulus-muted">
                  No plugins found for this profile yet.
                </div>
              )}
            </div>
            
            <div className="mt-4 p-3 bg-amber-900/20 border border-amber-500/20 rounded-lg">
              <p className="text-xs text-amber-200">
                <strong>Auto-Adapter</strong> follows the selected profile. Repos/tools added here should land under that profile.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="flex justify-between items-center">
              <label className="text-xs font-semibold text-dulus-muted uppercase tracking-wider">Profile Skills</label>
              <span className="text-[10px] text-dulus-accent font-mono">{skills.length}</span>
            </div>

            <div className="space-y-2">
              {skills.length ? skills.map(skill => (
                <div key={skill.id} className="bg-black/30 border border-white/5 rounded-lg p-3 group hover:border-white/10 transition-colors">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-slate-200 truncate">{skill.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-400/10 text-emerald-200 uppercase">on</span>
                  </div>
                  <p className="text-xs text-dulus-muted truncate mt-1" title={skill.source}>{compactPath(skill.source)}</p>
                </div>
              )) : (
                <div className="bg-black/30 border border-white/5 rounded-lg p-3 text-sm text-dulus-muted">
                  No skills found for this profile yet.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'context' && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="flex justify-between items-center">
              <label className="text-xs font-semibold text-dulus-muted uppercase tracking-wider">Session Context</label>
              <span className="text-[10px] text-dulus-accent font-mono">{state.contextItems.length}</span>
            </div>

            <div className="space-y-2">
              {state.contextItems.length ? state.contextItems.map(item => (
                <div key={item.id} className="bg-black/30 border border-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    {item.kind === 'file' ? <FilePlus2 className="w-3.5 h-3.5 text-dulus-accent" /> : <TextCursorInput className="w-3.5 h-3.5 text-dulus-accent" />}
                    <span className="text-sm font-medium text-slate-200 truncate">{item.name}</span>
                  </div>
                  <p className="text-xs text-dulus-muted truncate mt-1" title={item.source || item.text}>{item.source ? compactPath(item.source) : item.text}</p>
                </div>
              )) : (
                <div className="bg-black/30 border border-white/5 rounded-lg p-3 text-sm text-dulus-muted">
                  Nothing attached to this session.
                </div>
              )}
            </div>

            <textarea
              value={draftContext}
              onChange={(e) => setDraftContext(e.target.value)}
              className="w-full glass-input rounded-lg p-3 text-sm min-h-24 resize-none"
              placeholder="Add context text for this session..."
            />

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={addTextContext}
                className="px-3 py-2 rounded-lg bg-dulus-accent/15 border border-dulus-accent/30 text-dulus-accent text-xs hover:bg-dulus-accent/25 transition-colors"
              >
                Add Text
              </button>
              <label className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 text-xs text-center hover:bg-white/10 transition-colors cursor-pointer">
                Add Files
                <input
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    addFiles(e.target.files);
                    e.currentTarget.value = '';
                  }}
                />
              </label>
            </div>

            <div className="bg-black/30 border border-white/5 rounded-lg p-3">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-semibold text-dulus-muted uppercase tracking-wider">Permissions</span>
                <span className="text-[10px] text-dulus-accent font-mono">{state.permissionMode}</span>
              </div>
              {['auto', 'accept-all', 'manual', 'plan'].map(mode => (
                <label key={mode} className="flex items-center space-x-2 cursor-pointer group py-1">
                  <input
                    type="radio"
                    name="permission"
                    value={mode}
                    checked={state.permissionMode === mode}
                    onChange={() => setState(s => ({ ...s, permissionMode: mode as AppState['permissionMode'] }))}
                    className="text-dulus-accent focus:ring-dulus-accent bg-black/50 border-white/20"
                  />
                  <span className={cn(
                    "text-sm capitalize transition-colors",
                    state.permissionMode === mode ? "text-white font-medium" : "text-dulus-muted group-hover:text-slate-300"
                  )}>
                    {mode}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

