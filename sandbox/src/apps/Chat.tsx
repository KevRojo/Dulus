// ============================================================
// Chat — Dulus AI Chat (connects to real /chat backend)
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, Sparkles, Trash2, Copy, CheckCircle2, Loader2, Terminal, Wand2 } from 'lucide-react';
import { useSkillBridge, useMemoryBridge, type SkillInjectPayload, type MemoryInjectPayload } from '@/hooks/useSkillBridge';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  streaming?: boolean;
  error?: boolean;
}

const DULUS_CHAT_URL = '/chat';

async function* streamDulus(url: string, body: object): AsyncGenerator<string> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) {
    yield `[error] HTTP ${resp.status}`;
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const obj = JSON.parse(line.slice(6));
        if (obj.type === 'text' && obj.text) yield obj.text;
        if (obj.type === 'error' && obj.message) yield `[error] ${obj.message}`;
      } catch { /* skip */ }
    }
  }
}

function useDulusChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '¡Wepa! Soy Dulus, tu asistente coding. ¿En qué puedo ayudarte?',
      timestamp: Date.now(),
    },
  ]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const checkBackend = useCallback(async () => {
    try {
      const r = await fetch('/api/health', { signal: AbortSignal.timeout(2000) });
      setBackendAvailable(r.ok);
    } catch {
      setBackendAvailable(false);
    }
  }, []);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text.trim(),
      timestamp: Date.now(),
    };
    const assistantMsg: ChatMessage = {
      id: `a-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      streaming: true,
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    try {
      let fullText = '';
      for await (const chunk of streamDulus(DULUS_CHAT_URL, { message: text.trim(), stream: true })) {
        if (chunk.startsWith('[error]')) {
          fullText += chunk;
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsg.id ? { ...m, content: fullText, streaming: false, error: true } : m))
          );
        } else {
          fullText += chunk;
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsg.id ? { ...m, content: fullText } : m))
          );
        }
      }
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantMsg.id ? { ...m, streaming: false } : m))
      );
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: 'Error connecting to Dulus backend. Is the server running?', streaming: false, error: true }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: '¡Wepa! Soy Dulus, tu asistente coding. ¿En qué puedo ayudarte?',
        timestamp: Date.now(),
      },
    ]);
  }, []);

  return { messages, isStreaming, backendAvailable, sendMessage, clearChat, checkBackend };
}

interface ChatProps {
  windowId?: string;
}

export default function Chat({ windowId }: ChatProps) {
  const { messages, isStreaming, backendAvailable, sendMessage, clearChat, checkBackend } = useDulusChat();
  const [input, setInput] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [injectedSkill, setInjectedSkill] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Listen for skill injection events
  useSkillBridge(useCallback((payload: SkillInjectPayload) => {
    const skillText = `/${payload.skillName}`;
    setInjectedSkill(skillText);
    // Auto-send the skill as a message
    sendMessage(`Execute skill: ${payload.skillName}`);
  }, [sendMessage]));

  // Listen for memory injection events — push the .md content as a user message
  useMemoryBridge(useCallback((payload: MemoryInjectPayload) => {
    setInjectedSkill(`memory:${payload.name}`);
    sendMessage(`Para contexto, te paso esta memoria "${payload.name}":\n\n${payload.content}`);
  }, [sendMessage]));

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    const text = input;
    setInput('');
    await sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const copyToClipboard = async (content: string, id: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch { /* ignore */ }
  };

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-window)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent-primary)15' }}>
            <Sparkles size={16} style={{ color: 'var(--accent-primary)' }} />
          </div>
          <div>
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Dulus Chat</h2>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${backendAvailable === true ? 'bg-[var(--accent-success)]' : backendAvailable === false ? 'bg-[var(--accent-error)]' : 'bg-[var(--text-secondary)] animate-pulse'}`} />
              <span className="text-[10px] text-[var(--text-secondary)]">
                {backendAvailable === true ? 'Connected' : backendAvailable === false ? 'Offline' : 'Checking...'}
              </span>
              {injectedSkill && (
                <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ml-2" style={{ background: 'var(--accent-secondary)20', color: 'var(--accent-secondary)' }}>
                  <Wand2 size={10} />
                  Skill: {injectedSkill}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={checkBackend} className="p-1.5 rounded-lg" style={{ color: 'var(--text-secondary)' }} title="Check connection">
            <Loader2 size={14} />
          </button>
          <button onClick={clearChat} className="p-1.5 rounded-lg" style={{ color: 'var(--text-secondary)' }} title="Clear chat">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5" style={{
              background: msg.role === 'assistant' ? 'var(--accent-primary)15' : 'var(--accent-secondary)15',
            }}>
              {msg.role === 'assistant' ? <Bot size={14} style={{ color: 'var(--accent-primary)' }} /> : <User size={14} style={{ color: 'var(--accent-secondary)' }} />}
            </div>

            {/* Bubble */}
            <div className={`max-w-[80%] group ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className="px-3.5 py-2.5 rounded-2xl text-xs leading-relaxed"
                style={{
                  background: msg.role === 'assistant' ? 'var(--bg-hover)' : 'var(--accent-primary)',
                  color: msg.role === 'assistant' ? 'var(--text-primary)' : 'white',
                  borderBottomLeftRadius: msg.role === 'assistant' ? 4 : undefined,
                  borderBottomRightRadius: msg.role === 'user' ? 4 : undefined,
                  border: msg.role === 'assistant' ? '1px solid var(--border-default)' : 'none',
                }}
              >
                {msg.error ? (
                  <span className="text-[var(--accent-error)]">{msg.content}</span>
                ) : (
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                )}
                {msg.streaming && (
                  <span className="inline-block w-1.5 h-3 ml-0.5 bg-current animate-pulse" style={{ opacity: 0.5 }} />
                )}
              </div>

              {/* Actions */}
              <div className={`flex items-center gap-2 mt-1 opacity-0 group-hover:opacity-100 transition-opacity ${msg.role === 'user' ? 'justify-end' : ''}`}>
                <span className="text-[10px] text-[var(--text-secondary)]">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                {msg.role === 'assistant' && !msg.streaming && (
                  <button
                    onClick={() => copyToClipboard(msg.content, msg.id)}
                    className="p-0.5 rounded"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {copiedId === msg.id ? <CheckCircle2 size={10} style={{ color: 'var(--accent-success)' }} /> : <Copy size={10} />}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border-default)' }}>
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Dulus anything... (Shift+Enter for new line)"
              rows={1}
              disabled={isStreaming}
              className="w-full px-3 py-2.5 pr-10 rounded-xl text-xs outline-none resize-none max-h-32"
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-primary)',
              }}
            />
            <span className="absolute right-3 bottom-2.5 text-[10px] text-[var(--text-secondary)] opacity-50">
              {input.length}
            </span>
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="p-2.5 rounded-xl text-white transition-all hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
            style={{ background: 'var(--accent-primary)' }}
          >
            {isStreaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
        <div className="flex items-center justify-between mt-1.5 px-1">
          <span className="text-[10px] text-[var(--text-secondary)]">Powered by Dulus Agent</span>
          <span className="text-[10px] text-[var(--text-secondary)]">Press Enter to send</span>
        </div>
      </div>
    </div>
  );
}
