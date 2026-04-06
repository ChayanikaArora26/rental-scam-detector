"use client";
import { useState } from "react";
import { ChevronDown, Flag, CheckCircle2, AlertTriangle } from "lucide-react";
import type { RedFlag } from "@/lib/types";
import { cn } from "@/lib/utils";

export function RedFlags({ flags }: { flags: RedFlag[] }) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Flag size={14} className={flags.length ? "text-red-400" : "text-emerald-400"} />
          <h3 className="text-sm font-semibold text-white">Red Flags</h3>
        </div>
        <span className={cn(
          "text-[11px] font-bold px-2 py-0.5 rounded-full",
          flags.length
            ? "bg-red-500/15 text-red-400 border border-red-500/20"
            : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
        )}>
          {flags.length} found
        </span>
      </div>

      {flags.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <CheckCircle2 size={22} className="text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-300">No red flags detected</p>
            <p className="text-xs text-zinc-600 mt-0.5">No known scam patterns found in this document</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {flags.map((rf, i) => (
            <div
              key={i}
              className="rounded-xl border border-red-500/15 bg-red-500/[0.04] overflow-hidden"
            >
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-red-500/[0.06] transition-colors group"
              >
                <AlertTriangle size={13} className="text-red-400/70 shrink-0" />
                <span className="flex-1 text-sm font-medium text-zinc-200 group-hover:text-white transition-colors truncate">
                  {rf.flag}
                </span>
                <ChevronDown
                  size={13}
                  className={cn("text-zinc-600 transition-transform shrink-0", open === i && "rotate-180")}
                />
              </button>
              {open === i && (
                <div className="px-4 pb-3 pt-1">
                  <pre className="text-xs text-zinc-400 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap border border-white/[0.05] font-mono leading-relaxed">
                    {rf.snippet}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
