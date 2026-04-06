"use client";
import { useState } from "react";
import { Search, ChevronDown, Flag, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getHistory } from "@/lib/api";
import type { HistoryItem, RiskLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

function getRiskLevel(verdict: string): RiskLevel {
  const v = verdict.toUpperCase();
  if (v.includes("HIGH")) return "HIGH";
  if (v.includes("MEDIUM")) return "MEDIUM";
  return "LOW";
}

const RISK_BADGE: Record<RiskLevel, React.ComponentProps<typeof Badge>["variant"]> = {
  HIGH: "high", MEDIUM: "medium", LOW: "low",
};

export default function HistoryPage() {
  const [email, setEmail] = useState("");
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<number | null>(null);

  async function load() {
    if (!email.trim()) return;
    setError(""); setLoading(true);
    try {
      const data = await getHistory(email.trim());
      setItems(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-white">My History</h1>
        <p className="text-zinc-400">Look up past analyses by email address.</p>
      </div>

      <Card>
        <CardContent className="p-6">
          <div className="flex gap-3">
            <input
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key === "Enter" && load()}
              placeholder="jane@email.com"
              type="email"
              className="flex-1 rounded-xl bg-zinc-800/60 border border-white/8 px-4 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/50"
            />
            <Button onClick={load} disabled={loading || !email.trim()}>
              <Search size={15} />
              {loading ? "Loading…" : "Load history"}
            </Button>
          </div>
          {error && (
            <p className="mt-3 text-sm text-red-400">{error}</p>
          )}
        </CardContent>
      </Card>

      {items !== null && (
        <div className="space-y-3">
          {items.length === 0 ? (
            <p className="text-zinc-500 text-sm text-center py-10">
              No analyses found for <span className="text-white">{email}</span>.
            </p>
          ) : (
            <>
              <p className="text-sm text-zinc-500">
                {items.length} analysis/analyses found for{" "}
                <span className="text-white">{email}</span>
              </p>
              {items.map((item, i) => {
                const level = getRiskLevel(item.verdict);
                return (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-white/8 bg-zinc-900/40 overflow-hidden"
                  >
                    <button
                      onClick={() => setOpen(open === i ? null : i)}
                      className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-white/3 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <Badge variant={RISK_BADGE[level]}>{level}</Badge>
                          <span className="text-sm font-medium text-white truncate">
                            {item.filename || "Pasted text"}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-zinc-500">
                          <span className="flex items-center gap-1">
                            <Clock size={11} />
                            {item.created_at.slice(0, 16).replace("T", " ")} UTC
                          </span>
                          <span>Risk: {item.combined_risk}%</span>
                          <span className="flex items-center gap-1">
                            <Flag size={11} />
                            {item.n_flags} flag{item.n_flags !== 1 ? "s" : ""}
                          </span>
                        </div>
                      </div>
                      <ChevronDown
                        size={15}
                        className={cn(
                          "text-zinc-500 transition-transform shrink-0",
                          open === i && "rotate-180"
                        )}
                      />
                    </button>

                    {open === i && (
                      <div className="border-t border-white/8 px-5 py-4 space-y-4">
                        <p className="text-sm font-medium text-white">{item.verdict}</p>
                        {item.llm_summary && (
                          <div className="rounded-xl border-l-4 border-violet-500 bg-violet-500/8 px-4 py-3 text-sm text-zinc-300 leading-relaxed">
                            {item.llm_summary}
                          </div>
                        )}
                        {item.red_flags?.length > 0 ? (
                          <div className="space-y-2">
                            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                              Red flags
                            </p>
                            {item.red_flags.map((rf, j) => (
                              <div key={j} className="flex gap-2 text-sm text-zinc-400">
                                <span className="text-red-400 shrink-0">🚩</span>
                                <span>
                                  <span className="text-red-300 font-medium">{rf.flag}</span>
                                  {rf.snippet && (
                                    <code className="ml-2 text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                                      {rf.snippet.slice(0, 80)}…
                                    </code>
                                  )}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-emerald-400">✓ No red flags in this analysis.</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}
