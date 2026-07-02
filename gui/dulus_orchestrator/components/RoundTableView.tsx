import React, { useState } from 'react';
import { Send, Layers, Loader2, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { generateChatStream } from '../services/ai.ts';
import { cn } from '../utils.ts';

const AVAILABLE_MODELS = [
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'Google' },
  { id: 'claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', provider: 'Anthropic' },
  { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI' },
  { id: 'deepseek-r1', name: 'DeepSeek R1', provider: 'DeepSeek' },
  { id: 'qwen-2.5-coder', name: 'Qwen 2.5 Coder', provider: 'Alibaba' },
  { id: 'llama-3.3-70b', name: 'Llama 3.3 70B', provider: 'Meta' }
];

export const RoundTableView: React.FC = () => {
  const [selectedModels, setSelectedModels] = useState<string[]>(['gemini-2.5-flash', 'claude-3.5-sonnet', 'gpt-4o']);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [responses, setResponses] = useState<Record<string, { text: string, isStreaming: boolean }>>({});
  const [hasSearched, setHasSearched] = useState(false);

  const toggleModel = (id: string) => {
    setSelectedModels(prev => {
      if (prev.includes(id)) {
        return prev.filter(m => m !== id);
      } else {
        if (prev.length >= 5) return prev; // Max 5
        return [...prev, id];
      }
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;
    if (selectedModels.length < 3 || selectedModels.length > 5) {
      alert("Please select between 3 and 5 models.");
      return;
    }

    setIsGenerating(true);
    setHasSearched(true);

    const initialResponses: Record<string, { text: string, isStreaming: boolean }> = {};
    selectedModels.forEach(id => {
      initialResponses[id] = { text: '', isStreaming: true };
    });
    setResponses(initialResponses);

    const promises = selectedModels.map(async (modelId) => {
      const modelDef = AVAILABLE_MODELS.find(m => m.id === modelId);
      try {
        // Simulating different models using Gemini with persona prompting
        const stream = await generateChatStream(
          prompt,
          [],
          undefined,
          `You are ${modelDef?.name} by ${modelDef?.provider}. You are participating in a multi-model round table. Provide a concise, expert response to the user's prompt.`
        );

        let fullText = '';
        for await (const chunk of stream) {
          fullText += chunk.text;
          setResponses(prev => ({
            ...prev,
            [modelId]: { text: fullText, isStreaming: true }
          }));
        }
        setResponses(prev => ({
          ...prev,
          [modelId]: { text: fullText, isStreaming: false }
        }));
      } catch (error) {
        setResponses(prev => ({
          ...prev,
          [modelId]: { text: 'Error connecting to model gateway.', isStreaming: false }
        }));
      }
    });

    await Promise.all(promises);
    setIsGenerating(false);
  };

  return (
    <div className="flex flex-col h-full w-full p-6 overflow-hidden">
      <div className="mb-6 flex-shrink-0">
        <h2 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Layers className="w-8 h-8 mr-3 text-dulus-accent" />
          Round Table
        </h2>
        <p className="text-dulus-muted">Query 3 to 5 models simultaneously to compare their insights.</p>
      </div>

      {/* Model Selector */}
      <div className="glass-panel rounded-2xl p-4 mb-6 flex-shrink-0 shadow-lg">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Select Models ({selectedModels.length}/5)</span>
          {selectedModels.length < 3 && <span className="text-xs text-red-400">Select at least 3 models</span>}
        </div>
        <div className="flex flex-wrap gap-2">
          {AVAILABLE_MODELS.map(model => {
            const isSelected = selectedModels.includes(model.id);
            const isDisabled = !isSelected && selectedModels.length >= 5;
            return (
              <button
                key={model.id}
                onClick={() => toggleModel(model.id)}
                disabled={isDisabled}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center border",
                  isSelected 
                    ? "bg-dulus-accent/20 border-dulus-accent text-dulus-accent shadow-[0_0_10px_rgba(251,191,36,0.2)]" 
                    : "bg-black/40 border-white/10 text-slate-400 hover:border-white/30",
                  isDisabled && "opacity-50 cursor-not-allowed"
                )}
              >
                {isSelected && <Check className="w-3 h-3 mr-1.5" />}
                {model.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-2 mb-6 flex-shrink-0 shadow-xl flex items-end focus-within:ring-1 focus-within:ring-dulus-accent/50 transition-all">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder="Ask the Round Table..."
          className="flex-1 bg-transparent border-0 focus:ring-0 text-white placeholder-slate-500 resize-none py-3 px-4 max-h-32 min-h-[52px] font-sans"
          rows={1}
        />
        <button
          type="submit"
          disabled={!prompt.trim() || isGenerating || selectedModels.length < 3}
          className="p-3 m-1 bg-gradient-to-br from-zinc-800 to-black border border-zinc-700 hover:border-dulus-accent text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(251,191,36,0.15)]"
        >
          {isGenerating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </form>

      {/* Results Area */}
      <div className="flex-1 overflow-y-auto pb-4">
        {hasSearched && (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {selectedModels.map(modelId => {
              const modelDef = AVAILABLE_MODELS.find(m => m.id === modelId);
              const response = responses[modelId];
              
              return (
                <div key={modelId} className="glass-panel rounded-2xl flex flex-col overflow-hidden border border-white/10">
                  <div className="bg-black/60 px-4 py-3 border-b border-white/5 flex items-center justify-between">
                    <div className="flex items-center">
                      <div className={cn("w-2 h-2 rounded-full mr-2", response?.isStreaming ? "bg-dulus-accent animate-pulse" : "bg-green-500")}></div>
                      <span className="font-bold text-sm text-white">{modelDef?.name}</span>
                    </div>
                    <span className="text-[10px] uppercase tracking-wider text-slate-500">{modelDef?.provider}</span>
                  </div>
                  <div className="p-4 flex-1 bg-black/20 overflow-y-auto prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-black/80 prose-pre:border prose-pre:border-white/10">
                    {response ? (
                      response.text ? (
                        <ReactMarkdown>{response.text}</ReactMarkdown>
                      ) : (
                        <div className="flex items-center text-dulus-accent/70 text-sm">
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Awaiting response...
                        </div>
                      )
                    ) : (
                      <div className="text-slate-500 text-sm italic">Waiting to start...</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

