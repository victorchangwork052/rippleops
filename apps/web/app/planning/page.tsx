"use client";

import { CalendarRange, CircleCheck, Cpu, Factory, Play, ThumbsDown, ThumbsUp, TrendingUp, UserCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, buttonVariants, inputClass } from "@/components/ui";
import { AgentFindings } from "@/features/agents/agent-findings";
import { ForecastChart, LineHeatmap, RunwayChart, weekLabel } from "@/features/planning/charts";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import { moneyCompact, pct, qty } from "@/lib/format";
import type { PlanKpis, PlanningView, PlanStatus, ProductionPlan, WorkflowRun } from "@/lib/types";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<PlanStatus, { label: string; tone: "neutral" | "warning" | "success" | "critical" }> = {
  DRAFT: { label: "Draft", tone: "neutral" },
  PROPOSED: { label: "Awaiting approval", tone: "warning" },
  APPROVED: { label: "Approved", tone: "success" },
  REJECTED: { label: "Rejected", tone: "critical" },
};

async function load(eventId: string): Promise<{ view: PlanningView; run: WorkflowRun | null }> {
  const [view, run] = await Promise.all([api.planning(eventId), api.workflow(eventId)]);
  return { view, run };
}

function PlanningPage() {
  const params = useSearchParams();
  const { eventId: current, setEventId } = useCurrentEvent();
  const eventId = params.get("event") ?? current;
  const data = useLoad(eventId ? () => load(eventId) : null, eventId ?? "");
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (eventId && eventId !== current) setEventId(eventId);
  }, [eventId, current, setEventId]);

  const header = (
    <PageHeader title="Production Plan"
      description="Demand forecast, component runway and a 13-week re-plan from the Google OR-Tools optimizer. Agents propose; a person approves." />
  );
  if (!eventId) {
    return (
      <div className="space-y-6">{header}
        <Card><EmptyState icon={Factory} title="No change event selected" description="Analyze a component change to re-plan production around it."
          actions={<Link href="/events/new" className={buttonVariants()}>Analyze a Change</Link>} /></Card>
      </div>
    );
  }
  if (data.loading) return <div className="space-y-6">{header}<Card><LoadingState label="Forecasting demand and optimizing the plan…" /></Card></div>;
  if (data.error || !data.data) return <div className="space-y-6">{header}<ErrorState message={data.error ?? "No data"} /></div>;

  const { view, run } = data.data;
  const plans = view.plans;
  const plan = plans.find((p) => p.plan_id === (selected ?? view.proposed_plan_id)) ?? plans[0];

  function replace(p: ProductionPlan) {
    if (!data.data) return;
    const others = data.data.view.plans.filter((x) => x.plan_id !== p.plan_id).map((x) =>
      p.status === "PROPOSED" && x.status === "PROPOSED" ? { ...x, status: "DRAFT" as const } : x);
    const all = [...others, p].sort((a, b) => a.plan_id.localeCompare(b.plan_id));
    data.setData({ ...data.data, view: { ...data.data.view, plans: all,
      proposed_plan_id: p.status === "PROPOSED" || p.status === "APPROVED" ? p.plan_id : data.data.view.proposed_plan_id } });
    setSelected(p.plan_id);
  }

  return (
    <div className="space-y-6">
      {header}
      <PlanPicker plans={plans} selected={plan.plan_id} onSelect={setSelected} eventId={eventId} onNewPlan={replace} />
      <ApprovalCard plan={plan} onChange={replace} />
      <KpiCompare base={plan.baseline} opt={plan.optimized} plan={plan} />

      <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHeader icon={CalendarRange} title="What changes" description={`${plan.label} · ${plan.weeks.length} weeks from ${weekLabel(plan.weeks[0])}`} />
          <ul className="divide-y divide-border">
            {plan.changes.map((c, i) => (
              <li key={i} className="flex items-start gap-3 px-5 py-3">
                <Badge tone={c.kind === "UNMET_DEMAND" ? "critical" : c.kind === "BRIDGE_BUY" ? "warning" : "primary"}>
                  {c.kind.replaceAll("_", " ").toLowerCase()}
                </Badge>
                <p className="text-sm text-text">{c.description}</p>
              </li>
            ))}
          </ul>
        </Card>
        <AgentFindings run={run} agents={["demand_planner", "production_planner"]} title="Planning agents" />
      </div>

      <HeatmapCard plan={plan} />

      <div className="grid gap-5 xl:grid-cols-2">
        <ForecastCard view={view} />
        <Card>
          <CardHeader icon={Cpu} title={`${view.materials.part_id} runway`}
            description={`${qty(view.materials.available_qty)} available · runs out ${view.materials.stockout_week ? `the week of ${weekLabel(view.materials.stockout_week)}` : "after the horizon"} if nothing changes`} />
          <div className="px-3 py-4"><RunwayChart materials={view.materials} /></div>
        </Card>
      </div>

      <ProductTable plan={plan} />
      <p className="num text-xs text-subtle">
        {plan.solver.name} · {plan.solver.status === "OPTIMAL" ? `optimal within ${pct(plan.solver.gap_limit, 2)}` : plan.solver.status.toLowerCase()} ·{" "}
        {qty(plan.solver.variables)} decision variables · {qty(plan.solver.constraints)} constraints · solved in {(plan.solver.solve_ms / 1000).toFixed(2)} s.
        Margin is gross margin on units built in the horizon, after any broker premium.
      </p>
    </div>
  );
}

