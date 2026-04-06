"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthForm } from "@/components/auth-form";
import { register } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [done, setDone] = useState(false);

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="glass rounded-2xl p-10 max-w-md w-full text-center space-y-4">
          <div className="text-5xl">📬</div>
          <h2 className="text-xl font-bold text-white">Check your email</h2>
          <p className="text-zinc-400 text-sm leading-relaxed">
            We sent a verification link to your inbox. Click it to activate your account, then{" "}
            <Link href="/login" className="text-violet-400 hover:underline">sign in</Link>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <AuthForm
      title="Create account"
      subtitle="Start detecting rental scams for free"
      fields={[
        { name: "email",    label: "Email",    type: "email",    placeholder: "jane@email.com" },
        {
          name: "password", label: "Password", type: "password", placeholder: "••••••••",
          hint: "Min 8 chars · 1 uppercase · 1 number · 1 special character",
        },
      ]}
      submitLabel="Create account"
      onSubmit={async ({ email, password }) => {
        await register(email, password);
        setDone(true);
      }}
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="text-violet-400 hover:text-violet-300 transition-colors">
            Sign in
          </Link>
        </>
      }
    />
  );
}
