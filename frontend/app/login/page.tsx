"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();

  return (
    <AuthForm
      title="Welcome back"
      subtitle="Sign in to your RentalGuard account"
      fields={[
        { name: "email",    label: "Email",    type: "email",    placeholder: "jane@email.com" },
        { name: "password", label: "Password", type: "password", placeholder: "••••••••" },
      ]}
      submitLabel="Sign in"
      onSubmit={async ({ email, password }) => {
        await login(email, password);
        router.push("/");
      }}
      footer={
        <>
          <Link href="/forgot-password" className="text-violet-400 hover:text-violet-300 transition-colors">
            Forgot password?
          </Link>
          <span className="mx-3 text-zinc-700">·</span>
          No account?{" "}
          <Link href="/register" className="text-violet-400 hover:text-violet-300 transition-colors">
            Sign up
          </Link>
        </>
      }
    />
  );
}