function PlanPicker({ plans, selected, onSelect, eventId, onNewPlan }: {
  plans: ProductionPlan[]; selected: string; onSelect: (id: string) => void; eventId: string; onNewPlan: (p: ProductionPlan) => void;
}) {
  const [bridge, setBridge] = useState("1000");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      onNewPlan(await api.optimize(eventId, Math.max(0, Math.round(Number(bridge) || 0))));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-wrap items-end gap-4 px-5 py-4">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted">Plans</p>
        <div className="mt-1.5 flex flex-wrap gap-2" role="tablist" aria-label="Production plans">
          {plans.map((p) => (
            <button key={p.plan_id} role="tab" aria-selected={p.plan_id === selected} onClick={() => onSelect(p.plan_id)}
              className={cn("rounded-lg border px-3 py-1.5 text-left text-sm transition-colors",
                p.plan_id === selected ? "border-primary bg-primary-soft text-primary" : "border-border hover:bg-surface-muted")}>
              <span className="font-medium">{p.inputs.bridge_buy_qty ? `Bridge buy ${qty(p.inputs.bridge_buy_qty)}` : "No bridge buy"}</span>
              <span className="ml-2 text-xs text-subtle">{p.plan_id}</span>
              {p.status !== "DRAFT" && <Badge tone={STATUS_BADGE[p.status].tone} className="ml-2">{STATUS_BADGE[p.status].label}</Badge>}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-end gap-2">
        <label className="text-xs font-medium text-muted" htmlFor="bridge-qty">
          What-if: bridge buy (units)
          <input id="bridge-qty" type="number" min={0} step={500} value={bridge} onChange={(e) => setBridge(e.target.value)}
            className={cn(inputClass, "mt-1.5 w-36")} />
        </label>
        <Button variant="secondary" onClick={run} disabled={busy}><Play aria-hidden /> {busy ? "Optimizing…" : "Run Optimizer"}</Button>
      </div>
      {error && <p role="alert" className="w-full text-sm text-critical">{error}</p>}
    </Card>
  );
}

function ApprovalCard({ plan, onChange }: { plan: ProductionPlan; onChange: (p: ProductionPlan) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(fn: () => Promise<ProductionPlan>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await fn());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (plan.status === "APPROVED" || plan.status === "REJECTED") {
    const ok = plan.status === "APPROVED";
    return (
      <div className={cn("flex items-center gap-3 rounded-xl border p-4", ok ? "border-success-border bg-success-soft" : "border-critical-border bg-critical-soft")}>
        {ok ? <CircleCheck className="size-5 text-success" aria-hidden /> : <ThumbsDown className="size-5 text-critical" aria-hidden />}
        <p className="text-sm text-text"><strong>{plan.plan_id} {ok ? "approved" : "rejected"}</strong> by {plan.decided_by}
          {plan.decided_at ? ` on ${new Date(plan.decided_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}` : ""}.
          {ok ? " The plan is released to the lines." : ""}</p>
      </div>
    );
  }
  return (
    <Card className={cn("px-5 py-4", plan.status === "PROPOSED" && "border-warning-border")}>
      <div className="flex flex-wrap items-center gap-4">
        <UserCheck className="size-5 text-warning" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-text">
            {plan.status === "PROPOSED" ? "The Production Planner agent proposed this plan. It needs your approval." : "This plan is a draft."}
          </p>
          {plan.proposal_note && <p className="mt-0.5 text-sm text-muted">&ldquo;{plan.proposal_note}&rdquo;</p>}
        </div>
        {plan.status === "PROPOSED" ? (
          <div className="flex gap-2">
            <Button variant="secondary" disabled={busy} onClick={() => act(() => api.decidePlan(plan.plan_id, "REJECTED"))}><ThumbsDown aria-hidden /> Reject</Button>
            <Button disabled={busy} onClick={() => act(() => api.decidePlan(plan.plan_id, "APPROVED"))}><ThumbsUp aria-hidden /> Approve Plan</Button>
          </div>
        ) : (
          <Button variant="secondary" disabled={busy} onClick={() => act(() => api.proposePlan(plan.plan_id))}>Propose for Approval</Button>
        )}
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-critical">{error}</p>}
    </Card>
  );
}

const millions = (x: number) => `$${(x / 1_000_000).toFixed(2)}M`;

function KpiCompare({ base, opt, plan }: { base: PlanKpis; opt: PlanKpis; plan: ProductionPlan }) {
  const tiles = [
    { label: "Affected-product fill rate", now: pct(base.affected_fill_rate), next: pct(opt.affected_fill_rate), good: opt.affected_fill_rate >= base.affected_fill_rate },
    { label: "Strategic-customer fill rate", now: pct(base.strategic_fill_rate), next: pct(opt.strategic_fill_rate), good: opt.strategic_fill_rate >= base.strategic_fill_rate },
    { label: "Late unit-weeks", now: qty(base.late_unit_weeks), next: qty(opt.late_unit_weeks), good: opt.late_unit_weeks <= base.late_unit_weeks },
    { label: "Gross margin (13 weeks)", now: millions(base.gross_margin), next: millions(opt.gross_margin), good: opt.gross_margin >= base.gross_margin,
      note: opt.bridge_premium ? `after ${moneyCompact(opt.bridge_premium)} broker premium` : undefined },
    { label: `${plan.inputs.part_id} used`, now: qty(base.component_used), next: qty(opt.component_used),
      note: `${plan.inputs.alternative_part_id ?? "Alternative"}: ${qty(opt.alternative_used)} units` },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-xl border border-border bg-surface p-4">
          <p className="text-[13px] font-medium text-muted">{t.label}</p>
          <p className={cn("num mt-2 text-[26px] font-semibold leading-none", t.good === false ? "text-critical" : "text-text")}>{t.next}</p>
          <p className="num mt-1.5 text-xs text-subtle">Current schedule: {t.now}</p>
          {t.note && <p className="mt-0.5 text-xs text-subtle">{t.note}</p>}
        </div>
      ))}
    </div>
  );
}

