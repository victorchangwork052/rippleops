import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppShell } from "@/components/app-shell";
import { CurrentEventProvider } from "@/lib/current-event";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RippleOps — Change Impact Intelligence",
  description: "Trace product dependencies, quantify financial impact, simulate scenarios, and coordinate the next action.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <CurrentEventProvider>
          <AppShell>{children}</AppShell>
        </CurrentEventProvider>
      </body>
    </html>
  );
}
