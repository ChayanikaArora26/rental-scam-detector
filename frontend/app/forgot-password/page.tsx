"use client";
import Link from "next/link";
import { useState } from "react";
import { AuthForm } from "@/components/auth-form";
import { forgotPassword } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [done, setDone] = useState(false);

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="glass rounded-2xl p-10 max-w-md w-full text-center space-y-4">
          <div className="text-5xl">🔑</div>
          <h2 className="text-xl font-bold text-white">Reset link sent</h2>
          <p className="text-zinc-400 text-sm leading-relaxed">
            If that email is registered, you'll receive a password reset link valid for 15 minutes.
          </p>
          <Link href="/login" className="text-sm text-violet-400 hover:underline">Back to login</Link>
        </div>
      </div>
    );
  }

  return (
    <AuthForm
      title="Forgot password"
      subtitle="Enter your email and we'll send a reset link"
      fields={[
        { name: "email", label: "Email", type: "email", placeholder: "jane@email.com" },
      ]}
      submitLabel="Send reset link"
      onSubmit={async ({ email }) => {
        await forgotPassword(email);
        setDone(true);
      }}
      footer={
        <Link href="/login" className="text-violet-400 hover:text-violet-300 transition-colors">
          ← Back to login
        </Link>
      }
    />
  );
}
