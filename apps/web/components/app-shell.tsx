"use client";

import {
  Bot,
  Database,
  Factory,
  LayoutDashboard,
  ListChecks,
  Network,
  Radio,
  RotateCcw,
  Scale,
  SlidersHorizontal,
  Waves,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui";
import { Assistant } from "@/features/assistant/assistant";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import { cn } from "@/lib/utils";

const NAV: { href: string; label: string; icon: LucideIcon; eventScoped?: boolean }[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/events", label: "Events", icon: Radio },
  { href: "/analysis", label: "Impact Analysis", icon: Network, eventScoped: true },
  { href: "/sourcing", label: "Sourcing", icon: Scale, eventScoped: true },
  { href: "/planning", label: "Production Plan", icon: Factory, eventScoped: true },
  { href: "/scenarios", label: "Scenarios", icon: SlidersHorizontal, eventScoped: true },
  { href: "/actions", label: "Actions", icon: ListChecks, eventScoped: true },
  { href: "/agents", label: "Agent Activity", icon: Bot, eventScoped: true },
  { href: "/data", label: "Data", icon: Database },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { eventId, setEventId } = useCurrentEvent();
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  async function resetDemo() {
    setResetting(true);
    setResetError(null);
    try {
      await api.resetDemo();
      setEventId(null);
      // Event-scoped pages would refetch a deleted event, so leave them for the Overview;
      // if already there, tell it to reload.
      if (pathname === "/") window.dispatchEvent(new Event("rippleops:reset"));
      else router.push("/");
    } catch (err) {
      setResetError(errorMessage(err));
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface md:flex">
        <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
          <span className="grid size-8 place-items-center rounded-lg bg-primary text-white">
            <Waves className="size-[18px]" aria-hidden />
          </span>
          <span className="text-[17px] font-semibold tracking-tight">RippleOps</span>
        </Link>
        <nav aria-label="Primary" className="flex-1 space-y-0.5 px-3">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const href = item.eventScoped && eventId ? `${item.href}?event=${encodeURIComponent(eventId)}` : item.href;
            return (
              <Link
                key={item.href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-primary-soft text-primary" : "text-muted hover:bg-surface-muted hover:text-text",
                )}
              >
                <item.icon className="size-5" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="space-y-2 border-t border-border p-3">
          {resetError && <p className="px-1 text-xs text-critical">{resetError}</p>}
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={resetDemo} disabled={resetting}>
            <RotateCcw aria-hidden className={cn(resetting && "animate-spin")} />
            {resetting ? "Resetting…" : "Reset Demo"}
          </Button>
          <p className="px-1 text-[11px] leading-snug text-subtle">Fictional demo data. All figures are calculated, not generated.</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Compact navigation for tablet widths */}
        <header className="flex items-center gap-2 overflow-x-auto border-b border-border bg-surface px-4 py-2 md:hidden">
          <span className="mr-2 flex items-center gap-2 font-semibold">
            <Waves className="size-5 text-primary" aria-hidden /> RippleOps
          </span>
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.eventScoped && eventId ? `${item.href}?event=${eventId}` : item.href}
              className="rounded-md px-2 py-1 text-sm text-muted hover:bg-surface-muted"
            >
              {item.label}
            </Link>
          ))}
        </header>
        <main className="mx-auto w-full max-w-[1480px] flex-1 px-6 py-7 lg:px-8">{children}</main>
      </div>
      {pathname !== "/" && !pathname.startsWith("/events/new") && <Assistant />}
    </div>
  );
}
