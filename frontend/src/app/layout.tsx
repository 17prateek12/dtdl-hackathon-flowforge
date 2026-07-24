import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const sans = DM_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LoopForge — AI Coding Workbench",
  description:
    "A control plane for long-running AI coding loops: plan, execute, validate, retry.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} h-full`}>
      <body className="h-full overflow-hidden bg-[#f4f6fb] font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
