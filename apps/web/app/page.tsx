"use client";

import {
  ArrowRight,
  Box,
  CircleDollarSign,
  Cpu,
  ListChecks,
  PackageOpen,
  Percent,
  Play,
  Radio,
  Ship,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Button, Card, EmptyState, ErrorState, KpiCard, LoadingState, RiskBadge } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import { EVENT_TYPE_LABEL, date, moneyCompact } from "@/lib/format";
import type { ChangeEvent, EventType, ImpactAnalysis } from "@/lib/types";
import { useLoad } from "@/lib/use-load";

const EVENT_ICON: Record<EventType, LucideIcon> = {
  COMPONENT_EOL: Cpu,
  SUPPLIER_PRICE_INCREASE: TrendingUp,
  MATERIAL_PRICE_CHANGE: PackageOpen,
  FREIGHT_CHANGE: Ship,
  OTHER: Radio,
};

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning." : h < 18 ? "Good afternoon." : "Good evening.";
}

export default function OverviewPage() {
  const router = useRouter();
  const { setEventId } = useCurrentEvent();
  const events = useLoad(() => api.events(), "events");
  const latest = events.data?.find((e) => e.status === "ANALYZED") ?? null;
  const impact = useLoad(latest ? () => api.impact(latest.event_id) : null, latest?.event_id ?? "none",
    { refetchOnReset: false });
  const actions = useLoad(() => api.actionsSummary(), "actions");
  const [hello, setHello] = useState("Welcome.");
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setHello(greeting()), []);

  async function loadDemo() {
    setLoadingDemo(true);
    setDemoError(null);
    try {
      const { event } = await api.loadDemo();
      setEventId(event.event_id);
      router.push(`/analysis?event=${encodeURIComponent(event.event_id)}&reveal=1`);
    } catch (err) {
      setDemoError(errorMessage(err));
      setLoadingDemo(false);
    }
  }

  const ctas = (
    <>
      <Link href="/events/new" className="inline-flex h-11 items-center gap-2 rounded-lg bg-primary px-5 text-[15px] font-medium text-white shadow-sm hover:bg-primary-hover">
        <Radio className="size-[18px]" aria-hidden /> Analyze a Change
      </Link>
      <Button variant="secondary" size="lg" onClick={loadDemo} disabled={loadingDemo}>
        <Play aria-hidden /> {loadingDemo ? "Loading demo…" : "Load Demo Scenario"}
      </Button>
    </>
  );

  return (
    <div className="space-y-7">
      <section className="fade-in rounded-2xl border border-border bg-surface px-7 py-7">
        <p className="text-sm font-medium text-primary">{hello}</p>
        <h1 className="mt-2 max-w-3xl text-[30px] font-semibold leading-tight tracking-tight">
          Understand the ripple effect before it becomes a business problem.
        </h1>
        <p className="mt-2 max-w-2xl text-[15px] text-muted">
          Trace product dependencies, quantify financial impact, simulate scenarios, and coordinate the next action with AI.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">{ctas}</div>
        {demoError && <div className="mt-4"><ErrorState message={demoError} /></div>}
      </section>

      <section aria-labelledby="exposure">
        <h2 id="exposure" className="mb-3 text-lg font-semibold">Exposure Summary</h2>
        {impact.loading && latest ? (
          <Card><LoadingState label="Loading latest analysis…" /></Card>
        ) : impact.data ? (
          <ExposureCards impact={impact.data} openActions={actions.data?.open ?? null} totalActions={actions.data?.total ?? 0} />
        ) : (
          <Card>
            <EmptyState
              icon={Radio}
              title="No change events analyzed yet"
              description="Upload a supplier notice or load the demo scenario to see how RippleOps maps business impact."
              actions={ctas}
            />
          </Card>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <section aria-labelledby="active-events">
          <h2 id="active-events" className="mb-3 text-lg font-semibold">Active Change Events</h2>
          {events.loading ? (
            <Card><LoadingState label="Loading events…" /></Card>
          ) : events.error ? (
            <ErrorState message={events.error} action={<Button variant="secondary" size="sm" onClick={events.reload}>Try again</Button>} />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {(events.data ?? []).slice(0, 6).map((e) => <EventCard key={e.event_id} event={e} />)}
            </div>
          )}
        </section>

        <section aria-labelledby="recent">
          <h2 id="recent" className="mb-3 text-lg font-semibold">Recent Analysis</h2>
          <Card>
            {latest && impact.data ? (
              <div className="space-y-4 p-5">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge tone="primary">Analyzed</Badge>
                    <span className="text-xs text-subtle">{latest.event_id}</span>
                  </div>
                  <p className="mt-2 font-semibold">{latest.title}</p>
                  <p className="text-sm text-muted">{latest.supplier_name}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const)
                    .filter((l) => impact.data!.summary.risk_counts[l])
                    .map((l) => <RiskBadge key={l} level={l} suffix={` · ${impact.data!.summary.risk_counts[l]}`} />)}
                </div>
                <Link href={`/analysis?event=${latest.event_id}`} onClick={() => setEventId(latest.event_id)}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  Open analysis <ArrowRight className="size-4" aria-hidden />
                </Link>
              </div>
            ) : (
              <p className="p-5 text-sm text-muted">The most recent analysis will appear here.</p>
            )}
          </Card>
        </section>
      </div>
    </div>
  );
}

