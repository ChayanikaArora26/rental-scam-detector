import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";
import { ShieldCheck } from "lucide-react";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "RentalGuard — Rental Scam Detector",
  description: "Detect scams in rental listings and tenancy agreements using AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className={`${inter.variable} font-sans min-h-full flex flex-col`}>
        <Nav />
        <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-10">
          {children}
        </main>
        <footer className="border-t border-white/[0.05] mt-16">
          <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-zinc-500 text-sm">
              <ShieldCheck size={14} className="text-brand-500" />
              <span>RentalGuard — for informational purposes only, not legal advice</span>
            </div>
            <div className="flex items-center gap-5 text-xs text-zinc-600">
              <span>Powered by CUAD + NSW Tenancy Baseline</span>
              <span className="hidden sm:block">·</span>
              <span className="hidden sm:block">Claude AI (optional)</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
