"use client";

import {
  ArrowRightLeft,
  Ban,
  ChevronDown,
  CircleAlert,
  Gauge,
  Newspaper,
  PlugZap,
  Scale,
  ShieldCheck,
  Timer,
  Truck,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Fragment, Suspense, useEffect, useState } from "react";

import { Badge, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, buttonVariants } from "@/components/ui";
import { AgentFindings } from "@/features/agents/agent-findings";
import { api } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import { money, pct, qty } from "@/lib/format";
import type { Scorecard, SourcingCandidate, SourcingTier, SourcingView, SupplierEvidence, WorkflowRun } from "@/lib/types";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

const TIER: Record<SourcingTier, { label: string; tone: "success" | "primary" | "warning" | "neutral" | "critical" }> = {
  PREFERRED: { label: "Preferred", tone: "success" },
  VIABLE: { label: "Viable", tone: "primary" },
  BRIDGE_ONLY: { label: "Bridge only", tone: "warning" },
  NOT_RECOMMENDED: { label: "Not recommended", tone: "neutral" },
  BLOCKED: { label: "Blocked", tone: "critical" },
};

const SEVERITY_TONE: Record<string, "critical" | "warning" | "neutral" | "success"> = {
  HIGH: "critical", MEDIUM: "warning", LOW: "neutral", POSITIVE: "success",
};

async function load(eventId: string): Promise<{ view: SourcingView; run: WorkflowRun | null }> {
  const [view, run] = await Promise.all([api.sourcing(eventId), api.workflow(eventId)]);
  return { view, run };
}

function SourcingPage() {
  const params = useSearchParams();
  const { eventId: current, setEventId } = useCurrentEvent();
  const eventId = params.get("event") ?? current;
  const data = useLoad(eventId ? () => load(eventId) : null, eventId ?? "");

  useEffect(() => {
    if (eventId && eventId !== current) setEventId(eventId);
  }, [eventId, current, setEventId]);

  const header = (
    <PageHeader title="Alternative Sourcing"
      description="Alternative parts and suppliers, scored on delivery, quality, lead time, cost, supply risk and qualification. Scores are calculated; agents explain them." />
  );
  if (!eventId) {
    return (
      <div className="space-y-6">{header}
        <Card><EmptyState icon={Scale} title="No change event selected" description="Analyze a component change to evaluate alternative sources."
          actions={<Link href="/events/new" className={buttonVariants()}>Analyze a Change</Link>} /></Card>
      </div>
    );
  }
  if (data.loading) return <div className="space-y-6">{header}<Card><LoadingState label="Searching vendors and scoring suppliers…" /></Card></div>;
  if (data.error || !data.data) return <div className="space-y-6">{header}<ErrorState message={data.error ?? "No data"} /></div>;

  const { view, run } = data.data;
  const { sourcing, assessment } = view;
  const cand = Object.fromEntries(sourcing.candidates.map((c) => [c.candidate_id, c]));
  const card = Object.fromEntries(assessment.scorecards.map((c) => [c.candidate_id, c]));
  const pick = (id: string | null) => (id ? { c: cand[id], s: card[id] } : null);

  return (
    <div className="space-y-6">
      {header}
      <div className="grid gap-4 md:grid-cols-3">
        <RoleCard icon={ArrowRightLeft} role="Transition now" pick={pick(assessment.recommended_candidate_id)}
          note="Fastest approved replacement" />
        <RoleCard icon={ShieldCheck} role="Long-term second source" pick={pick(assessment.second_source_candidate_id)}
          note="Best supplier score; start qualification" />
        <RoleCard icon={Timer} role="Bridge stock" pick={pick(assessment.bridge_candidate_id)}
          note="Same part, to cover the gap; inspect on receipt" />
      </div>

      {assessment.blocked_candidate_ids.map((id) => (
        <div key={id} role="alert" className="flex items-start gap-3 rounded-xl border border-critical-border bg-critical-soft p-4">
          <Ban className="mt-0.5 size-5 shrink-0 text-critical" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-critical">{cand[id].supplier_name} is blocked</p>
            <p className="text-sm text-text">{card[id].flags[0]}. Its {cand[id].part_id} offer at {money(cand[id].unit_price)} cannot be used.</p>
          </div>
        </div>
      ))}

      <AgentFindings run={run} agents={["sourcing_scout", "supplier_evaluator"]} title="Sourcing agents" />

      <Card>
        <CardHeader icon={Scale} title={`Sourcing options for ${sourcing.part_id}`}
          description={`Current: ${sourcing.current_supplier} at ${money(sourcing.current_unit_price)} per unit · ${sourcing.affected_products} affected products. Select a row for the score breakdown.`} />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-sm">
            <thead className="bg-surface-muted text-left text-xs font-medium text-muted">
              <tr>
                <th className="px-5 py-2.5">Option</th>
                <th className="px-3 py-2.5">Source</th>
                <th className="px-3 py-2.5 text-right">Unit price</th>
                <th className="px-3 py-2.5 text-right">Lead time</th>
                <th className="px-3 py-2.5">Qualification</th>
                <th className="px-5 py-2.5">Score</th>
              </tr>
            </thead>
            <tbody>
              {assessment.scorecards.map((s) => <OptionRow key={s.candidate_id} c={cand[s.candidate_id]} s={s} />)}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <PerformanceCard evidence={assessment.evidence} />
        <NewsCard evidence={assessment.evidence} />
      </div>
      <ComplianceCard evidence={assessment.evidence} />
      <ProvidersCard providers={assessment.providers} />
    </div>
  );
}

