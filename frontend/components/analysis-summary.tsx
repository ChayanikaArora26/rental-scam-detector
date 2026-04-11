"use client";
import { useState, useRef, useEffect } from "react";
import { Sparkles, BookOpen, ChevronDown, Send, Bot, User } from "lucide-react";
import type { LLMResult, AnalysisResult } from "@/lib/types";
import { sendChat } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChatMsg { role: "user" | "assistant"; content: string; }

export function AnalysisSummary({ llm, result }: { llm: LLMResult; result: AnalysisResult }) {
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatOpen) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatOpen]);

  async function handleSend() {
    if (!input.trim() || thinking) return;
    const userMsg: ChatMsg = { role: "user", content: input.trim() };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setThinking(true);
    try {
      const reply = await sendChat(next, result as unknown as object);
      setMessages([...next, { role: "assistant", content: reply }]);
    } catch {
      setMessages([...next, { role: "assistant", content: "Sorry, something went wrong. Please try again." }]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="space-y-4 h-full flex flex-col">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Analysis</h3>
        <span className={cn(
          "inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full border",
          llm.powered_by_ai
            ? "bg-violet-500/15 text-violet-300 border-violet-500/25"
            : "bg-zinc-800 text-zinc-400 border-white/8"
        )}>
          {llm.powered_by_ai
            ? <><Sparkles size={9} className="animate-pulse2" />AI-powered</>
            : <><BookOpen size={9} />Rule-based</>
          }
        </span>
      </div>

      {/* Summary block */}
      <div className="relative rounded-xl border-l-[3px] border-violet-500 bg-violet-500/[0.06] px-4 py-3">
        <p className="text-sm text-zinc-300 leading-relaxed">{llm.summary}</p>
      </div>

      {/* Clause notes */}
      {llm.clause_advice?.length > 0 && (
        <div>
          <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-2">Clause notes</p>
          <ul className="space-y-1.5">
            {llm.clause_advice.map((line, i) => (
              <li key={i} className="flex gap-2 text-sm text-zinc-400">
                <span className="text-violet-500 shrink-0 mt-0.5 font-bold">›</span>
                <span className="leading-relaxed">{line}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div>
        <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider mb-2">What to do</p>
        <div className="space-y-1">
          {llm.user_action.split("\n").filter(Boolean).map((line, i) => (
            <p key={i} className="text-sm text-zinc-400 leading-relaxed">{line}</p>
          ))}
        </div>
      </div>


      {/* AI Chat */}
      <div className="mt-auto pt-3 border-t border-white/[0.06]">
        <button
          onClick={() => setChatOpen(!chatOpen)}
          className="flex items-center gap-2 text-[13px] font-medium text-violet-400 hover:text-violet-300 transition-colors w-full"
        >
          <Sparkles size={13} className={chatOpen ? "animate-pulse2" : ""} />
          <span>Ask AI about this document</span>
          <ChevronDown size={13} className={cn("ml-auto transition-transform", chatOpen && "rotate-180")} />
        </button>

        {chatOpen && (
          <div className="mt-3 space-y-3">
            <div className="rounded-xl bg-black/20 border border-white/[0.06] overflow-hidden">
              <div className="max-h-52 overflow-y-auto p-3 space-y-2">
                {messages.length === 0 && (
                  <p className="text-xs text-zinc-600 italic text-center py-2">
                    Ask about specific clauses, your rights as a tenant, or what a red flag means.
                  </p>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={cn("flex gap-2", m.role === "user" && "flex-row-reverse")}>
                    <div className={cn(
                      "w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                      m.role === "user" ? "bg-violet-600/30" : "bg-zinc-700/50"
                    )}>
                      {m.role === "user"
                        ? <User size={11} className="text-violet-300" />
                        : <Bot size={11} className="text-zinc-400" />
                      }
                    </div>
                    <div className={cn(
                      "rounded-xl px-3 py-2 text-xs max-w-[80%] leading-relaxed",
                      m.role === "user"
                        ? "bg-violet-600/25 text-violet-100"
                        : "bg-zinc-800/60 text-zinc-300"
                    )}>
                      {m.content}
                    </div>
                  </div>
                ))}
                {thinking && (
                  <div className="flex gap-2">
                    <div className="w-6 h-6 rounded-full bg-zinc-700/50 flex items-center justify-center shrink-0">
                      <Bot size={11} className="text-zinc-400" />
                    </div>
                    <div className="bg-zinc-800/60 rounded-xl px-3 py-2">
                      <span className="flex gap-1">
                        {[0,1,2].map(i => (
                          <span key={i} className="w-1 h-1 rounded-full bg-zinc-500 animate-pulse2"
                            style={{ animationDelay: `${i * 200}ms` }} />
                        ))}
                      </span>
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>

            <div className="flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSend()}
                placeholder="Ask a question…"
                className="flex-1 rounded-xl bg-white/[0.04] border border-white/8 px-3.5 py-2 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/50 transition-colors"
              />
              <button
                onClick={handleSend}
                disabled={thinking || !input.trim()}
                className="w-9 h-9 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors shrink-0"
              >
                <Send size={13} className="text-white" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