function HeatmapCard({ plan }: { plan: ProductionPlan }) {
  const [mode, setMode] = useState<"optimized" | "current">("optimized");
  return (
    <Card>
      <CardHeader icon={Factory} title="Line utilization"
        description={mode === "current" ? "Work orders as currently scheduled. Over 100% means the line cannot build it that week." : "After re-planning: load moved to the flex line and capacity respected."}
        action={
          <div className="flex rounded-lg border border-border p-0.5 text-sm" role="tablist" aria-label="Schedule">
            {(["current", "optimized"] as const).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                className={cn("rounded-md px-3 py-1", mode === m ? "bg-primary text-white" : "text-muted hover:text-text")}>
                {m === "current" ? "Current schedule" : "Optimized"}
              </button>
            ))}
          </div>
        } />
      <div className="p-4">
        <LineHeatmap loads={mode === "current" ? plan.baseline_line_loads : plan.line_loads} lines={plan.lines} weeks={plan.weeks} />
      </div>
    </Card>
  );
}

function ForecastCard({ view }: { view: PlanningView }) {
  const products = view.forecast.products;
  const top = [...products].sort((a, b) => b.delta_pct - a.delta_pct)[0];
  const [pid, setPid] = useState(top?.product_id ?? "");
  const product = products.find((p) => p.product_id === pid) ?? top;
  if (!product) return null;
  return (
    <Card>
      <CardHeader icon={TrendingUp} title="Demand forecast"
        description={`${view.forecast.model} · ${pct(view.forecast.confidence_level, 0)} interval`}
        action={
          <select aria-label="Product" className={cn(inputClass, "h-8 w-auto")} value={product.product_id} onChange={(e) => setPid(e.target.value)}>
            {products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_id} ({p.delta_pct > 0 ? "+" : ""}{pct(p.delta_pct)} vs plan)</option>)}
          </select>
        } />
      <div className="px-3 py-4"><ForecastChart product={product} /></div>
      {view.forecast.notice && <p className="px-5 pb-3 text-xs text-subtle">{view.forecast.notice}</p>}
    </Card>
  );
}

