'use client';

import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/Spinner';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface AIChatPanelProps {
  topicId: string;
  courseId: string;
  onClose: () => void;
}

export function AIChatPanel({ topicId, courseId, onClose }: AIChatPanelProps) {
  const user = useAuthStore((s) => s.user);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load existing conversation history for this topic on mount
  useEffect(() => {
    async function loadHistory() {
      setLoadingHistory(true);
      try {
        const convRes = await api.ai.getConversations(courseId, topicId);
        const convs: Array<{ id: string; title: string | null; created_at: string }> = convRes.data || [];
        if (convs.length > 0) {
          const latest = convs[0];
          const msgRes = await api.ai.getConversation(latest.id);
          const msgs: Array<{ role: string; content: string; created_at: string }> = msgRes.data || [];
          setConversationId(latest.id);
          setMessages(
            msgs.map((m, i) => ({
              id: `history-${i}`,
              role: m.role as 'user' | 'assistant',
              content: m.content,
            }))
          );
        }
      } catch {
        // No history or fetch failed — start fresh
      } finally {
        setLoadingHistory(false);
        inputRef.current?.focus();
      }
    }
    loadHistory();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId, courseId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.ai.askQuestion(courseId, {
        question: text,
        topic_id: topicId,
        conversation_id: conversationId,
      });
      const { answer, conversation_id } = res.data;
      setConversationId(conversation_id);
      setMessages((prev) => [
        ...prev,
        { id: `ai-${Date.now()}`, role: 'assistant', content: answer },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: 'assistant', content: 'Something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function clearHistory() {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    try {
      await api.ai.deleteConversation(conversationId);
    } catch { /* best-effort */ }
    setConversationId(undefined);
    setMessages([]);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  return (
    <>
      {/* Backdrop — mobile only */}
      <div
        className="fixed inset-0 z-40 md:hidden bg-black/20"
        onClick={onClose}
      />

      <div className={`
        fixed z-50 bg-white border-[#dedad4] flex flex-col shadow-xl
        bottom-0 left-0 right-0 h-[80vh] border-t rounded-t-2xl
        md:top-0 md:bottom-0 md:left-auto md:right-0 md:h-full md:w-[38%] md:border-t-0 md:border-l md:rounded-none md:overflow-hidden
        animate-slide-up md:animate-slide-in-right
      `}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#dedad4] shrink-0">
          <div className="absolute top-2 left-1/2 -translate-x-1/2 h-1 w-10 bg-[#dedad4] rounded-full md:hidden" />
          <h2 className="text-sm font-semibold text-[#1a1917]">Ask AI</h2>
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={clearHistory}
                className="text-xs text-[#9e9a94] hover:text-[#dc2626] transition-colors px-2 py-1 rounded-lg hover:bg-[#f0eeea]"
              >
                Clear history
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[#f0eeea] transition-colors text-[#6b6762]"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {loadingHistory ? (
            <div className="flex justify-center mt-8"><Spinner size="sm" /></div>
          ) : (
            <>
              {messages.length === 0 && (
                <p className="text-sm text-[#9e9a94] text-center mt-8">Ask anything about this topic</p>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`flex gap-2 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  {m.role === 'assistant' ? (
                    <div className="h-7 w-7 rounded-full bg-[#1a1917] text-white flex items-center justify-center text-xs font-bold shrink-0">AI</div>
                  ) : (
                    <Avatar name={user?.full_name} size="sm" />
                  )}
                  <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                    m.role === 'user'
                      ? 'bg-[#1a1917] text-white rounded-tr-sm'
                      : 'bg-[#f0eeea] text-[#1a1917] rounded-tl-sm'
                  }`}>
                    {m.role === 'assistant' ? (
                      <MarkdownRenderer content={m.content} className="text-sm" />
                    ) : m.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex gap-2">
                  <div className="h-7 w-7 rounded-full bg-[#1a1917] text-white flex items-center justify-center text-xs font-bold shrink-0">AI</div>
                  <div className="bg-[#f0eeea] rounded-2xl rounded-tl-sm px-3 py-2"><Spinner size="sm" /></div>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-[#dedad4] px-4 py-3 shrink-0">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question…"
              rows={1}
              className="flex-1 resize-none bg-[#f0eeea] border border-[#dedad4] rounded-xl px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917] max-h-32 overflow-y-auto"
              style={{ minHeight: '40px' }}
            />
            <button
              onClick={send}
              disabled={!input.trim() || loading}
              className="h-10 w-10 rounded-xl bg-[#1a1917] text-white flex items-center justify-center disabled:opacity-40 hover:opacity-90 transition-opacity shrink-0"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M13 8H3M13 8l-4-4M13 8l-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
