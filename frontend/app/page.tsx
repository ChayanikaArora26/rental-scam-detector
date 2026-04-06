"use client";
import { useState, useRef } from "react";
import { Upload, FileText, Link as LinkIcon, X, ScanSearch, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { VerdictCard } from "@/components/verdict-card";
import { RedFlags } from "@/components/red-flags";
import { AnalysisSummary } from "@/components/analysis-summary";
import { ChunkTable } from "@/components/chunk-table";
import { analyseText, analyseFile, scrapeUrl } from "@/lib/api";
import type { AnalysisResult } from "@/lib/types";
import { cn } from "@/lib/utils";

type Tab = "file" | "text" | "url";

const STEPS = [
  "Fetching document…",
  "Scanning for red-flag patterns…",
  "Computing clause similarity scores…",
  "Generating analysis…",
];

const HOW_IT_WORKS = [
  {
    icon: ScanSearch,
    title: "Upload or paste",
    desc: "Submit a rental listing URL, upload a PDF/DOCX, or paste the text directly.",
  },
  {
    icon: ShieldCheck,
    title: "AI scans clauses",
    desc: "28 red-flag rules + semantic similarity against 510 real legal contracts detect anomalies.",
  },
  {
    icon: Sparkles,
    title: "Get a plain-English verdict",
    desc: "Risk score, flagged clauses, and actionable advice — in seconds.",
  },
];

function LoadingOverlay({ step }: { step: number }) {
  return (
    <div className="glass rounded-2xl p-10 flex flex-col items-center gap-6 glow-violet">
      <div className="relative w-16 h-16">
        <div className="absolute inset-0 rounded-full border-2 border-violet-500/20" />
        <div className="absolute inset-0 rounded-full border-t-2 border-violet-500 animate-spin-slow" />
        <div className="absolute inset-2 rounded-full border-t-2 border-indigo-400/60 animate-spin" style={{ animationDirection: "reverse", animationDuration: "1.5s" }} />
        <ScanSearch size={18} className="absolute inset-0 m-auto text-violet-400" />
      </div>
      <div className="text-center space-y-1.5">
        <p className="text-sm font-semibold text-white">{STEPS[step]}</p>
        <p className="text-xs text-zinc-500">Step {step + 1} of {STEPS.length}</p>
      </div>
      <div className="flex gap-1.5">
        {STEPS.map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-1 rounded-full transition-all duration-500",
              i <= step ? "bg-violet-500 w-8" : "bg-white/10 w-4"
            )}
          />
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("file");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleAnalyse() {
    setError("");
    setResult(null);
    setLoading(true);
    setStep(0);

    try {
      let raw = text;

      if (tab === "url") {
        setStep(0);
        raw = await scrapeUrl(url);
      } else if (tab === "file" && file) {
        setStep(0);
        // file passed directly
      }

      setStep(1);
      await new Promise(r => setTimeout(r, 300));
      setStep(2);

      let res: AnalysisResult;
      if (tab === "file" && file) {
        res = await analyseFile(file, name, email);
      } else {
        res = await analyseText(raw, name, email);
      }

      setStep(3);
      await new Promise(r => setTimeout(r, 400));
      setResult(res);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const canSubmit =
    !loading &&
    (tab === "file" ? !!file : tab === "url" ? url.trim().length > 0 : text.trim().length > 0);

  return (
    <div className="space-y-16">

      {/* ── Hero ───────────────────────────────────────────────── */}
      {!result && (
        <section className="text-center pt-8 space-y-6 animate-fade-up">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs font-medium text-zinc-400 border border-white/8">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse2" />
            510 CUAD contracts · NSW Tenancy Baseline · Claude AI
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
            Detect rental scams{" "}
            <span className="text-gradient">before you sign</span>
          </h1>

          <p className="text-zinc-400 max-w-xl mx-auto text-base leading-relaxed">
            Upload a tenancy agreement or paste a listing. Our AI scans for 28 scam patterns,
            compares clauses against 510 real contracts, and gives you a plain-English verdict.
          </p>

          {/* How it works */}
          <div className="grid sm:grid-cols-3 gap-4 pt-4 text-left max-w-3xl mx-auto">
            {HOW_IT_WORKS.map(({ icon: Icon, title, desc }, i) => (
              <div
                key={i}
                className="glass rounded-2xl p-5 space-y-3 hover:border-white/10 transition-all hover:-translate-y-0.5"
              >
                <div className="w-9 h-9 rounded-xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center">
                  <Icon size={16} className="text-brand-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white mb-1">
                    <span className="text-brand-400 mr-1.5">{i + 1}.</span>{title}
                  </p>
                  <p className="text-xs text-zinc-500 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Results ────────────────────────────────────────────── */}
      {result && (
        <div className="space-y-6 animate-fade-up">
          <VerdictCard result={result} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="glass rounded-2xl p-5">
              <RedFlags flags={result.red_flags} />
            </div>
            <div className="glass rounded-2xl p-5">
              <AnalysisSummary llm={result.llm} result={result} />
            </div>
          </div>

          <ChunkTable details={result.details} />

          <div className="text-center pt-2">
            <button
              onClick={() => setResult(null)}
              className="text-sm text-zinc-500 hover:text-white transition-colors inline-flex items-center gap-1.5"
            >
              ← Analyse another document
            </button>
          </div>
        </div>
      )}

      {/* ── Input form ─────────────────────────────────────────── */}
      {!result && (
        <section className="max-w-2xl mx-auto w-full space-y-4">
          {loading ? (
            <LoadingOverlay step={step} />
          ) : (
            <div className="glass rounded-2xl p-6 space-y-5">
              {/* Profile row */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Name", value: name, set: setName, placeholder: "Jane Smith",        type: "text"  },
                  { label: "Email", value: email, set: setEmail, placeholder: "jane@email.com",  type: "email" },
                ].map(({ label, value, set, placeholder, type }) => (
                  <div key={label} className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">
                      {label} <span className="text-zinc-700 normal-case font-normal">{label === "Email" ? "— saves history" : "optional"}</span>
                    </label>
                    <input
                      value={value}
                      onChange={e => set(e.target.value)}
                      placeholder={placeholder}
                      type={type}
                      className="w-full rounded-xl bg-white/[0.04] border border-white/8 px-3.5 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/60 focus:bg-violet-500/[0.04] transition-colors"
                    />
                  </div>
                ))}
              </div>

              {/* Divider */}
              <div className="border-t border-white/[0.06]" />

              {/* Tab switcher */}
              <div className="flex gap-1 p-1 bg-black/30 rounded-xl w-fit border border-white/[0.06]">
                {(["file", "text", "url"] as Tab[]).map(t => {
                  const icons = { file: Upload, text: FileText, url: LinkIcon };
                  const labels = { file: "Upload file", text: "Paste text", url: "From URL" };
                  const Icon = icons[t];
                  return (
                    <button
                      key={t}
                      onClick={() => setTab(t)}
                      className={cn(
                        "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all",
                        tab === t
                          ? "bg-white/10 text-white shadow-sm"
                          : "text-zinc-600 hover:text-zinc-300"
                      )}
                    >
                      <Icon size={12} />
                      {labels[t]}
                    </button>
                  );
                })}
              </div>

              {/* File drop zone */}
              {tab === "file" && (
                <div
                  onClick={() => fileRef.current?.click()}
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
                  className={cn(
                    "relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all group",
                    file
                      ? "border-violet-500/50 bg-violet-500/[0.05]"
                      : "border-white/10 hover:border-white/20 hover:bg-white/[0.02]"
                  )}
                >
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.docx"
                    className="hidden"
                    onChange={e => setFile(e.target.files?.[0] ?? null)}
                  />
                  {file ? (
                    <div className="flex items-center justify-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
                        <FileText size={16} className="text-violet-400" />
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-medium text-white">{file.name}</p>
                        <p className="text-xs text-zinc-500">{(file.size / 1024).toFixed(0)} KB</p>
                      </div>
                      <button
                        onClick={e => { e.stopPropagation(); setFile(null); }}
                        className="ml-2 text-zinc-600 hover:text-red-400 transition-colors"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="w-12 h-12 rounded-2xl bg-white/[0.04] border border-white/8 flex items-center justify-center mx-auto group-hover:border-white/16 transition-colors">
                        <Upload size={20} className="text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                      </div>
                      <div>
                        <p className="text-sm text-zinc-300">
                          Drop a <span className="font-semibold text-white">PDF</span> or{" "}
                          <span className="font-semibold text-white">DOCX</span> here
                        </p>
                        <p className="text-xs text-zinc-600 mt-1">or click to browse · Max 200 MB</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Paste text */}
              {tab === "text" && (
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  rows={7}
                  placeholder="e.g. 'Send $2000 via Western Union to secure this property. Landlord is overseas and cannot show the property…'"
                  className="w-full rounded-xl bg-white/[0.04] border border-white/8 px-4 py-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/60 focus:bg-violet-500/[0.03] transition-colors resize-none font-mono"
                />
              )}

              {/* URL */}
              {tab === "url" && (
                <div className="space-y-2">
                  <div className="relative">
                    <LinkIcon size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                    <input
                      value={url}
                      onChange={e => setUrl(e.target.value)}
                      placeholder="https://www.gumtree.com.au/s-ad/..."
                      className="w-full rounded-xl bg-white/[0.04] border border-white/8 pl-9 pr-4 py-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/60 focus:bg-violet-500/[0.03] transition-colors"
                    />
                  </div>
                  <p className="text-xs text-zinc-600">
                    Supports Gumtree, Domain, realestate.com.au, and most public listing pages.
                  </p>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/[0.08] px-4 py-3">
                  <span className="text-red-400 mt-0.5 text-lg leading-none">⚠</span>
                  <p className="text-sm text-red-300">{error}</p>
                </div>
              )}

              {/* Submit */}
              <Button
                size="lg"
                className="w-full h-12 text-[15px] font-semibold tracking-tight"
                onClick={handleAnalyse}
                disabled={!canSubmit}
              >
                <ScanSearch size={17} />
                Analyse Document
              </Button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