function RoleCard({ icon: Icon, role, pick, note }: {
  icon: LucideIcon; role: string; note: string; pick: { c: SourcingCandidate; s: Scorecard } | null;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-[13px] font-medium text-muted"><Icon className="size-4" aria-hidden /> {role}</div>
      {pick ? (
        <>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-xl font-semibold text-text">{pick.c.part_id}</span>
            <span className="num text-sm text-muted">score {pick.s.total_score.toFixed(1)}</span>
          </div>
          <p className="text-sm text-text">{pick.c.supplier_name}</p>
          <p className="num mt-1 text-xs text-subtle">{money(pick.c.unit_price)} ({pick.c.price_delta_pct > 0 ? "+" : ""}{pct(pick.c.price_delta_pct)} vs. current) · {pick.c.lead_time_days} days</p>
          <p className="mt-2 text-xs text-muted">{note}</p>
        </>
      ) : <p className="mt-2 text-sm text-subtle">None found</p>}
    </Card>
  );
}

function OptionRow({ c, s }: { c: SourcingCandidate; s: Scorecard }) {
  const [open, setOpen] = useState(false);
  const tier = TIER[s.tier];
  return (
    <Fragment>
      <tr className={cn("cursor-pointer border-t border-border hover:bg-surface-muted/60", open && "bg-surface-muted/60")}
        onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <td className="px-5 py-3">
          <div className="flex items-center gap-2">
            <ChevronDown className={cn("size-4 text-subtle transition-transform", open && "rotate-180")} aria-hidden />
            <div>
              <p className="font-semibold text-text">{c.part_id} <span className="font-normal text-muted">· {c.supplier_name}</span></p>
              <p className="text-xs text-subtle">{c.country} · {c.match_type.replaceAll("_", " ").toLowerCase()}{c.is_new_supplier ? " · new supplier" : ""}</p>
            </div>
          </div>
        </td>
        <td className="px-3 py-3">
          <Badge tone={c.source === "INTERNAL_AVL" ? "primary" : "neutral"}>{c.source === "INTERNAL_AVL" ? "Approved vendor list" : "Distributor catalog"}</Badge>
          <p className="mt-1 text-xs text-subtle">{c.channel.replaceAll("_", " ").toLowerCase()}</p>
        </td>
        <td className="num px-3 py-3 text-right">{money(c.unit_price)}<p className={cn("text-xs", c.price_delta_pct > 0 ? "text-critical" : "text-success")}>{c.price_delta_pct > 0 ? "+" : ""}{pct(c.price_delta_pct)}</p></td>
        <td className="num px-3 py-3 text-right">{c.lead_time_days} days{c.available_stock ? <p className="text-xs text-subtle">{qty(c.available_stock)} in stock</p> : null}</td>
        <td className="px-3 py-3 text-xs text-muted">
          {c.match_type === "SAME_PART"
            ? `Same part${c.qualification_lead_time_days ? ` · inspection ~${c.qualification_lead_time_days} days` : ""}`
            : c.approval_status === "APPROVED"
            ? c.products_needing_validation.length ? `Approved · ${c.products_needing_validation.length} products need validation` : "Approved"
            : `${c.approval_status === "NOT_QUALIFIED" ? "Not qualified" : "Not approved"} · ~${c.qualification_lead_time_days} days`}
        </td>
        <td className="px-5 py-3">
          <div className="flex items-center gap-2.5">
            <div className="h-2 w-24 overflow-hidden rounded-full bg-surface-muted" aria-hidden>
              <div className={cn("h-full rounded-full", s.tier === "BLOCKED" ? "bg-critical" : s.tier === "PREFERRED" ? "bg-success" : "bg-primary")}
                style={{ width: `${s.total_score}%` }} />
            </div>
            <span className="num w-9 font-semibold text-text">{s.total_score.toFixed(1)}</span>
            <Badge tone={tier.tone}>{tier.label}</Badge>
          </div>
        </td>
      </tr>
      {open && (
        <tr className="bg-surface-muted/40">
          <td colSpan={6} className="px-5 pb-4 pt-1">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {s.components.map((x) => (
                <div key={x.criterion} className="rounded-lg border border-border bg-surface px-3 py-2">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs font-medium text-muted">{x.criterion}</span>
                    <span className="num text-sm font-semibold text-text">{x.score.toFixed(1)} / {x.weight}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-subtle">{x.evidence}</p>
                </div>
              ))}
            </div>
            {!!s.flags.length && (
              <ul className="mt-3 space-y-1">
                {s.flags.map((f) => (
                  <li key={f} className="flex items-start gap-1.5 text-xs text-warning"><CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {f}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-subtle">{c.notes}</p>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

function PerformanceCard({ evidence }: { evidence: SupplierEvidence[] }) {
  return (
    <Card>
      <CardHeader icon={Gauge} title="Supplier performance" description="Last four quarters from the ERP and quality system" />
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-muted">
          <tr><th className="px-5 py-2">Supplier</th><th className="px-3 py-2 text-right">On time</th><th className="px-3 py-2 text-right">Defects (ppm)</th><th className="px-5 py-2 text-right">Trend</th></tr>
        </thead>
        <tbody>
          {evidence.map((e) => (
            <tr key={e.supplier_id} className="border-t border-border">
              <td className="px-5 py-2.5 text-text">{e.supplier_name}</td>
              {e.performance ? (
                <>
                  <td className="num px-3 py-2.5 text-right">{pct(e.performance.on_time_delivery_rate)}</td>
                  <td className="num px-3 py-2.5 text-right">{qty(e.performance.quality_ppm)}</td>
                  <td className={cn("num px-5 py-2.5 text-right", e.performance.on_time_trend_points < 0 ? "text-critical" : "text-success")}>
                    {e.performance.on_time_trend_points > 0 ? "+" : ""}{e.performance.on_time_trend_points.toFixed(1)} pts
                  </td>
                </>
              ) : <td colSpan={3} className="px-5 py-2.5 text-right text-xs text-subtle">No history (new supplier)</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function NewsCard({ evidence }: { evidence: SupplierEvidence[] }) {
  const items = evidence.flatMap((e) => e.news.map((n) => ({ ...n, supplier: e.supplier_name })))
    .sort((a, b) => ["HIGH", "MEDIUM", "LOW", "POSITIVE"].indexOf(a.severity) - ["HIGH", "MEDIUM", "LOW", "POSITIVE"].indexOf(b.severity));
  return (
    <Card>
      <CardHeader icon={Newspaper} title="Supplier news" description="Capacity, quality, financial and disruption signals" />
      <ul className="divide-y divide-border">
        {items.map((n) => (
          <li key={n.headline} className="px-5 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={SEVERITY_TONE[n.severity]}>{n.severity === "POSITIVE" ? "Positive" : n.severity.toLowerCase()}</Badge>
              <span className="text-xs text-subtle">{n.supplier} · {n.source} · {n.date}</span>
            </div>
            <p className="mt-1 text-sm font-medium text-text">{n.headline}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ComplianceCard({ evidence }: { evidence: SupplierEvidence[] }) {
  const hits = evidence.filter((e) => e.sanctions_hits.length);
  return (
    <Card>
      <CardHeader icon={ShieldCheck} title="Compliance screening"
        description={`${evidence.length} suppliers screened against sanctions and export-control lists · ${hits.length} match${hits.length === 1 ? "" : "es"}`} />
      <div className="flex flex-wrap gap-2 px-5 py-4">
        {evidence.map((e) => (
          <Badge key={e.supplier_id} tone={e.sanctions_hits.length ? "critical" : "success"}>
            {e.sanctions_hits.length ? <Ban aria-hidden /> : <ShieldCheck aria-hidden />} {e.supplier_name}
          </Badge>
        ))}
      </div>
      {hits.map((e) => e.sanctions_hits.map((h) => (
        <p key={h.entity_id} className="border-t border-border px-5 py-3 text-sm text-text">
          <strong>{e.supplier_name}</strong> matches <strong>{h.listed_name}</strong> ({h.entity_id}) on the {h.list_name}: {h.program}, listed {h.listed_on}.
        </p>
      )))}
    </Card>
  );
}

function ProvidersCard({ providers }: { providers: Record<string, string> }) {
  const rows: { key: string; label: string; icon: LucideIcon; real: string }[] = [
    { key: "internal", label: "Approved vendors, KPIs", icon: Truck, real: "Your ERP data in BigQuery" },
    { key: "catalog", label: "Cross-references and offers", icon: PlugZap, real: "e.g. DigiKey / Mouser APIs" },
    { key: "sanctions", label: "Sanctions screening", icon: ShieldCheck, real: "e.g. OpenSanctions" },
    { key: "news", label: "Supplier news", icon: Newspaper, real: "e.g. news or web-search API" },
  ];
  return (
    <Card>
      <CardHeader icon={PlugZap} title="Data sources"
        description="External sources are mock connectors with fictional data for this demo. Each sits behind an interface that a production API can implement." />
      <ul className="grid gap-3 p-5 sm:grid-cols-2">
        {rows.map((r) => (
          <li key={r.key} className="flex items-start gap-2.5">
            <r.icon className="mt-0.5 size-4 shrink-0 text-subtle" aria-hidden />
            <div className="text-sm">
              <p className="font-medium text-text">{r.label}</p>
              <p className="text-xs text-subtle">{providers[r.key]}</p>
              <p className="text-xs text-muted">Production: {r.real}</p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Loading sourcing…" />}>
      <SourcingPage />
    </Suspense>
  );
}