function ExposureCards({ impact, openActions, totalActions }: { impact: ImpactAnalysis; openActions: number | null; totalActions: number }) {
  const s = impact.summary;
  return (
    <div className="fade-in grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard label="Products at Risk" icon={Box} tone="critical" value={s.affected_product_count}
        context={`Use ${impact.component.part_id}, across ${s.product_family_count} product families`} />
      <KpiCard label="Revenue Exposure" icon={CircleDollarSign} value={moneyCompact(s.revenue_exposure)}
        context={`Forecast revenue, next ${s.horizon_months} months`} />
      <KpiCard label="Margin at Risk" icon={Percent} tone="warning"
        value={s.replacement_gross_profit_at_risk != null ? moneyCompact(s.replacement_gross_profit_at_risk) : "—"}
        context={s.replacement_part_id
          ? `Gross profit lost if switched to ${s.replacement_part_id}, next ${s.horizon_months} months`
          : "No alternative to evaluate"} />
      <KpiCard label="Open Actions" icon={ListChecks} tone="primary" value={openActions ?? "—"}
        context={totalActions ? `${totalActions - (openActions ?? 0)} of ${totalActions} completed` : "No response plan generated yet"} />
    </div>
  );
}

function EventCard({ event }: { event: ChangeEvent }) {
  const Icon = EVENT_ICON[event.event_type] ?? Radio;
  const { setEventId } = useCurrentEvent();
  const href = event.analyzable ? `/analysis?event=${event.event_id}` : `/events?focus=${event.event_id}`;
  return (
    <Link href={href} onClick={() => event.analyzable && setEventId(event.event_id)}
      className="group rounded-xl border border-border bg-surface p-4 transition-colors hover:border-primary-border">
      <div className="flex items-start justify-between gap-2">
        <span className="grid size-9 place-items-center rounded-lg bg-surface-muted text-muted group-hover:bg-primary-soft group-hover:text-primary">
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <Badge tone={event.status === "ANALYZED" ? "primary" : event.status === "NEW" ? "warning" : "neutral"}>
          {event.status === "ANALYZED" ? "Analyzed" : event.status === "NEW" ? "New" : "Monitoring"}
        </Badge>
      </div>
      <p className="mt-3 text-xs font-medium uppercase tracking-wide text-subtle">{EVENT_TYPE_LABEL[event.event_type]}</p>
      <p className="mt-0.5 font-semibold text-text">{event.title}</p>
      <p className="mt-1 line-clamp-2 text-sm text-muted">{event.summary}</p>
      <p className="mt-2 text-xs text-subtle">{date(event.event_date)}</p>
    </Link>
  );
}