function ProductTable({ plan }: { plan: ProductionPlan }) {
  const rows = plan.products.filter((r) => r.affected);
  return (
    <Card>
      <CardHeader icon={Cpu} title="Affected products" description="Units over the 13-week horizon" />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-surface-muted text-left text-xs font-medium text-muted">
            <tr>
              <th className="px-5 py-2.5">Product</th>
              <th className="px-3 py-2.5 text-right">Demand</th>
              <th className="px-3 py-2.5 text-right">Current schedule</th>
              <th className="px-3 py-2.5 text-right">Optimized</th>
              <th className="px-3 py-2.5 text-right">With {plan.inputs.alternative_part_id ?? "alternative"}</th>
              <th className="px-3 py-2.5 text-right">On flex line</th>
              <th className="px-5 py-2.5 text-right">Unmet</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.product_id} className="border-t border-border">
                <td className="px-5 py-2.5">
                  <span className="font-semibold text-text">{r.product_id}</span> <span className="text-muted">{r.name}</span>
                  {r.strategic && <Badge tone="primary" className="ml-2">Strategic</Badge>}
                  <p className="text-xs text-subtle">{r.alternative_from_week ? `Alternative allowed from ${weekLabel(r.alternative_from_week)}` : "No approved alternative"}</p>
                </td>
                <td className="num px-3 py-2.5 text-right">{qty(r.demand)}</td>
                <td className={cn("num px-3 py-2.5 text-right", r.baseline_built < r.demand && "text-critical")}>{qty(r.baseline_built)}</td>
                <td className="num px-3 py-2.5 text-right font-semibold">{qty(r.built)}</td>
                <td className="num px-3 py-2.5 text-right">{qty(r.built_with_alternative)}</td>
                <td className="num px-3 py-2.5 text-right">{qty(r.built_on_alternate_line)}</td>
                <td className={cn("num px-5 py-2.5 text-right", r.unmet > 0 ? "font-semibold text-critical" : "text-subtle")}>{qty(r.unmet)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Loading the production plan…" />}>
      <PlanningPage />
    </Suspense>
  );
}
