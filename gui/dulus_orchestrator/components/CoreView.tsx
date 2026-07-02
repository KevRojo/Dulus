import React, { useState } from 'react';
import { Bot, Boxes, Brain, Cable, GitBranch, Network, SendHorizontal, ShieldCheck, Sparkles, Wrench } from 'lucide-react';
import { AppState } from '../types.ts';

interface CoreViewProps {
  state: AppState;
}

const modules = [
  {
    icon: GitBranch,
    title: 'Repo Intake',
    status: 'Ready',
    text: 'Detects project shape, stack, entrypoints, tests, and risky legacy zones before touching code.',
  },
  {
    icon: Bot,
    title: 'Agent Builder',
    status: 'Next',
    text: 'Turns client requests into role-specific agents with tools, memory scope, and operating rules.',
  },
  {
    icon: Brain,
    title: 'Adaptive Memory',
    status: 'Active',
    text: 'Keeps project facts, user preferences, decisions, and reusable patterns available across sessions.',
  },
  {
    icon: Wrench,
    title: 'AutoAdapter',
    status: 'Core',
    text: 'Learns new repo conventions and proposes bridges instead of forcing one fixed workflow.',
  },
  {
    icon: Cable,
    title: 'Connector Layer',
    status: 'Planned',
    text: 'Maps external APIs, CLIs, MCP tools, webhooks, and local scripts into safe Dulus tools.',
  },
  {
    icon: ShieldCheck,
    title: 'Guard Rails',
    status: 'Active',
    text: 'Separates inspect, edit, run, and deploy paths so client work stays controlled.',
  },
];

const pipeline = [
  'Scan workspace',
  'Infer repo contract',
  'Create/assign agents',
  'Patch and verify',
  'Store durable lessons',
];

const compactPath = (path: string) => {
  const parts = path.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) return path;
  return parts.slice(-2).join('/');
};

const buildAdaptationPrompt = (topic: string, state: AppState) => `Investigate "${topic}" for Dulus auto-adaptation.

Current workspace: ${state.workspace}
Active profile: ${state.profile}
Active model: ${state.model}${state.modelProvider ? ` (${state.modelProvider})` : ''}

Goal:
Research what this request needs, then propose concrete Dulus adaptations.

Return:
1. What the user likely wants.
2. Repos, files, APIs, CLIs, MCPs, plugins, or skills Dulus should inspect.
3. Agents Dulus should create or assign.
4. Context files/text that should be attached for this session.
5. AutoAdapter changes or connectors that would make this repeatable.
6. Risks, permissions needed, and the safest next action.`;

