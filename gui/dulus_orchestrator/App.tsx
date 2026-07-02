import React, { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar.tsx';
import { RightPanel } from './components/RightPanel.tsx';
import { ChatView } from './components/ChatView.tsx';
import { RoundTableView } from './components/RoundTableView.tsx';
import { AgentsView } from './components/AgentsView.tsx';
import { BrainstormView } from './components/BrainstormView.tsx';
import { VoiceView } from './components/VoiceView.tsx';
import { VisionView } from './components/VisionView.tsx';
import { CoreView } from './components/CoreView.tsx';
import { CosmicBackground } from './components/CosmicBackground.tsx';
import { AppState, GuiQuestion, RuntimeState, ViewMode, WebchatSession } from './types.ts';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';

const readRuntime = (): RuntimeState => {
  const params = new URLSearchParams(window.location.search);
  const workspace = params.get('workspace') || 'workspace1';
  const runtime = window.__DULUS_RUNTIME__;

  return {
    workspace: runtime?.workspace || workspace,
    workspaces: runtime?.workspaces?.length ? runtime.workspaces : [workspace],
    profile: runtime?.profile || 'default',
    profiles: runtime?.profiles?.length ? runtime.profiles : [runtime?.profile || 'default'],
    model: runtime?.model || 'gemini-2.5-flash',
    modelProvider: runtime?.modelProvider || 'auto',
    models: runtime?.models?.length ? runtime.models : ['gemini-2.5-flash', 'grok-4'],
    modelProviders: runtime?.modelProviders || {},
    permissionMode: runtime?.permissionMode || 'auto',
    plugins: runtime?.plugins || {},
    skills: runtime?.skills || {},
    contextItems: runtime?.contextItems || [],
    webchatUrl: runtime?.webchatUrl || 'http://127.0.0.1:5000',
  };
};

const App: React.FC = () => {
  const runtime = readRuntime();
  const [state, setState] = useState<AppState>({
    currentView: 'chat',
    model: runtime.model,
    modelProvider: runtime.modelProvider,
    models: runtime.models,
    modelProviders: runtime.modelProviders || {},
    workspace: runtime.workspace,
    workspaces: runtime.workspaces,
    profile: runtime.profile,
    profiles: runtime.profiles,
    permissionMode: runtime.permissionMode || 'auto',
    isSSJMode: false,
    rightPanelOpen: true,
    pluginsByProfile: runtime.plugins,
    skillsByProfile: runtime.skills,
    contextItems: runtime.contextItems,
    webchatUrl: runtime.webchatUrl,
  });
  const [pendingQuestion, setPendingQuestion] = useState<GuiQuestion | null>(null);
  const [freeTextAnswer, setFreeTextAnswer] = useState('');
  const [selectedSession, setSelectedSession] = useState<WebchatSession | null>(null);

  useEffect(() => {
    let cancelled = false;
    const pollQuestion = async () => {
      const api = window.pywebview?.api;
      if (!api?.get_pending_question) return;
      try {
        const question = await api.get_pending_question();
        if (!cancelled) {
          setPendingQuestion(question || null);
        }
      } catch {
        if (!cancelled) setPendingQuestion(null);
      }
    };

    pollQuestion();
    const timer = window.setInterval(pollQuestion, 1200);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const answerPendingQuestion = async (answer: string) => {
    if (!pendingQuestion) return;
    const api = window.pywebview?.api;
    if (api?.answer_question) {
      await api.answer_question(pendingQuestion.id, answer);
    }
    setPendingQuestion(null);
    setFreeTextAnswer('');
  };

  const renderView = () => {
    switch (state.currentView) {
      case 'chat': return <ChatView state={state} setState={setState} selectedSession={selectedSession} />;
      case 'core': return <CoreView state={state} />;
      case 'roundtable': return <RoundTableView />;
      case 'agents': return <AgentsView />;
      case 'brainstorm': return <BrainstormView />;
      case 'voice': return <VoiceView />;
      case 'vision': return <VisionView />;
      default: return <ChatView state={state} setState={setState} selectedSession={selectedSession} />;
    }
  };

  return (
    <div className="flex h-screen w-full bg-transparent text-slate-200 overflow-hidden font-sans">
      <CosmicBackground />
      <Sidebar
        currentView={state.currentView}
        webchatUrl={state.webchatUrl}
        activeSessionId={selectedSession?.id || null}
        onSessionSelect={(session) => {
          setSelectedSession(session);
          setState(s => ({ ...s, currentView: 'chat' }));
        }}
        onViewChange={(v) => setState(s => ({ ...s, currentView: v }))}
      />
      
      <main className="flex-1 relative h-full overflow-hidden flex flex-col bg-black/40 backdrop-blur-sm">
        {/* Top subtle gradient */}
        <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-black/80 to-transparent pointer-events-none z-0"></div>
        
        <div className="relative z-10 flex-1 h-full overflow-hidden flex">
          <div className="flex-1 h-full overflow-hidden relative">
            {renderView()}
            
            {/* Toggle Right Panel Button */}
            <button 
              onClick={() => setState(s => ({ ...s, rightPanelOpen: !s.rightPanelOpen }))}
              className="absolute top-3 right-4 z-50 p-2 bg-black/50 hover:bg-white/10 rounded-lg border border-white/10 text-slate-400 hover:text-white transition-colors backdrop-blur-md"
              title="Toggle Control Panel"
            >
              {state.rightPanelOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
            </button>
          </div>
          
          <RightPanel state={state} setState={setState} />
        </div>
      </main>

      {pendingQuestion && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-lg glass-panel rounded-2xl p-5 shadow-2xl border-dulus-accent/30">
            <div className="text-[10px] uppercase tracking-[0.22em] text-dulus-accent font-semibold mb-3">
              Dulus needs your input
            </div>
            <h3 className="text-xl font-bold text-white leading-snug">{pendingQuestion.question}</h3>

            {pendingQuestion.options.length > 0 && (
              <div className="mt-5 space-y-2">
                {pendingQuestion.options.map((option) => (
                  <button
                    key={option.label}
                    onClick={() => answerPendingQuestion(option.label)}
                    className="w-full text-left rounded-xl border border-white/10 bg-black/40 hover:border-dulus-accent/60 hover:bg-dulus-accent/10 px-4 py-3 transition-colors"
                  >
                    <div className="text-sm font-semibold text-white">{option.label}</div>
                    {option.description && (
                      <div className="text-xs text-dulus-muted mt-1">{option.description}</div>
                    )}
                  </button>
                ))}
              </div>
            )}

            {pendingQuestion.allow_freetext && (
              <div className="mt-4 flex gap-2">
                <input
                  value={freeTextAnswer}
                  onChange={(e) => setFreeTextAnswer(e.target.value)}
                  className="flex-1 glass-input rounded-lg px-3 py-2 text-sm"
                  placeholder="Type custom answer..."
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && freeTextAnswer.trim()) {
                      answerPendingQuestion(freeTextAnswer.trim());
                    }
                  }}
                />
                <button
                  onClick={() => freeTextAnswer.trim() && answerPendingQuestion(freeTextAnswer.trim())}
                  className="px-4 py-2 rounded-lg bg-dulus-accent text-black text-sm font-semibold hover:bg-amber-300 transition-colors"
                >
                  Send
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default App;

