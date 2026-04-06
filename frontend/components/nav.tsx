"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ShieldCheck, LayoutDashboard, History, Info, LogIn, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { logout, getAccessToken } from "@/lib/auth";

const links = [
  { href: "/",        label: "Analyse", icon: LayoutDashboard },
  { href: "/history", label: "History", icon: History         },
  { href: "/about",   label: "About",   icon: Info            },
];

export function Nav() {
  const path     = usePathname();
  const router   = useRouter();
  const loggedIn = typeof window !== "undefined" && !!getAccessToken();

  async function handleLogout() {
    await logout();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-50 glass border-b border-white/[0.06]">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">

        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 group shrink-0">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-500 flex items-center justify-center shadow-lg group-hover:shadow-violet-500/30 transition-shadow">
            <ShieldCheck size={14} className="text-white" strokeWidth={2.5} />
          </div>
          <span className="font-semibold text-sm text-white tracking-tight hidden sm:block">
            Rental<span className="text-brand-400">Guard</span>
          </span>
        </Link>

        <div className="flex items-center gap-1">
          {/* Nav links */}
          <nav className="flex items-center gap-0.5">
            {links.map(({ href, label, icon: Icon }) => {
              const active = path === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[13px] font-medium transition-all",
                    active
                      ? "bg-white/10 text-white"
                      : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05]"
                  )}
                >
                  <Icon size={13} strokeWidth={active ? 2.5 : 2} />
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* Auth action */}
          <div className="ml-2 pl-2 border-l border-white/[0.08]">
            {loggedIn ? (
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium text-zinc-500 hover:text-red-400 hover:bg-red-500/[0.07] transition-all"
              >
                <LogOut size={13} />
                <span className="hidden sm:inline">Sign out</span>
              </button>
            ) : (
              <Link
                href="/login"
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[13px] font-medium transition-all",
                  path === "/login"
                    ? "bg-white/10 text-white"
                    : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05]"
                )}
              >
                <LogIn size={13} />
                <span className="hidden sm:inline">Sign in</span>
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
