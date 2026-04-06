import type { AnalysisResult, HistoryItem, StatusResult } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function analyseText(
  text: string,
  name: string,
  email: string
): Promise<AnalysisResult> {
  const fd = new FormData();
  fd.append("text", text);
  fd.append("name", name);
  fd.append("email", email);
  const res = await fetch(`${BASE}/api/analyse`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Analysis failed");
  return res.json();
}

export async function analyseFile(
  file: File,
  name: string,
  email: string
): Promise<AnalysisResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", name);
  fd.append("email", email);
  const res = await fetch(`${BASE}/api/analyse`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Analysis failed");
  return res.json();
}

export async function scrapeUrl(url: string): Promise<string> {
  const res = await fetch(`${BASE}/api/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Scrape failed");
  const data = await res.json();
  return data.text;
}

export async function getHistory(email: string): Promise<HistoryItem[]> {
  const res = await fetch(`${BASE}/api/history/${encodeURIComponent(email)}`);
  if (!res.ok) throw new Error("Failed to load history");
  const data = await res.json();
  return data.analyses;
}

export async function getStatus(): Promise<StatusResult> {
  const res = await fetch(`${BASE}/api/status`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function sendChat(
  messages: { role: string; content: string }[],
  context: object | null
): Promise<string> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, context }),
  });
  if (!res.ok) throw new Error("Chat failed");
  const data = await res.json();
  return data.reply;
}
