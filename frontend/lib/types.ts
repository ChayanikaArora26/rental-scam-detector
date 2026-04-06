export type RiskLevel = "HIGH" | "MEDIUM" | "LOW";

export interface RedFlag {
  flag: string;
  snippet: string;
}

export interface LLMResult {
  summary: string;
  clause_advice: string[];
  user_action: string;
  powered_by_ai: boolean;
  provider: string;
}

export interface ChunkDetail {
  chunk: string;
  best_score: number;
  anomalous: boolean;
}

export interface AnalysisResult {
  verdict: string;
  combined_risk: number;
  flag_score: number;
  n_flags: number;
  n_anomalous: number;
  total_chunks: number;
  anomaly_pct: number;
  red_flags: RedFlag[];
  llm: LLMResult;
  details: ChunkDetail[];
  filename: string;
}

export interface HistoryItem {
  id: number;
  filename: string;
  verdict: string;
  combined_risk: number;
  n_flags: number;
  n_anomalous: number;
  llm_summary: string;
  created_at: string;
  red_flags: RedFlag[];
}

export interface StatusResult {
  ok: boolean;
  llm_provider: string;
  llm_enabled: boolean;
}
