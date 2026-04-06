"use client";
import { useState } from "react";
import Link from "next/link";
import { Loader2, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

interface Field {
  name: string;
  label: string;
  type?: string;
  placeholder?: string;
  hint?: string;
}

interface AuthFormProps {
  title: string;
  subtitle: string;
  fields: Field[];
  submitLabel: string;
  onSubmit: (values: Record<string, string>) => Promise<void>;
  footer?: React.ReactNode;
}

export function AuthForm({ title, subtitle, fields, submitLabel, onSubmit, footer }: AuthFormProps) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map(f => [f.name, ""]))
  );
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setSuccess("");
    setLoading(true);
    try {
      await onSubmit(values);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-md space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-500 flex items-center justify-center mx-auto shadow-lg shadow-violet-500/25">
            <ShieldCheck size={22} className="text-white" strokeWidth={2.5} />
          </div>
          <h1 className="text-2xl font-bold text-white">{title}</h1>
          <p className="text-sm text-zinc-500">{subtitle}</p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl p-8 space-y-5">
          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/[0.08] px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.08] px-4 py-3 text-sm text-emerald-300">
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {fields.map(field => (
              <div key={field.name} className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  {field.label}
                </label>
                <div className="relative">
                  <input
                    type={
                      field.type === "password"
                        ? showPassword ? "text" : "password"
                        : field.type ?? "text"
                    }
                    value={values[field.name]}
                    onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))}
                    placeholder={field.placeholder}
                    required
                    autoComplete={field.type === "password" ? "current-password" : field.name}
                    className="w-full rounded-xl bg-white/[0.04] border border-white/8 px-4 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/60 focus:bg-violet-500/[0.03] transition-colors pr-10"
                  />
                  {field.type === "password" && (
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors"
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  )}
                </div>
                {field.hint && (
                  <p className="text-xs text-zinc-600">{field.hint}</p>
                )}
              </div>
            ))}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-500 text-white text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed mt-2 shadow-lg shadow-violet-500/20"
            >
              {loading ? <><Loader2 size={15} className="animate-spin" />Working…</> : submitLabel}
            </button>
          </form>
        </div>

        {footer && (
          <div className="text-center text-sm text-zinc-500">{footer}</div>
        )}
      </div>
    </div>
  );
}
