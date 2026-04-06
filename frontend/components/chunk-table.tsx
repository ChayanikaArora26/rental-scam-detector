"use client";
import { useState } from "react";
import { ChevronDown, TableProperties } from "lucide-react";
import type { ChunkDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  details: ChunkDetail[];
}

export function ChunkTable({ details }: Props) {
  const [open, setOpen] = useState(false);
  if (!details?.length) return null;

  return (
    <div className="rounded-2xl border border-white/8 bg-zinc-900/40 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/3 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <TableProperties size={15} className="text-zinc-500" />
          Detailed clause scores ({details.length} chunks)
        </div>
        <ChevronDown
          size={15}
          className={cn("text-zinc-500 transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="overflow-x-auto border-t border-white/8">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-zinc-900/60">
                <th className="text-left px-4 py-2.5 text-zinc-500 font-medium w-1/2">Chunk</th>
                <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Score</th>
                <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {details.map((row, i) => (
                <tr key={i} className={cn("transition-colors", row.anomalous && "bg-red-500/5")}>
                  <td className="px-4 py-2.5 text-zinc-400 max-w-xs">
                    <p className="truncate">{row.chunk}</p>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <span
                      className={cn(
                        "font-mono font-semibold",
                        row.best_score < 0.2
                          ? "text-red-400"
                          : row.best_score < 0.3
                          ? "text-amber-400"
                          : "text-emerald-400"
                      )}
                    >
                      {row.best_score.toFixed(3)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {row.anomalous ? (
                      <span className="inline-flex items-center rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-400">
                        Anomalous
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                        Normal
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
