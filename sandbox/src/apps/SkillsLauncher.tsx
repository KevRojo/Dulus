// ============================================================
// Skills Launcher — Dulus Native App (Hook-based)
// ============================================================

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Wand2, Search, Play, Star, Clock, Zap, Shield, Code,
  GitBranch, MessageSquare, FileSearch, Bug, Terminal,
  RefreshCw, AlertCircle, CheckCircle2, XCircle, Loader2,
  MessageCircle,
  type LucideIcon,
} from 'lucide-react';
import { useDulusSkills } from '@/hooks/useDulusSkills';
import { emitSkillInject, shouldSendToChat } from '@/hooks/useSkillBridge';
import type { SkillInfo } from '@/lib/dulus-api';

interface SkillView extends SkillInfo {
  icon: React.ReactNode;
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  System: Terminal,
  Dev: Code,
  Review: FileSearch,
  Chat: MessageSquare,
  Utility: Zap,
};

const CATEGORY_COLORS: Record<string, { color: string; bg: string }> = {
  System: { color: 'var(--accent-primary)', bg: 'var(--accent-primary)15' },
  Dev: { color: 'var(--accent-success)', bg: 'var(--accent-success)15' },
  Review: { color: 'var(--accent-secondary)', bg: 'var(--accent-secondary)15' },
  Chat: { color: 'var(--accent-warning)', bg: 'var(--accent-warning)15' },
  Utility: { color: 'var(--text-secondary)', bg: 'var(--text-secondary)15' },
};

function enrichSkill(skill: SkillInfo): SkillView {
  const Icon = CATEGORY_ICONS[skill.category || 'Utility'] || Zap;
  return { ...skill, icon: <Icon size={16} /> };
}