export const CoreView: React.FC<CoreViewProps> = ({ state }) => {
  const [topic, setTopic] = useState('');
  const [lastPrompt, setLastPrompt] = useState('');
  const [status, setStatus] = useState<'idle' | 'sent' | 'local'>('idle');

  const submitIntake = async (event: React.FormEvent) => {
    event.preventDefault();
    const cleanTopic = topic.trim();
    if (!cleanTopic) return;
    const prompt = buildAdaptationPrompt(cleanTopic, state);
    setLastPrompt(prompt);

    const api = window.pywebview?.api;
    if (api?.submit_core_intake) {
      await api.submit_core_intake(cleanTopic, prompt, state.workspace, state.profile, state.model);
      setStatus('sent');
    } else {
      setStatus('local');
    }
    setTopic('');
  };

  return (
    <div className="h-full overflow-y-auto p-6 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-4">
          <div>
            <div className="flex items-center text-dulus-accent text-xs uppercase tracking-[0.24em] font-bold mb-3">
              <Sparkles className="w-4 h-4 mr-2" />
              Core Adaptation Layer
            </div>
            <h2 className="text-3xl md:text-4xl font-bold text-white tracking-wide">Dulus Core</h2>
            <p className="text-dulus-muted mt-3 max-w-3xl">
              The center of Dulus is not a fixed dashboard. It is the system that studies a repo,
              creates the right agents, wires tools, and adapts itself to what the client actually asked for.
            </p>
          </div>

          <div className="glass-panel rounded-2xl px-4 py-3 min-w-0 xl:w-[420px]">
            <div className="text-[10px] uppercase tracking-[0.2em] text-dulus-muted mb-1">Current Workspace</div>
            <div className="font-mono text-sm text-white truncate" title={state.workspace}>{compactPath(state.workspace)}</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-5">
          <section className="glass-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="font-bold text-white text-lg">Adaptation Pipeline</h3>
                <p className="text-sm text-dulus-muted">From unknown repo to useful specialized agents.</p>
              </div>
              <Network className="w-6 h-6 text-dulus-accent" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {pipeline.map((step, index) => (
                <div key={step} className="relative rounded-xl border border-white/10 bg-black/30 p-4 min-h-[104px]">
                  <div className="text-dulus-accent font-mono text-xs mb-3">0{index + 1}</div>
                  <div className="text-sm font-semibold text-white leading-snug">{step}</div>
                  {index < pipeline.length - 1 && (
                    <div className="hidden md:block absolute top-1/2 -right-2 w-4 h-px bg-dulus-accent/40" />
                  )}
                </div>
              ))}
            </div>

            <form onSubmit={submitIntake} className="mt-5 rounded-2xl border border-dulus-accent/20 bg-black/35 p-4">
              <label className="text-[10px] uppercase tracking-[0.2em] text-dulus-accent font-semibold">
                Auto-adaptation request
              </label>
              <div className="mt-3 flex flex-col md:flex-row gap-3">
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="flex-1 glass-input rounded-xl px-4 py-3 text-sm"
                  placeholder="What do you want?"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-dulus-accent text-black px-4 py-3 text-sm font-bold hover:bg-amber-300 transition-colors"
                >
                  <SendHorizontal className="w-4 h-4" />
                  Adapt
                </button>
              </div>
              {status !== 'idle' && (
                <p className="mt-3 text-xs text-dulus-muted">
                  {status === 'sent'
                    ? 'Prompt queued for Dulus investigation.'
                    : 'Prompt prepared in this GUI session.'}
                </p>
              )}
              {lastPrompt && (
                <details className="mt-3 text-xs text-dulus-muted">
                  <summary className="cursor-pointer text-dulus-accent">Generated prompt</summary>
                  <pre className="mt-2 whitespace-pre-wrap rounded-xl bg-black/40 border border-white/10 p-3 font-mono text-[11px] leading-relaxed">
                    {lastPrompt}
                  </pre>
                </details>
              )}
            </form>
          </section>

          <section className="glass-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-white text-lg">Client Request Intake</h3>
              <Boxes className="w-6 h-6 text-dulus-accent" />
            </div>
            <div className="space-y-3 text-sm">
              <div className="rounded-xl bg-black/30 border border-white/10 p-4">
                <div className="text-dulus-muted mb-1">Primary focus</div>
                <div className="text-white font-semibold">Auto-adapt to repos and build requested agents</div>
              </div>
              <div className="rounded-xl bg-black/30 border border-white/10 p-4">
                <div className="text-dulus-muted mb-1">Default behavior</div>
                <div className="text-white font-semibold">Inspect first, then choose tools, edits, tests, and memory updates</div>
              </div>
            </div>
          </section>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {modules.map((mod) => {
            const Icon = mod.icon;
            return (
              <div key={mod.title} className="glass-panel rounded-2xl p-5 hover:border-dulus-accent/40 transition-colors">
                <div className="flex items-start justify-between">
                  <Icon className="w-7 h-7 text-dulus-accent" />
                  <span className="text-[10px] uppercase tracking-wider text-dulus-accent border border-dulus-accent/30 rounded-full px-2 py-1 bg-dulus-accent/10">
                    {mod.status}
                  </span>
                </div>
                <h4 className="mt-5 text-white font-bold">{mod.title}</h4>
                <p className="mt-2 text-sm leading-relaxed text-dulus-muted">{mod.text}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

