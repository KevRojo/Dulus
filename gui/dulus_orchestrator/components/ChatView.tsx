import React, { useState, useRef, useEffect } from 'react';
import {
  Send, Paperclip, X, Loader2, TerminalSquare, History, ChevronRight, Mic, Download,
  Wrench, ChevronDown, Check, Copy, Brain, ShieldAlert, HelpCircle,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';
import { AppState, ChatMessage, MessageBlock, WebchatSession, GuiQuestionOption } from '../types.ts';
import { fileToBase64, cn } from '../utils.ts';

interface ChatViewProps {
  state: AppState;
  setState: React.Dispatch<React.SetStateAction<AppState>>;
  selectedSession?: WebchatSession | null;
}

const compactPath = (path: string) => {
  const parts = path.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) return path;
  return parts.slice(-2).join('/');
};

const modelLabel = (model: string, state: AppState) => {
  const provider = state.modelProviders[model] || (model === state.model ? state.modelProvider : '');
  return provider ? `${model} (${provider})` : model;
};

const messageText = (content: WebchatSession['messages'][number]['content']) => {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.find(item => item.type === 'text')?.text || '';
  }
  return '';
};

const webchatBase = (state: AppState) => (state.webchatUrl || '').replace(/\/$/, '');

// ─── Markdown with GFM + syntax highlighting + copy buttons ─────────────────
const CodePre: React.FC<React.HTMLAttributes<HTMLPreElement>> = ({ children, ...props }) => {
  const preRef = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const code = preRef.current?.querySelector('code')?.textContent || '';
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  };

  return (
    <div className="relative group/code">
      <button
        type="button"
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-md bg-white/5 border border-white/10 text-slate-400 opacity-0 group-hover/code:opacity-100 hover:text-white hover:bg-white/10 transition-all z-10"
        title={copied ? 'Copied!' : 'Copy code'}
      >
        {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
      <pre ref={preRef} {...props}>{children}</pre>
    </div>
  );
};

const Markdown: React.FC<{ children: string }> = ({ children }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    rehypePlugins={[[rehypeHighlight, { ignoreMissing: true }]]}
    components={{ pre: CodePre }}
  >
    {children}
  </ReactMarkdown>
);

// ─── Collapsible thinking block ──────────────────────────────────────────────
const ThinkingBlock: React.FC<{ text: string }> = ({ text }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="my-2 rounded-lg border border-purple-500/20 bg-purple-500/5 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-purple-300/80 hover:bg-purple-500/10 transition-colors"
      >
        <Brain className="w-3.5 h-3.5" />
        <span className="font-mono">Thinking</span>
        <ChevronDown className={cn('w-3 h-3 ml-auto transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="px-3 pb-2 text-xs text-purple-200/70 whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">
          {text}
        </div>
      )}
    </div>
  );
};