export default function SkillsLauncher() {
  const { skills: apiSkills, isLoading, error, refresh, invoke } = useDulusSkills();
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [runningId, setRunningId] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<{ id: string; success: boolean; message: string } | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());

  // Load favorites from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('dulus_skills_favorites');
    if (saved) {
      try { setFavorites(new Set(JSON.parse(saved))); } catch { /* ignore */ }
    }
  }, []);

  const skills = useMemo(() => {
    const enriched = apiSkills.map(enrichSkill);
    const saved = localStorage.getItem('dulus_skills_lastUsed');
    if (!saved) return enriched;
    try {
      const parsed = JSON.parse(saved) as Record<string, string>;
      return enriched.map((s) => (parsed[s.name || ''] ? { ...s, lastUsed: parsed[s.name || ''] } : s));
    } catch { return enriched; }
  }, [apiSkills]);

  const toggleFavorite = (id: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      localStorage.setItem('dulus_skills_favorites', JSON.stringify([...next]));
      return next;
    });
  };

  const runSkill = useCallback(async (skill: SkillView, sendToChat = false) => {
    setRunningId(skill.id || skill.name);
    setLastResult(null);

    // If sendToChat is true or skill is Chat category, emit injection event
    const autoSend = sendToChat || shouldSendToChat(skill.name, skill.category);
    if (autoSend) {
      emitSkillInject(skill.name, { description: skill.description, category: skill.category });
      setLastResult({ id: skill.id || skill.name, success: true, message: `Sent "${skill.name}" to Chat 💬` });
      setRunningId(null);
      // Still track usage
      const now = new Date().toISOString();
      const saved = localStorage.getItem('dulus_skills_lastUsed');
      const parsed = saved ? JSON.parse(saved) : {};
      parsed[skill.name] = now;
      localStorage.setItem('dulus_skills_lastUsed', JSON.stringify(parsed));
      return;
    }

    const result = await invoke(skill.name, {});

    if (result !== null && typeof result === 'object' && 'success' in result) {
      const res = result as { success: boolean; result?: string; skill?: string; error?: string };
      if (res.success && res.result) {
        const preview = res.result.length > 120 ? res.result.slice(0, 120) + '...' : res.result;
        setLastResult({ id: skill.id || skill.name, success: true, message: preview });
      } else if (res.error) {
        setLastResult({ id: skill.id || skill.name, success: false, message: res.error });
      } else {
        setLastResult({ id: skill.id || skill.name, success: true, message: `Skill "${skill.name}" executed` });
      }
    } else if (result !== null) {
      const preview = String(result).length > 120 ? String(result).slice(0, 120) + '...' : String(result);
      setLastResult({ id: skill.id || skill.name, success: true, message: preview });
    } else {
      setLastResult({ id: skill.id || skill.name, success: false, message: `Skill "${skill.name}" failed` });
    }

    setRunningId(null);
    const now = new Date().toISOString();
    const saved = localStorage.getItem('dulus_skills_lastUsed');
    const parsed = saved ? JSON.parse(saved) : {};
    parsed[skill.name] = now;
    localStorage.setItem('dulus_skills_lastUsed', JSON.stringify(parsed));
  }, [invoke]);

  const categories = useMemo(
    () => ['all', ...Array.from(new Set(skills.map((s) => s.category || 'Utility')))],
    [skills]
  );

  const filtered = skills.filter((s) => {
    const matchesCat = selectedCategory === 'all' || (s.category || 'Utility') === selectedCategory;
    const q = search.toLowerCase();
    const matchesSearch = !q || s.name.toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q);
    return matchesCat && matchesSearch;
  });

  const favoriteSkills = filtered.filter((s) => favorites.has(s.id || s.name));
  const regularSkills = filtered.filter((s) => !favorites.has(s.id || s.name));

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-3">
          <Wand2 size={18} style={{ color: 'var(--accent-secondary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Skills Launcher</h2>
          <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
            {skills.length} skills
          </span>
          {isLoading && <Loader2 size={14} className="animate-spin text-[var(--text-secondary)]" />}
          {error && <span className="text-[10px] text-[var(--accent-error)]" title={error}>Error</span>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refresh()} className="p-1.5 rounded-md hover:bg-[var(--bg-hover)]" title="Refresh">
            <RefreshCw size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search skills..."
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', width: 200 }}
            />
          </div>
        </div>
      </div>

      {/* Category filter */}
      <div className="flex gap-1 px-4 py-2 border-b" style={{ borderColor: 'var(--border-default)' }}>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className="px-3 py-1 rounded-md text-[11px] font-medium capitalize transition-colors"
            style={{
              background: selectedCategory === cat ? 'var(--accent-primary)' : 'var(--bg-hover)',
              color: selectedCategory === cat ? 'white' : 'var(--text-secondary)',
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Result toast */}
      {lastResult && (
        <div className={`px-4 py-2 border-b flex items-center gap-2 text-xs ${lastResult.success ? 'text-[var(--accent-success)]' : 'text-[var(--accent-error)]'}`} style={{ borderColor: 'var(--border-default)', background: lastResult.success ? 'var(--accent-success)08' : 'var(--accent-error)08' }}>
          {lastResult.success ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          {lastResult.message}
          <button onClick={() => setLastResult(null)} className="ml-auto"><XCircle size={12} /></button>
        </div>
      )}

      {/* Skills grid */}
      <div className="flex-1 overflow-auto p-4">
        {isLoading && skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-2">
            <Loader2 size={24} className="animate-spin" />
            <p className="text-xs">Loading skills...</p>
          </div>
        ) : skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-2">
            <Wand2 size={32} opacity={0.4} />
            <p className="text-sm font-medium">No skills found</p>
            <p className="text-xs opacity-70">Add skills to ~/.dulus/skills to see them here</p>
          </div>
        ) : (
          <>
            {favoriteSkills.length > 0 && (
              <>
                <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                  <Star size={12} /> Favorites
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mb-4">
                  {favoriteSkills.map((skill) => (
                    <SkillCard key={skill.id || skill.name} skill={skill} isFavorite={true} isRunning={runningId === (skill.id || skill.name)} onRun={() => runSkill(skill)} onSendToChat={() => runSkill(skill, true)} onToggleFav={() => toggleFavorite(skill.id || skill.name)} />
                  ))}
                </div>
              </>
            )}

            {regularSkills.length > 0 && (
              <>
                {favoriteSkills.length > 0 && (
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                    <Zap size={12} /> All Skills
                  </h3>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {regularSkills.map((skill) => (
                    <SkillCard key={skill.id || skill.name} skill={skill} isFavorite={false} isRunning={runningId === (skill.id || skill.name)} onRun={() => runSkill(skill)} onSendToChat={() => runSkill(skill, true)} onToggleFav={() => toggleFavorite(skill.id || skill.name)} />
                  ))}
                </div>
              </>
            )}

            {filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)] gap-2">
                <Search size={24} />
                <p className="text-xs">No skills match your search</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function SkillCard({ skill, isFavorite, isRunning, onRun, onSendToChat, onToggleFav }: {
  skill: SkillView;
  isFavorite: boolean;
  isRunning: boolean;
  onRun: () => void;
  onSendToChat: () => void;
  onToggleFav: () => void;
}) {
  const catStyle = CATEGORY_COLORS[skill.category || 'Utility'] || CATEGORY_COLORS.Utility;

  return (
    <div
      className="group relative p-3 rounded-xl border transition-all hover:shadow-md"
      style={{ background: 'var(--bg-hover)', borderColor: 'var(--border-default)' }}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: catStyle.bg, color: catStyle.color }}>
            {skill.icon}
          </div>
          <div>
            <h4 className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{skill.name}</h4>
            <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: catStyle.bg, color: catStyle.color }}>{skill.category || 'Utility'}</span>
          </div>
        </div>
        <button onClick={onToggleFav} className="p-1 rounded transition-colors" style={{ color: isFavorite ? 'var(--accent-warning)' : 'var(--text-secondary)' }}>
          <Star size={14} fill={isFavorite ? 'currentColor' : 'none'} />
        </button>
      </div>

      <p className="text-[11px] mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{skill.description}</p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] text-[var(--text-secondary)]">
          {skill.hotkey && <span className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-input)' }}>{skill.hotkey}</span>}
          {skill.lastUsed && (
            <span className="flex items-center gap-1">
              <Clock size={10} /> {new Date(skill.lastUsed).toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={onSendToChat}
            disabled={isRunning}
            className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-medium transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ background: 'var(--accent-secondary)20', color: 'var(--accent-secondary)' }}
            title="Send to Chat"
          >
            <MessageCircle size={12} />
            Chat
          </button>
          <button
            onClick={onRun}
            disabled={isRunning}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ background: 'var(--accent-primary)' }}
          >
            {isRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {isRunning ? 'Running...' : 'Run'}
          </button>
        </div>
      </div>
    </div>
  );
}
