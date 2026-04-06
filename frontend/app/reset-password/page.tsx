"use client";
import Link from "next/link";
import { useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { resetPassword } from "@/lib/auth";

function ResetPasswordInner() {
  const params = useSearchParams();
  const token  = params.get("token") ?? "";
  const router = useRouter();
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="glass rounded-2xl p-10 max-w-md w-full text-center space-y-4">
          <p className="text-red-400">Invalid reset link. Please request a new one.</p>
          <Link href="/forgot-password" className="text-violet-400 hover:underline text-sm">
            Request new link
          </Link>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="glass rounded-2xl p-10 max-w-md w-full text-center space-y-4">
          <div className="text-5xl">✅</div>
          <h2 className="text-xl font-bold text-white">Password updated</h2>
          <p className="text-zinc-400 text-sm">You can now sign in with your new password.</p>
          <Link href="/login" className="text-sm text-violet-400 hover:underline">Sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <AuthForm
      title="Set new password"
      subtitle="Choose a strong password for your account"
      fields={[
        {
          name: "password", label: "New password", type: "password", placeholder: "••••••••",
          hint: "Min 8 chars · 1 uppercase · 1 number · 1 special character",
        },
      ]}
      submitLabel="Update password"
      onSubmit={async ({ password }) => {
        await resetPassword(token, password);
        setDone(true);
      }}
    />
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordInner />
    </Suspense>
  );
}
