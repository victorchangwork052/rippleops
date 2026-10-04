"use client";

import { CircleDollarSign, Percent, TrendingDown, TriangleAlert } from "lucide-react";

import { Badge, Card, CardHeader, KpiCard, RiskBadge } from "@/components/ui";
import { money, moneyCompact, pct, pts, signedMoney } from "@/lib/format";
import type { ScenarioResult } from "@/lib/types";
import { cn } from "@/lib/utils";

import { MarginChart } from "./margin-chart";

export function ScenarioResults({ result }: { result: ScenarioResult }) {
  const s = result.summary;
  const threshold = result.inputs.margin_threshold;
  const drivers = s.driver_average_delta;

  return (
    <div className="fade-in space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Products Below Margin Target" icon={TriangleAlert} tone={s.products_below_margin_threshold ? "critical" : "neutral"}
          value={s.products_below_margin_threshold}
          context={`Target: ${pct(threshold, 0)} · ${s.products_newly_below_threshold} newly below`} />
        <KpiCard label="Average Unit Cost" icon={CircleDollarSign} value={signedMoney(s.average_unit_cost_delta)}
          context={`${money(s.average_current_unit_cost)} → ${money(s.average_scenario_unit_cost)} per product`} />
        <KpiCard label="Average Gross Margin" icon={Percent} tone="warning" value={pts(s.average_margin_delta_points)}
          context={`${pct(s.average_current_margin)} → ${pct(s.average_scenario_margin)}`} />
        <KpiCard label="Revenue at Risk" icon={TrendingDown} value={moneyCompact(s.revenue_at_risk)}
          context={`Forecast revenue of products below target, next ${s.horizon_months} months`} />
      </div>

      <Card>
        <CardHeader title="Compare to Current State" description={result.name} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Current state compared with the scenario</caption>
            <thead>
              <tr className="border-b border-border bg-surface-muted text-left text-xs text-subtle">
                <th scope="col" className="px-5 py-2 font-medium">Measure</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Current</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Scenario</th>
                <th scope="col" className="px-5 py-2 text-right font-medium">Change</th>
              </tr>
            </thead>
            <tbody className="num">
              <CompareRow label="Average unit cost" current={money(s.average_current_unit_cost)} scenario={money(s.average_scenario_unit_cost)} change={signedMoney(s.average_unit_cost_delta)} bad={s.average_unit_cost_delta > 0} />
              <CompareRow label="Average gross margin" current={pct(s.average_current_margin)} scenario={pct(s.average_scenario_margin)} change={pts(s.average_margin_delta_points)} bad={s.average_margin_delta_points < 0} />
              <CompareRow label={`Products below ${pct(threshold, 0)} target`} current={String(s.current_products_below_threshold)} scenario={String(s.products_below_margin_threshold)} change={`${s.products_below_margin_threshold - s.current_products_below_threshold >= 0 ? "+" : ""}${s.products_below_margin_threshold - s.current_products_below_threshold}`} bad={s.products_below_margin_threshold > s.current_products_below_threshold} />
              <CompareRow label={`Gross profit change, next ${s.horizon_months} months`} current="Baseline" scenario={signedMoney(-s.gross_profit_impact)} change={signedMoney(-s.gross_profit_impact)} bad={s.gross_profit_impact > 0} />
            </tbody>
          </table>
        </div>
        <div className="grid gap-3 border-t border-border px-5 py-4 text-sm sm:grid-cols-3">
          <Driver label="Component replacement" value={drivers.component_replacement} />
          <Driver label="Raw material" value={drivers.material} />
          <Driver label="Freight" value={drivers.freight} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Gross margin by product" description="Current vs scenario, sorted by scenario margin" />
        <div className="px-3 pb-3 pt-4"><MarginChart products={result.products} threshold={threshold} /></div>
      </Card>

      <Card>
        <CardHeader title="Product impact" description={`${s.product_count} products · cost changes attributed to replacement, material and freight`} />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <caption className="sr-only">Scenario results by product</caption>
            <thead>
              <tr className="border-b border-border bg-surface-muted text-left text-xs text-subtle">
                <th scope="col" className="px-5 py-2.5 font-medium">Product</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Unit cost</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Change</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Replacement / Material / Freight</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Current margin</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Scenario margin</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Change</th>
                <th scope="col" className="px-5 py-2.5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="num [&_td]:whitespace-nowrap">
              {result.products.map((p) => (
                <tr key={p.product_id} className={cn("border-b border-border last:border-0", p.below_threshold && "bg-critical-soft/40")}>
                  <td className="!whitespace-normal px-5 py-2.5">
                    <span className="font-semibold">{p.product_id}</span> {p.name}
                    <span className="block text-xs text-subtle">{p.effective_component_qty}× {result.part_id}</span>
                  </td>
                  <td className="px-3 py-2.5 text-right">{money(p.scenario_unit_cost)}</td>
                  <td className="px-3 py-2.5 text-right font-medium">{signedMoney(p.unit_cost_delta)}</td>
                  <td className="px-3 py-2.5 text-right text-xs text-muted">
                    {signedMoney(p.delta_breakdown.component_replacement)} / {signedMoney(p.delta_breakdown.material)} / {signedMoney(p.delta_breakdown.freight)}
                  </td>
                  <td className="px-3 py-2.5 text-right">{pct(p.current_margin)}</td>
                  <td className={cn("px-3 py-2.5 text-right font-semibold", p.below_threshold && "text-critical")}>{pct(p.scenario_margin)}</td>
                  <td className="px-3 py-2.5 text-right">{pts(p.margin_delta_points)}</td>
                  <td className="px-5 py-2.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <RiskBadge level={p.risk_level} />
                      {p.crosses_threshold && <Badge tone="critical">Falls below target</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function CompareRow({ label, current, scenario, change, bad }: { label: string; current: string; scenario: string; change: string; bad: boolean }) {
  return (
    <tr className="border-b border-border last:border-0">
      <th scope="row" className="px-5 py-2.5 text-left font-medium text-text">{label}</th>
      <td className="px-3 py-2.5 text-right text-muted">{current}</td>
      <td className="px-3 py-2.5 text-right font-semibold">{scenario}</td>
      <td className={cn("px-5 py-2.5 text-right font-semibold", bad ? "text-critical" : "text-success")}>{change}</td>
    </tr>
  );
}

function Driver({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-surface-muted px-3 py-2">
      <p className="text-xs text-subtle">{label}</p>
      <p className="num font-semibold">{signedMoney(value)} <span className="text-xs font-normal text-subtle">avg. per unit</span></p>
    </div>
  );
}