// ─── Tool pill (collapsible, shows args + result) ────────────────────────────
const ToolPill: React.FC<{ block: Extract<MessageBlock, { kind: 'tool' }> }> = ({ block }) => {
  const [open, setOpen] = useState(false);
  const running = block.status === 'running';
  return (
    <div className={cn(
      'my-2 rounded-lg border overflow-hidden text-xs',
      running ? 'border-amber-500/30 bg-amber-500/5' : 'border-white/10 bg-black/40'
    )}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-white/5 transition-colors"
      >
        {running
          ? <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
          : block.permitted === false
            ? <X className="w-3.5 h-3.5 text-red-400" />
            : <Check className="w-3.5 h-3.5 text-green-400" />}
        <Wrench className="w-3 h-3 text-slate-400" />
        <span className="font-mono text-slate-300">{block.name}</span>
        <span className="text-slate-500 ml-1">{running ? 'running…' : block.permitted === false ? 'denied' : 'done'}</span>
        <ChevronDown className={cn('w-3 h-3 ml-auto text-slate-500 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-1.5 border-t border-white/5 pt-2">
          {block.args != null && (
            <div>
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-0.5">Input</div>
              <pre className="bg-black/60 rounded p-2 overflow-x-auto text-slate-300 max-h-32 overflow-y-auto">
                {typeof block.args === 'string' ? block.args : JSON.stringify(block.args, null, 2)}
              </pre>
            </div>
          )}
          {block.result != null && (
            <div>
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-0.5">Result</div>
              <pre className="bg-black/60 rounded p-2 overflow-x-auto text-slate-300 max-h-40 overflow-y-auto whitespace-pre-wrap">
                {String(block.result).slice(0, 4000)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── Permission banner ───────────────────────────────────────────────────────
const PermissionBanner: React.FC<{
  block: Extract<MessageBlock, { kind: 'permission' }>;
  onAnswer: (permId: string, granted: boolean) => void;
}> = ({ block, onAnswer }) => {
  if (block.answered) {
    return (
      <div className="my-2 px-3 py-1.5 rounded-lg border border-white/10 bg-black/30 text-xs text-slate-400 flex items-center gap-2">
        {block.granted ? <Check className="w-3.5 h-3.5 text-green-400" /> : <X className="w-3.5 h-3.5 text-red-400" />}
        Permission {block.granted ? 'granted' : 'denied'}: {block.description}
      </div>
    );
  }
  return (
    <div className="my-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2.5 flex items-center gap-3" role="alertdialog">
      <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" />
      <span className="text-sm text-amber-100 flex-1">{block.description}</span>
      <div className="flex gap-2 shrink-0">
        <button
          type="button"
          onClick={() => onAnswer(block.permId, false)}
          className="px-3 py-1 rounded-md border border-white/20 text-xs text-slate-300 hover:bg-white/10 transition-colors"
        >
          Deny
        </button>
        <button
          type="button"
          onClick={() => onAnswer(block.permId, true)}
          className="px-3 py-1 rounded-md bg-amber-500/80 text-xs text-black font-semibold hover:bg-amber-400 transition-colors"
        >
          Allow
        </button>
      </div>
    </div>
  );
};

// ─── Question banner (AskUserQuestion) ───────────────────────────────────────
const QuestionBanner: React.FC<{
  block: Extract<MessageBlock, { kind: 'question' }>;
  onAnswer: (questionId: string, answer: string) => void;
}> = ({ block, onAnswer }) => {
  const [freetext, setFreetext] = useState('');
  if (block.answer) {
    return (
      <div className="my-2 px-3 py-1.5 rounded-lg border border-white/10 bg-black/30 text-xs text-slate-400 flex items-center gap-2">
        <Check className="w-3.5 h-3.5 text-green-400" /> {block.answer}
      </div>
    );
  }
  return (
    <div className="my-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2.5" role="alertdialog">
      <div className="flex items-center gap-2 mb-2">
        <HelpCircle className="w-4 h-4 text-sky-400 shrink-0" />
        <span className="text-sm text-sky-100">{block.question}</span>
      </div>
      {block.options?.length > 0 && (
        <div className="flex flex-col gap-1.5 mb-2">
          {block.options.map((opt, i) => {
            const label = typeof opt === 'string' ? opt : (opt as GuiQuestionOption).label || '';
            const desc = typeof opt === 'object' ? (opt as GuiQuestionOption).description : undefined;
            return (
              <button
                key={i}
                type="button"
                onClick={() => onAnswer(block.questionId, label)}
                className="text-left px-3 py-1.5 rounded-md border border-sky-500/30 bg-black/30 hover:bg-sky-500/20 transition-colors"
              >
                <span className="text-sm text-sky-100">{label}</span>
                {desc && <span className="block text-xs text-slate-400 mt-0.5">{desc}</span>}
              </button>
            );
          })}
        </div>
      )}
      {block.allowFreetext !== false && (
        <div className="flex gap-2">
          <input
            type="text"
            value={freetext}
            onChange={e => setFreetext(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && freetext.trim()) onAnswer(block.questionId, freetext.trim()); }}
            placeholder="Or type your answer…"
            className="flex-1 bg-black/40 border border-white/10 rounded-md px-2.5 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500/50"
          />
          <button
            type="button"
            onClick={() => { if (freetext.trim()) onAnswer(block.questionId, freetext.trim()); }}
            className="px-3 py-1 rounded-md bg-sky-500/80 text-xs text-black font-semibold hover:bg-sky-400 transition-colors"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
};

export const ChatView: React.FC<ChatViewProps> = ({ state, setState, selectedSession }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'system',
    text: '> DULUS interface initialized. Type `/help` for commands.'
  }]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [isListening, setIsListening] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const slashCommands = [
    { cmd: '/model', desc: 'Switch model' },
    { cmd: '/ssj', desc: 'Power menu' },
    { cmd: '/brainstorm', desc: 'Council of ghosts' },
    { cmd: '/plugin', desc: 'Manage plugins' },
    { cmd: '/cloudflare_tunnel', desc: 'Toggle Cloudflare tunnel' },
    { cmd: '/checkpoint', desc: 'Rewind state' },
    { cmd: '/memory', desc: 'Search persistent memory' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [input]);

  useEffect(() => {
    if (!selectedSession) return;
    const loadedMessages: ChatMessage[] = (selectedSession.messages || [])
      .map((message, index) => {
        const text = messageText(message.content);
        if (!text) return null;
        return {
          id: `${selectedSession.id}-${index}`,
          role: message.role === 'assistant' ? 'model' : message.role === 'user' ? 'user' : 'system',
          text,
        } as ChatMessage;
      })
      .filter(Boolean) as ChatMessage[];

    setMessages(loadedMessages.length ? loadedMessages : [{
      id: `${selectedSession.id}-empty`,
      role: 'system',
      text: `Loaded chat: ${selectedSession.title || 'Chat'}`
    }]);
  }, [selectedSession?.id]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);
    if (val.startsWith('/') && val.length < 10 && !val.includes(' ')) {
      setShowSlashMenu(true);
    } else {
      setShowSlashMenu(false);
    }
  };

  const handleCommandSelect = (cmd: string, value?: string) => {
    setInput(value ? `${cmd} ${value}` : cmd + ' ');
    if (cmd === '/model' && value) {
      setState(prev => ({ ...prev, model: value, modelProvider: prev.modelProviders[value] || prev.modelProvider }));
    }
    setShowSlashMenu(false);
    inputRef.current?.focus();
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        const base64 = await fileToBase64(file);
        setSelectedImage(base64);
      } catch (error) {
        console.error("Error reading file:", error);
      }
    }
  };

  const handleVoiceInput = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript || '';
      if (transcript) {
        setInput(prev => `${prev}${prev ? ' ' : ''}${transcript}`);
      }
    };
    recognition.start();
  };

  const exportMarkdown = () => {
    const title = selectedSession?.title || 'dulus-chat';
    const body = messages.map(message => {
      const role = message.role === 'model' ? 'DULUS' : message.role.toUpperCase();
      return `## ${role}\n\n${message.text}`;
    }).join('\n\n');
    const blob = new Blob([`# ${title}\n\n${body}\n`], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${title.replace(/[^\w.-]+/g, '-').slice(0, 64) || 'dulus-chat'}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // ─── Block helpers ─────────────────────────────────────────────────────────
  const updateMsg = (msgId: string, updater: (msg: ChatMessage) => ChatMessage) => {
    setMessages(prev => prev.map(msg => (msg.id === msgId ? updater(msg) : msg)));
  };

  const appendBlock = (msg: ChatMessage, block: MessageBlock): ChatMessage => ({
    ...msg,
    blocks: [...(msg.blocks || []), block],
  });

  /** Append text to the last block if it matches `kind`, otherwise push a new block. */
  const mergeText = (msg: ChatMessage, kind: 'text' | 'thinking', text: string): ChatMessage => {
    const blocks = [...(msg.blocks || [])];
    const last = blocks[blocks.length - 1];
    if (last && last.kind === kind) {
      blocks[blocks.length - 1] = { ...last, text: (last as any).text + text } as MessageBlock;
    } else {
      blocks.push({ kind, text } as MessageBlock);
    }
    return { ...msg, blocks, text: kind === 'text' ? msg.text + text : msg.text };
  };

  const answerPermission = (msgId: string) => async (permId: string, granted: boolean) => {
    updateMsg(msgId, msg => ({
      ...msg,
      blocks: (msg.blocks || []).map(b =>
        b.kind === 'permission' && b.permId === permId ? { ...b, answered: true, granted } : b
      ),
    }));
    try {
      await fetch(`${webchatBase(state)}/permission`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: permId, granted }),
      });
    } catch (error) {
      console.error('Permission answer failed:', error);
    }
  };

  const answerQuestion = (msgId: string) => async (questionId: string, answer: string) => {
    updateMsg(msgId, msg => ({
      ...msg,
      blocks: (msg.blocks || []).map(b =>
        b.kind === 'question' && b.questionId === questionId ? { ...b, answer } : b
      ),
    }));
    try {
      await fetch(`${webchatBase(state)}/question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: questionId, answer }),
      });
    } catch (error) {
      console.error('Question answer failed:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && !selectedImage) || isGenerating) return;

    const userMsgId = Date.now().toString();
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      text: input,
      imageUrl: selectedImage || undefined,
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setSelectedImage(null);
    setShowSlashMenu(false);

    // Handle local slash commands visually
    if (currentInput.startsWith('/')) {
      const [cmd, value] = currentInput.split(/\s+/);
      if (cmd === '/model' && value) {
        setState(prev => ({ ...prev, model: value, modelProvider: prev.modelProviders[value] || prev.modelProvider }));
        setMessages(prev => [...prev, {
          id: Date.now().toString() + 'sys',
          role: 'system',
          text: `Model switched locally to \`${value}\`.`
        }]);
      } else {
        const nativeEvents = await window.pywebview?.api?.send_gui_message?.(currentInput);
        const text = nativeEvents
          ?.map(event => event.text || event.message || '')
          .filter(Boolean)
          .join('')
          .trim();
        setMessages(prev => [...prev, {
          id: Date.now().toString() + 'sys',
          role: 'system',
          text: text || `Executed backend command: \`${cmd}\`.`
        }]);
      }
      return;
    }

    setIsGenerating(true);
    const modelMsgId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: modelMsgId, role: 'model', text: '', blocks: [], isStreaming: true }]);

    // Full SSE event handling — mirrors webchat_ui/app.js handleStreamEvent()
    const applyEvent = (event: Record<string, any>) => {
      switch (event.type) {
        case 'text':
          updateMsg(modelMsgId, msg => mergeText(msg, 'text', event.text || ''));
          break;
        case 'thinking':
          updateMsg(modelMsgId, msg => mergeText(msg, 'thinking', event.text || ''));
          break;
        case 'tool_start':
          updateMsg(modelMsgId, msg => appendBlock(msg, {
            kind: 'tool',
            toolId: `${event.name || 'tool'}-${Date.now()}-${(msg.blocks || []).length}`,
            name: event.name || 'tool',
            args: event.inputs,
            status: 'running',
          }));
          break;
        case 'tool_end':
          updateMsg(modelMsgId, msg => {
            const blocks = [...(msg.blocks || [])];
            // Find last running tool block with matching name (or last running block).
            for (let i = blocks.length - 1; i >= 0; i--) {
              const b = blocks[i];
              if (b.kind === 'tool' && b.status === 'running' && (!event.name || b.name === event.name)) {
                blocks[i] = { ...b, status: 'done', result: event.result, permitted: event.permitted };
                return { ...msg, blocks };
              }
            }
            return msg;
          });
          break;
        case 'permission':
          updateMsg(modelMsgId, msg => appendBlock(msg, {
            kind: 'permission',
            permId: event.id,
            description: event.description || 'Permission required',
          }));
          break;
        case 'question':
          updateMsg(modelMsgId, msg => appendBlock(msg, {
            kind: 'question',
            questionId: event.id,
            question: event.question || '',
            options: event.options || [],
            allowFreetext: event.allow_freetext !== false,
          }));
          break;
        case 'turn_done':
          updateMsg(modelMsgId, msg => ({
            ...msg,
            isStreaming: false,
            stats: { in: event.in, out: event.out, cacheRead: event.cache_read, cacheWrite: event.cache_write },
          }));
          break;
        case 'error':
          updateMsg(modelMsgId, msg => mergeText(msg, 'text', `\n\n[error] ${event.message || 'Unknown error'}`));
          break;
      }
    };

    const streamDirectly = async () => {
      const resp = await fetch(`${webchatBase(state)}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: currentInput }),
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            applyEvent(JSON.parse(line.slice(6)));
          } catch {
            continue;
          }
        }
      }
    };

    try {
      // Prefer REAL incremental streaming through the webchat server (chunk by
      // chunk). The pywebview bridge is batch-only (all events arrive at once,
      // after the whole turn), so it's only used as a fallback.
      if (state.webchatUrl) {
        try {
          await streamDirectly();
        } catch (streamError) {
          const nativeEvents = await window.pywebview?.api?.send_gui_message?.(currentInput);
          if (nativeEvents) {
            nativeEvents.forEach(applyEvent);
          } else {
            throw streamError;
          }
        }
      } else {
        const nativeEvents = await window.pywebview?.api?.send_gui_message?.(currentInput);
        if (nativeEvents) {
          nativeEvents.forEach(applyEvent);
        } else {
          await streamDirectly();
        }
      }
      fetch(`${webchatBase(state)}/api/sessions/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: selectedSession?.id || 'default' }),
      }).catch(() => {});
    } catch (error) {
      console.error("Chat error:", error);
      updateMsg(modelMsgId, msg => mergeText(msg, 'text', `Connection error: ${(error as Error).message}`));
    } finally {
      updateMsg(modelMsgId, msg => ({ ...msg, isStreaming: false }));
      setIsGenerating(false);
    }
  };

  const renderBlocks = (msg: ChatMessage) => {
    if (!msg.blocks?.length) {
      return <Markdown>{msg.text}</Markdown>;
    }
    return (
      <>
        {msg.blocks.map((block, i) => {
          switch (block.kind) {
            case 'text':
              return <Markdown key={i}>{block.text}</Markdown>;
            case 'thinking':
              return <ThinkingBlock key={i} text={block.text} />;
            case 'tool':
              return <ToolPill key={block.toolId} block={block} />;
            case 'permission':
              return <PermissionBanner key={block.permId} block={block} onAnswer={answerPermission(msg.id)} />;
            case 'question':
              return <QuestionBanner key={block.questionId} block={block} onAnswer={answerQuestion(msg.id)} />;
            default:
              return null;
          }
        })}
      </>
    );
  };

  return (
    <div className="flex flex-col h-full w-full relative">
      {/* Top Bar */}
      <div className="h-12 border-b border-dulus-border flex items-center px-4 justify-between bg-dulus-panel/50 backdrop-blur-md z-10">
        <div className="flex items-center space-x-2 text-sm text-slate-300">
          <TerminalSquare className="w-4 h-4 text-dulus-accent" />
          <span className="font-mono truncate max-w-[18vw]" title={state.workspace}>{compactPath(state.workspace)}</span>
          <ChevronRight className="w-4 h-4 text-slate-600" />
          <span className="text-dulus-accent font-mono text-xs border border-dulus-accent/30 bg-dulus-accent/10 px-2 py-0.5 rounded">main</span>
          {selectedSession && (
            <>
              <ChevronRight className="w-4 h-4 text-slate-600" />
              <span className="font-mono truncate max-w-[16vw]" title={selectedSession.title}>{selectedSession.title}</span>
            </>
          )}
        </div>
        <div className="hidden lg:grid grid-cols-3 gap-2 w-[42vw] max-w-2xl mx-4">
          <label className="sr-only" htmlFor="top-model">Model</label>
          <select
            id="top-model"
            className="glass-input rounded-md px-2 py-1.5 text-xs font-mono"
            value={state.model}
            onChange={(e) => setState(prev => ({ ...prev, model: e.target.value, modelProvider: prev.modelProviders[e.target.value] || prev.modelProvider }))}
            title="Active model"
          >
            {state.models.map(model => (
              <option key={model} value={model}>
                {modelLabel(model, state)}
              </option>
            ))}
          </select>

          <label className="sr-only" htmlFor="top-workspace">Workspace</label>
          <select
            id="top-workspace"
            className="glass-input rounded-md px-2 py-1.5 text-xs font-mono"
            value={state.workspace}
            onChange={(e) => setState(prev => ({ ...prev, workspace: e.target.value }))}
            title="Workspace"
          >
            {state.workspaces.map(workspace => (
              <option key={workspace} value={workspace}>{compactPath(workspace)}</option>
            ))}
          </select>

          <label className="sr-only" htmlFor="top-profile">Profile</label>
          <select
            id="top-profile"
            className="glass-input rounded-md px-2 py-1.5 text-xs font-mono"
            value={state.profile}
            onChange={(e) => setState(prev => ({ ...prev, profile: e.target.value }))}
            title="Profile"
          >
            {state.profiles.map(profile => (
              <option key={profile} value={profile}>{profile}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center space-x-3">
          <button className="text-xs flex items-center text-slate-400 hover:text-white transition-colors">
            <History className="w-3 h-3 mr-1" /> Checkpoints
          </button>
          <button
            onClick={exportMarkdown}
            className="text-xs flex items-center text-slate-400 hover:text-white transition-colors"
            title="Export chat"
          >
            <Download className="w-3 h-3 mr-1" /> Export
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className={cn("flex", msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            <div className={cn(
              "max-w-[85%] md:max-w-[75%] rounded-2xl p-4 shadow-lg",
              msg.role === 'user' ? 'bg-dulus-primary/40 border border-dulus-primary/50 text-white rounded-tr-sm' :
              msg.role === 'system' ? 'bg-black/60 border border-white/10 text-slate-400 font-mono text-sm w-full max-w-full rounded-lg' :
              'bg-dulus-surface/80 border border-white/10 text-slate-200 rounded-tl-sm backdrop-blur-sm'
            )}>
              {msg.role === 'model' && (
                <div className="flex items-center mb-2 text-dulus-accent text-xs font-bold tracking-widest uppercase">
                  DULUS
                  {msg.stats && (
                    <span className="ml-auto font-mono text-[10px] text-slate-500 normal-case tracking-normal font-normal">
                      ↑{msg.stats.in ?? 0} ↓{msg.stats.out ?? 0}
                      {(msg.stats.cacheRead ?? 0) > 0 && ` ⚡${msg.stats.cacheRead}`}
                    </span>
                  )}
                </div>
              )}

              {msg.imageUrl && (
                <img src={msg.imageUrl} alt="Uploaded" className="max-w-md w-full h-auto rounded-lg mb-3 border border-white/10" />
              )}

              <div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-black/80 prose-pre:border prose-pre:border-white/10 prose-pre:shadow-inner">
                {msg.isStreaming && !msg.text && !msg.blocks?.length ? (
                  <div className="flex items-center space-x-2 text-dulus-accent">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm font-mono">Synthesizing...</span>
                  </div>
                ) : (
                  renderBlocks(msg)
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-gradient-to-t from-dulus-bg via-dulus-bg to-transparent">
        <div className="max-w-4xl mx-auto relative">

          {/* Slash Command Menu */}
          {showSlashMenu && (
            <div className="absolute bottom-full left-0 mb-2 w-64 bg-dulus-panel border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-2">
              <div className="px-3 py-2 bg-black/60 border-b border-white/5 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Commands
              </div>
              <div className="max-h-48 overflow-y-auto p-1">
                {input.trim() === '/model' ? state.models.map(model => (
                  <button
                    key={model}
                    onClick={() => handleCommandSelect('/model', model)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-dulus-primary/40 hover:text-white text-slate-300 flex items-center justify-between group transition-colors"
                  >
                    <span className="font-mono text-sm text-dulus-accent group-hover:text-white">{modelLabel(model, state)}</span>
                    <span className="text-xs text-slate-500 group-hover:text-slate-300">{model === state.model ? 'active' : 'switch'}</span>
                  </button>
                )) : slashCommands.map(cmd => (
                  <button
                    key={cmd.cmd}
                    onClick={() => handleCommandSelect(cmd.cmd)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-dulus-primary/40 hover:text-white text-slate-300 flex items-center justify-between group transition-colors"
                  >
                    <span className="font-mono text-sm text-dulus-accent group-hover:text-white">{cmd.cmd}</span>
                    <span className="text-xs text-slate-500 group-hover:text-slate-300">{cmd.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {selectedImage && (
            <div className="absolute bottom-full left-0 mb-2 p-2 bg-dulus-panel border border-white/10 rounded-xl flex items-start shadow-xl">
              <img src={selectedImage} alt="Preview" className="h-16 w-16 object-cover rounded-lg" />
              <button
                onClick={() => setSelectedImage(null)}
                className="ml-2 p-1 bg-black/50 rounded-full hover:bg-red-500/50 transition-colors text-white"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="relative flex items-end glass-panel rounded-2xl p-1 shadow-2xl focus-within:ring-1 focus-within:ring-dulus-accent/50 transition-all">
            <div className="flex flex-col gap-1 pb-1 pl-1">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-2.5 rounded-xl text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
                title="Attach Image"
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImageUpload}
                accept="image/*"
                className="hidden"
              />
              <button
                type="button"
                onClick={handleVoiceInput}
                className={cn(
                  "p-2.5 rounded-xl transition-colors",
                  isListening ? "text-dulus-accent bg-dulus-accent/10" : "text-slate-400 hover:bg-white/10 hover:text-white"
                )}
                title="Voice input"
              >
                <Mic className="w-5 h-5" />
              </button>
            </div>

            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Type / for commands, or chat with Dulus..."
              className="flex-1 bg-transparent border-0 focus:ring-0 text-white placeholder-slate-500 resize-none py-3.5 px-3 max-h-40 min-h-[52px] font-sans"
              rows={1}
            />

            <button
              type="submit"
              disabled={(!input.trim() && !selectedImage) || isGenerating}
              className="p-3 m-1 bg-gradient-to-br from-zinc-800 to-black border border-zinc-700 hover:border-dulus-accent text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(251,191,36,0.15)]"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
          <div className="text-center mt-2 text-[10px] text-slate-500 font-mono">
            Dulus Orchestrator - Press Enter to send
          </div>
        </div>
      </div>
    </div>
  );
};
