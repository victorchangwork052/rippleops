"use client";

import {
  ArrowRight,
  Box,
  CalendarDays,
  CircleDollarSign,
  Factory,
  FlaskConical,
  GitBranch,
  ListChecks,
  Network,
  Radio,
  TriangleAlert,
  Warehouse,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import {
  ApprovalBadge,
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingState,
  RiskBadge,
  buttonVariants,
} from "@/components/ui";
import { AiExplanation } from "@/features/assistant/ai-explanation";
import { BomGraph, type GraphSelection } from "@/features/impact/bom-graph";
import { ProductPanel } from "@/features/impact/product-panel";
import { ProductTable } from "@/features/impact/product-table";
import { api } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import { EVENT_TYPE_LABEL, TRACE_METHOD_LABEL, date, days, money, moneyCompact, pts, signedPct } from "@/lib/format";
import type { ChangeEvent, ImpactAnalysis, RiskLevel } from "@/lib/types";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

const RISK_RANK: RiskLevel[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

async function loadWorkspace(eventId: string): Promise<{ event: ChangeEvent; analysis: ImpactAnalysis }> {
  const event = await api.event(eventId);
  const analysis = event.latest_analysis_id ? await api.impact(eventId) : await api.analyze(eventId);
  return { event, analysis };
}

function Workspace() {
  const params = useSearchParams();
  const { eventId: current, setEventId } = useCurrentEvent();
  const eventId = params.get("event") ?? current;
  const ws = useLoad(eventId ? () => loadWorkspace(eventId) : null, eventId ?? "none");
  const initialProduct = params.get("product");
  const [selection, setSelection] = useState<GraphSelection | null>(
    initialProduct ? { nodeId: initialProduct.toUpperCase(), itemType: "FINISHED_GOOD" } : null,
  );

  useEffect(() => {
    if (eventId && eventId !== current) setEventId(eventId);
  }, [eventId, current, setEventId]);

  if (!eventId) {
    return (
      <Card>
        <EmptyState icon={Network} title="No change event selected"
          description="Upload a supplier notice or load the demo scenario to see how RippleOps maps business impact."
          actions={<Link href="/events/new" className={buttonVariants()}>Analyze a Change</Link>} />
      </Card>
    );
  }
  if (ws.loading) return <Card><LoadingState label="Tracing dependencies and calculating impact…" /></Card>;
  if (ws.error || !ws.data) {
    return <ErrorState title="We couldn't load this analysis" message={ws.error ?? "Unknown error"}
      action={<Link href="/events" className={buttonVariants({ variant: "secondary", size: "sm" })}>Back to events</Link>} />;
  }

  const { event, analysis } = ws.data;
  return <WorkspaceView event={event} analysis={analysis} selection={selection} onSelect={setSelection} />;
}

function WorkspaceView({ event, analysis, selection, onSelect }: {
  event: ChangeEvent;
  analysis: ImpactAnalysis;
  selection: GraphSelection | null;
  onSelect: (s: GraphSelection | null) => void;
}) {
  const s = analysis.summary;
  const part = analysis.component.part_id;
  const overall = RISK_RANK.find((l) => s.risk_counts[l] > 0) ?? "LOW";
  const selectedProduct = useMemo(
    () => (selection?.itemType === "FINISHED_GOOD" ? analysis.products.find((p) => p.product_id === selection.nodeId) ?? null : null),
    [analysis, selection],
  );
  const recommended = analysis.alternatives.find((a) => a.recommended);
  const { setProductInView } = useCurrentEvent();
  useEffect(() => {
    setProductInView(selectedProduct?.product_id ?? null);
    return () => setProductInView(null);
  }, [selectedProduct, setProductInView]);
  const q = `?event=${encodeURIComponent(event.event_id)}`;

  return (
    <div className="space-y-5">
      {/* Event header */}
      <Card className="fade-in px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-subtle">
              <Radio className="size-3.5" aria-hidden /> {EVENT_TYPE_LABEL[event.event_type]} · {event.event_id}
            </div>
            <h1 className="mt-1.5 flex flex-wrap items-center gap-3 text-[28px] font-semibold tracking-tight">
              {part} {event.event_type === "COMPONENT_EOL" ? "End-of-Life" : EVENT_TYPE_LABEL[event.event_type]}
              <RiskBadge level={overall} suffix=" Risk" />
            </h1>
            <p className="mt-1 text-sm text-muted">{analysis.component.name} · {analysis.component.supplier_name}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/scenarios${q}`} className={buttonVariants({ variant: "secondary" })}>
              <FlaskConical aria-hidden /> Run Scenario
            </Link>
            <Link href={`/actions${q}`} className={buttonVariants()}>
              <ListChecks aria-hidden /> Recommended Response
            </Link>
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-border pt-4 text-sm sm:grid-cols-3 lg:grid-cols-5">
          <Detail icon={Factory} label="Supplier" value={analysis.component.supplier_name ?? "Unknown"} />
          <Detail icon={CalendarDays} label="Last time buy" value={date(event.last_time_buy_date)} />
          <Detail icon={CalendarDays} label="Last ship date" value={date(event.last_ship_date)} />
          <Detail icon={GitBranch} label="Recommended replacement" value={event.recommended_alternative_item_id ?? "None provided"} />
          <Detail icon={Warehouse} label={`${part} available`} value={`${Math.round(s.component_available_qty).toLocaleString("en-US")} units`} />
        </dl>
      </Card>

      {/* Graph + business impact */}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="flex min-h-[560px] flex-col overflow-hidden">
          <CardHeader icon={Network} title="Dependency Map"
            description={`Every path from ${part} to a finished product. Select a product to trace it.`}
            action={<Badge tone="neutral">{TRACE_METHOD_LABEL[analysis.trace_method] ?? analysis.trace_method}</Badge>} />
          <div className="relative h-[560px] flex-1 bg-surface-muted/60">
            <BomGraph analysis={analysis} selection={selection} onSelect={onSelect} />
          </div>
        </Card>

        <Card className="flex max-h-[680px] flex-col overflow-hidden">
          {selectedProduct ? (
            <ProductPanel analysis={analysis} product={selectedProduct} onClose={() => onSelect(null)}>
              <AiExplanation eventId={event.event_id} productId={selectedProduct.product_id} />
            </ProductPanel>
          ) : (
            <>
              <CardHeader title="Business Impact" description={`Next ${s.horizon_months} months from ${date(s.horizon_start)}`} />
              <div className="space-y-3 overflow-y-auto p-4">
                <KpiCard label="Affected SKUs" icon={Box} tone="critical" value={s.affected_product_count}
                  context={`Across ${s.product_family_count} product families`} />
                <KpiCard label="Revenue Exposure" icon={CircleDollarSign} value={moneyCompact(s.revenue_exposure)}
                  context={`Forecast revenue, next ${s.horizon_months} months`} />
                <KpiCard label="Inventory Coverage" icon={Warehouse} tone={s.inventory_coverage_days < 90 ? "warning" : "neutral"}
                  value={days(s.inventory_coverage_days)} context={`${part} stock, based on current forecast`} />
                <KpiCard label="No Approved Alternative" icon={TriangleAlert} tone="warning" value={s.products_without_approved_alternative}
                  context={recommended ? `Products where ${recommended.part_id} still needs validation` : "Products without an approved alternative"} />
              </div>
            </>
          )}
        </Card>
      </div>

      {/* Alternatives */}
      {analysis.alternatives.length > 0 && (
        <Card>
          <CardHeader icon={GitBranch} title="Approved Alternatives"
            description={`Replacement options for ${part}, compared on the same ${s.affected_product_count} products`} />
          <div className="grid gap-3 p-4 md:grid-cols-2">
            {analysis.alternatives.map((a) => (
              <div key={a.part_id} className={cn("rounded-xl border p-4", a.recommended ? "border-primary-border bg-primary-soft/40" : "border-border")}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{a.part_id} {a.recommended && <Badge tone="primary" className="ml-1">Recommended by supplier</Badge>}</p>
                    <p className="text-xs text-subtle">{a.name} · {a.supplier_name}</p>
                  </div>
                  <ApprovalBadge status={a.default_approval} />
                </div>
                <dl className="num mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-4">
                  <Stat label="Unit price" value={a.unit_price != null ? money(a.unit_price) : "—"}
                    sub={a.unit_price_delta_pct != null ? `${signedPct(a.unit_price_delta_pct)} vs ${part}` : undefined} />
                  <Stat label="Avg. unit cost" value={`+${money(a.average_unit_cost_delta)}`} sub="per product" />
                  <Stat label="Avg. margin" value={pts(a.average_margin_delta_points)} sub={`${a.products_below_margin_threshold} below target`} />
                  <Stat label="Approved for" value={`${a.approved_products} of ${s.affected_product_count}`}
                    sub={a.max_qualification_lead_time_days ? `${a.max_qualification_lead_time_days}-day qualification` : "No qualification needed"} />
                </dl>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Affected products */}
      <Card>
        <CardHeader icon={Box} title="Affected Products"
          description={`${s.affected_product_count} finished products use ${part}. Select a row to see its dependency path.`}
          action={
            <Link href={`/scenarios${q}`} className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
              Simulate replacement <ArrowRight className="size-4" aria-hidden />
            </Link>
          } />
        <ProductTable products={analysis.products} partId={part} threshold={s.margin_threshold}
          selectedId={selectedProduct?.product_id ?? null}
          onSelect={(id) => {
            onSelect({ nodeId: id, itemType: "FINISHED_GOOD" });
            window.scrollTo({ top: 0, behavior: "smooth" });
          }} />
      </Card>
      <p className="text-xs text-subtle">
        Figures are calculated deterministically from {analysis.data_source === "bigquery" ? "BigQuery" : "the seeded demo dataset"} as of {date(analysis.as_of_date)} (analysis {analysis.analysis_id}).
      </p>
    </div>
  );
}

function Detail({ icon: Icon, label, value }: { icon: typeof Factory; label: string; value: string }) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-xs text-subtle"><Icon className="size-3.5" aria-hidden />{label}</dt>
      <dd className="mt-0.5 font-medium text-text">{value}</dd>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="font-semibold text-text">{value}</dd>
      {sub && <dd className="text-[11.5px] text-subtle">{sub}</dd>}
    </div>
  );
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading analysis…" />}>
      <Workspace />
    </Suspense>
  );
}
