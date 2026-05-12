// ============================================================
// useDulusChat — Streaming chat hook for Dulus Agent
// ============================================================

import { useState, useCallback, useRef } from 'react';
import { streamChat, type ChatMessage } from '@/lib/dulus-api';

export interface UseDulusChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  clearChat: () => void;
}

export function useDulusChat(systemPrompt?: string): UseDulusChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>(
    systemPrompt ? [{ role: 'system', content: systemPrompt }] : []
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      abortRef.current = false;
      setError(null);

      const userMsg: ChatMessage = { role: 'user', content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);

      const conversation: ChatMessage[] =
        systemPrompt
          ? [{ role: 'system', content: systemPrompt }, ...messages.slice(messages[0].role === 'system' ? 1 : 0), userMsg]
          : [...messages, userMsg];

      let assistantText = '';
      try {
        for await (const chunk of streamChat(conversation)) {
          if (abortRef.current) break;
          if (chunk.startsWith('[error]')) {
            setError(chunk.replace('[error]', '').trim());
            break;
          }
          assistantText += chunk;
          setMessages((prev) => {
            const withoutPending = prev.filter((m) => m.role !== 'assistant' || m.content !== '...');
            return [...withoutPending, { role: 'assistant', content: assistantText }];
          });
        }
        if (!assistantText && !error) {
          setMessages((prev) => [...prev, { role: 'assistant', content: '...' }]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsStreaming(false);
      }
    },
    [messages, systemPrompt, error]
  );

  const clearChat = useCallback(() => {
    abortRef.current = true;
    setMessages(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []);
    setError(null);
    setIsStreaming(false);
  }, [systemPrompt]);

  return { messages, isStreaming, error, sendMessage, clearChat };
}
