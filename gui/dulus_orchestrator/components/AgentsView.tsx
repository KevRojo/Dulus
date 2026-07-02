import React from 'react';
import { GitBranch, Play, CheckCircle2, AlertCircle, Clock, TerminalSquare } from 'lucide-react';
import { SubAgent } from '../types.ts';
import { cn } from '../utils.ts';

export const AgentsView: React.FC = () => {
  const agents: SubAgent[] = [
    { id: 'ag-1', type: 'coder', task: 'Refactor auth module to use JWT', status: 'working', branch: 'feature/auth-refactor' },
    { id: 'ag-2', type: 'reviewer', task: 'Review PR #042 for security flaws', status: 'idle', branch: 'main' },
    { id: 'ag-3', type: 'tester', task: 'Run e2e tests on auth endpoints', status: 'done', branch: 'feature/auth-refactor' },
  ];

  const getStatusIcon = (status: string) => {
    switch(status) {
      case 'working': return <div className="w-4 h-4 rounded-full border-2 border-dulus-accent border-t-transparent animate-spin"></div>;
      case 'done': return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-red-400" />;
      default: return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <div className="flex flex-col h-full w-full p-6 overflow-y-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white mb-2 flex items-center">
          <GitBranch className="w-8 h-8 mr-3 text-dulus-accent" />
          Sub-Agents Flock
        </h2>
        <p className="text-dulus-muted">Isolated git worktrees running parallel tasks.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {agents.map(agent => (
          <div key={agent.id} className="glass-panel rounded-2xl p-5 flex flex-col relative overflow-hidden group hover:border-dulus-accent/50 transition-colors">
            {agent.status === 'working' && (
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-dulus-accent to-transparent animate-pulse"></div>
            )}
            
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-1 rounded-md bg-white/10 text-xs font-bold uppercase tracking-wider text-slate-200">
                  {agent.type}
                </span>
                <span className="text-xs font-mono text-slate-500">{agent.id}</span>
              </div>
              {getStatusIcon(agent.status)}
            </div>

            <p className="text-sm text-white mb-4 flex-1">{agent.task}</p>

            <div className="bg-black/60 rounded-lg p-3 mt-auto border border-white/5">
              <div className="flex items-center text-xs text-slate-400 font-mono mb-2">
                <GitBranch className="w-3 h-3 mr-1.5" /> {agent.branch}
              </div>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5">
                <button className="text-xs text-dulus-accent hover:text-amber-300 flex items-center transition-colors">
                  <TerminalSquare className="w-3 h-3 mr-1" /> View Logs
                </button>
                {agent.status === 'idle' && (
                  <button className="text-xs bg-white/10 hover:bg-white/20 text-white px-3 py-1 rounded transition-colors flex items-center">
                    <Play className="w-3 h-3 mr-1" /> Start
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Add New Agent Card */}
        <button className="glass-panel rounded-2xl p-5 flex flex-col items-center justify-center text-dulus-muted hover:text-white hover:border-dulus-accent/50 transition-all border-dashed border-2 border-white/10 min-h-[200px]">
          <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-3 group-hover:bg-white/10 transition-colors">
            <span className="text-2xl">+</span>
          </div>
          <span className="font-medium">Spawn Agent</span>
        </button>
      </div>
    </div>
  );
};

