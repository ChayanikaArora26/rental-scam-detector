const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface AuthUser {
  id: string;
  email: string;
  is_verified: boolean;
  role: string;
}

// ── Token storage (memory only — not localStorage) ─────────────
let _accessToken: string | null = null;
let _expiresAt: number | null   = null;

export function setAccessToken(token: string, expiresIn: number) {
  _accessToken = token;
  _expiresAt   = Date.now() + expiresIn * 1000 - 30_000; // 30s buffer
}

export function getAccessToken(): string | null {
  if (!_accessToken || !_expiresAt) return null;
  if (Date.now() > _expiresAt) {
    _accessToken = null;
    return null;
  }
  return _accessToken;
}

export function clearAccessToken() {
  _accessToken = null;
  _expiresAt   = null;
}

// ── API calls ──────────────────────────────────────────────────

export async function register(email: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Registration failed");
  return data;
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",   // receive httpOnly refresh cookie
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Login failed");
  setAccessToken(data.access_token, data.expires_in);
  return data.access_token;
}

export async function refreshToken(): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = await res.json();
    setAccessToken(data.access_token, data.expires_in);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  clearAccessToken();
  await fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "include" });
}

export async function getMe(token: string): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to get user");
  return data;
}

export async function forgotPassword(email: string): Promise<void> {
  await fetch(`${BASE}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Reset failed");
}

// ── Auth context helper ────────────────────────────────────────

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let token = getAccessToken();
  if (!token) token = await refreshToken();
  if (!token) throw new Error("Not authenticated");

  return fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
}
