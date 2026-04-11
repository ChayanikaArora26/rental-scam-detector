import { ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import type { AnalysisResult, RiskLevel } from "@/lib/types";

const RISK_CONFIG: Record<RiskLevel, {
  label: string;
  icon: React.ElementType;
  color: string;
  textColor: string;
  border: string;
  bg: string;
  glow: string;
  ringColor: string;
  trackColor: string;
}> = {
  HIGH: {
    label: "HIGH RISK",
    icon: ShieldX,
    color: "#ef4444",
    textColor: "text-red-400",
    border: "border-red-500/25",
    bg: "bg-red-500/[0.07]",
    glow: "glow-red",
    ringColor: "#ef4444",
    trackColor: "#ef444420",
  },
  MEDIUM: {
    label: "MEDIUM RISK",
    icon: ShieldAlert,
    color: "#f59e0b",
    textColor: "text-amber-400",
    border: "border-amber-500/25",
    bg: "bg-amber-500/[0.07]",
    glow: "glow-amber",
    ringColor: "#f59e0b",
    trackColor: "#f59e0b20",
  },
  LOW: {
    label: "LOW RISK",
    icon: ShieldCheck,
    color: "#10b981",
    textColor: "text-emerald-400",
    border: "border-emerald-500/25",
    bg: "bg-emerald-500/[0.07]",
    glow: "glow-green",
    ringColor: "#10b981",
    trackColor: "#10b98120",
  },
};

export function getRiskLevel(verdict: string): RiskLevel {
  const v = verdict.toUpperCase();
  if (v.includes("HIGH RISK")) return "HIGH";
  if (v.includes("LOW-MEDIUM") || v.includes("LOW MEDIUM")) return "LOW";
  if (v.includes("MEDIUM")) return "MEDIUM";
  return "LOW";
}

function ScoreRing({ value, color, trackColor }: { value: number; color: string; trackColor: string }) {
  const size = 120;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(value, 100) / 100;
  const offset = circ * (1 - pct);

  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      {/* Track */}
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={trackColor} strokeWidth={stroke} />
      {/* Progress */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{ filter: `drop-shadow(0 0 6px ${color}80)`, transition: "stroke-dashoffset 0.8s ease" }}
      />
    </svg>
  );
}

export function VerdictCard({ result }: { result: AnalysisResult }) {
  const level = getRiskLevel(result.verdict);
  const cfg = RISK_CONFIG[level];
  const Icon = cfg.icon;
  const risk = Math.min(result.combined_risk, 100);

  const stats = [
    { label: "Red Flags",         value: result.n_flags,                                   },
    { label: "Anomalous Clauses", value: `${result.n_anomalous}/${result.total_chunks}`     },
    { label: "Safe Clauses",      value: result.total_chunks - result.n_anomalous           },
  ];

  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} ${cfg.glow} p-6`}>
      <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">

        {/* Score ring */}
        <div className="relative shrink-0">
          <ScoreRing value={risk} color={cfg.ringColor} trackColor={cfg.trackColor} />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-2xl font-bold ${cfg.textColor}`}>{risk}%</span>
            <span className="text-[10px] text-zinc-500 font-medium tracking-wide">RISK</span>
          </div>
        </div>

        {/* Text content */}
        <div className="flex-1 min-w-0 text-center sm:text-left space-y-3">
          <div>
            <div className="flex items-center justify-center sm:justify-start gap-2 mb-1">
              <Icon size={16} className={cfg.textColor} />
              <span className={`text-[11px] font-bold tracking-widest ${cfg.textColor} uppercase`}>
                {cfg.label}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white leading-snug">{result.verdict}</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Scanned against 510 CUAD contracts + NSW Tenancy Baseline
            </p>
          </div>

          {/* Stats row */}
          <div className="flex flex-wrap justify-center sm:justify-start gap-3">
            {stats.map(({ label, value }) => (
              <div key={label} className="glass rounded-xl px-4 py-2.5 text-center min-w-[90px]">
                <p className="text-base font-bold text-white">{value}</p>
                <p className="text-[11px] text-zinc-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
