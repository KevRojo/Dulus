import React, { useState } from 'react';
import { Lightbulb, MessageSquare, Play, Loader2 } from 'lucide-react';
import { Persona } from '../types.ts';
import { cn } from '../utils.ts';

export const BrainstormView: React.FC = () => {
  const [topic, setTopic] = useState('Should we rewrite the backend in Rust?');
  const [isDebating, setIsDebating] = useState(false);

  const personas: Persona[] = [
    { id: 'p1', name: 'Skeptical PM', role: 'Product', avatar: 'ðŸ‘”', currentArgument: 'Rust is great, but it will delay our roadmap by 6 months. We need to ship features, not rewrite working code.' },
    { id: 'p2', name: 'Principal Eng', role: 'Architecture', avatar: 'ðŸ§™â€â™‚ï¸', currentArgument: 'The current Node.js monolith is hitting memory limits. Rust gives us predictable latency and safety. It pays off in year 2.' },
    { id: 'p3', name: 'Grumpy DBA', role: 'Database', avatar: 'ðŸ—„ï¸', currentArgument: 'I don\'t care what language you use as long as you stop writing N+1 queries. But Rust\'s ORMs are still immature compared to Prisma.' },
    { id: 'p4', name: 'Hot-take Intern', role: 'Junior', avatar: 'ðŸš€', currentArgument: 'Why not Go? Or Zig? Rust compile times are going to ruin my flow state.' },
  ];

  return (
    <div className="flex flex-col h-full w-full p-6 overflow-hidden">
      <div className="mb-6 flex-shrink-0">
        <h2 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Lightbulb className="w-8 h-8 mr-3 text-dulus-accent" />
          Council of Ghosts
        </h2>
        <p className="text-dulus-muted">Multi-persona AI debate. Fabricate experts and let them argue.</p>
      </div>

      <div className="glass-panel rounded-2xl p-4 mb-6 flex-shrink-0 flex gap-3 items-center shadow-lg">
        <input 
          type="text" 
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="flex-1 glass-input rounded-xl px-4 py-3 text-sm"
          placeholder="Enter a topic to debate..."
        />
        <button 
          onClick={() => setIsDebating(!isDebating)}
          className="px-6 py-3 bg-dulus-accent hover:bg-amber-500 text-black font-bold rounded-xl flex items-center transition-colors shadow-[0_0_15px_rgba(251,191,36,0.4)]"
        >
          {isDebating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Debating...</> : <><Play className="w-4 h-4 mr-2" /> Start Debate</>}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-2 gap-4 pb-4">
        {personas.map((p, idx) => (
          <div key={p.id} className="glass-panel rounded-2xl p-5 flex flex-col relative">
            <div className="flex items-center mb-4">
              <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center text-xl mr-3 border border-white/5">
                {p.avatar}
              </div>
              <div>
                <h3 className="text-white font-bold text-sm">{p.name}</h3>
                <span className="text-xs text-dulus-accent uppercase tracking-wider">{p.role}</span>
              </div>
            </div>
            
            <div className="bg-black/40 rounded-xl p-4 flex-1 border border-white/5 relative">
              <MessageSquare className="absolute top-3 right-3 w-4 h-4 text-white/10" />
              <p className="text-sm text-slate-300 leading-relaxed italic">
                "{p.currentArgument}"
              </p>
            </div>
          </div>
        ))}
      </div>
      
      {/* Consensus Area */}
      <div className="mt-4 glass-panel rounded-2xl p-5 border-dulus-accent/30 flex-shrink-0">
        <h4 className="text-sm font-bold text-dulus-accent uppercase tracking-wider mb-2">Distilled Consensus (Round 3)</h4>
        <p className="text-sm text-slate-200">
          The council agrees that a full rewrite is too risky. The compromise is to extract the high-compute microservices (image processing, heavy math) into Rust via FFI or separate services, while keeping the business logic in the current stack until ORM maturity improves.
        </p>
      </div>
    </div>
  );
};

