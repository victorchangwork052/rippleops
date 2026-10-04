"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { qty } from "@/lib/format";
import type { LineWeekLoad, MaterialPlan, ProductForecast } from "@/lib/types";
import { cn } from "@/lib/utils";

const AXIS = { fontSize: 12, fill: "#667085" };
const monthLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", year: "2-digit" });
export const weekLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

/** Shipment history, the demand plan and the statistical forecast with its interval. */
export function ForecastChart({ product }: { product: ProductForecast }) {
  const history = product.history.slice(-12).map((h) => ({ month: h.month, actual: h.qty }));
  const future = product.points.map((p) => ({
    month: p.month, plan: p.plan_qty, forecast: p.forecast_qty, band: [p.lower, p.upper] as [number, number],
  }));
  const data = [...history, ...future];
  return (
    <div className="h-[260px]" role="img"
      aria-label={`Monthly demand for ${product.product_id}: last 12 months shipped, then plan and statistical forecast for ${future.length} months.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
          <CartesianGrid vertical={false} stroke="#eaecf0" />
          <XAxis dataKey="month" tickFormatter={monthLabel} tickLine={false} axisLine={false} tick={AXIS} interval={1} />
          <YAxis tickLine={false} axisLine={false} tick={AXIS} width={48} />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as Record<string, number | [number, number]>;
              return (
                <div className="rounded-lg border border-border bg-white px-3 py-2 text-xs shadow-md">
                  <p className="font-semibold text-text">{monthLabel(String(label))}</p>
                  {"actual" in d && <p className="num text-muted">Shipped {qty(d.actual as number)}</p>}
                  {"plan" in d && <p className="num text-muted">Plan {qty(d.plan as number)}</p>}
                  {"forecast" in d && <p className="num text-muted">Forecast {qty(d.forecast as number)} ({qty((d.band as [number, number])[0])}–{qty((d.band as [number, number])[1])})</p>}
                </div>
              );
            }}
          />
          <Legend iconSize={10} wrapperStyle={{ fontSize: 12, color: "#475467" }} />
          <Area dataKey="band" name="Forecast interval" fill="#c7d2fe" fillOpacity={0.5} stroke="none" isAnimationActive={false} />
          <Line dataKey="actual" name="Shipped" stroke="#98a2b3" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="plan" name="Demand plan" stroke="#475467" strokeDasharray="5 4" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="forecast" name="Statistical forecast" stroke="#4f46e5" strokeWidth={2.25} dot={{ r: 2.5 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Projected component stock by week at plan and at the statistical forecast. */
export function RunwayChart({ materials }: { materials: MaterialPlan }) {
  const data = materials.weeks.map((w) => ({ week: w.week, plan: w.projected_available, forecast: w.projected_available_forecast }));
  return (
    <div className="h-[240px]" role="img"
      aria-label={`Projected ${materials.part_id} stock by week. It runs out the week of ${materials.stockout_week ? weekLabel(materials.stockout_week) : "after the horizon"}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="#eaecf0" />
          <XAxis dataKey="week" tickFormatter={weekLabel} tickLine={false} axisLine={false} tick={AXIS} interval={1} />
          <YAxis tickLine={false} axisLine={false} tick={AXIS} width={56} tickFormatter={(v) => qty(v)} />
          <Tooltip formatter={(v) => qty(Number(v))} labelFormatter={(l) => `Week of ${weekLabel(String(l))}`} />
          <Legend iconSize={10} wrapperStyle={{ fontSize: 12, color: "#475467" }} />
          <ReferenceLine y={0} stroke="#b42318" strokeDasharray="5 4" label={{ value: "Out of stock", position: "insideBottomLeft", fill: "#b42318", fontSize: 11 }} />
          {materials.stockout_week && <ReferenceLine x={materials.stockout_week} stroke="#b42318" />}
          <Line dataKey="plan" name="At demand plan" stroke="#4f46e5" strokeWidth={2.25} dot={false} isAnimationActive={false} />
          <Line dataKey="forecast" name="At statistical forecast" stroke="#c4320a" strokeDasharray="5 4" strokeWidth={2} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function cellTone(u: number): string {
  if (u > 1.0001) return "bg-critical text-white";
  if (u >= 0.97) return "bg-warning-soft text-warning";
  if (u >= 0.75) return "bg-primary-soft text-primary";
  return "bg-surface-muted text-muted";
}

/** Line utilization by week; over 100% means work that cannot be built that week. */
export function LineHeatmap({ loads, lines, weeks }: { loads: LineWeekLoad[]; lines: Record<string, string>; weeks: string[] }) {
  const by = new Map(loads.map((l) => [`${l.line_id}|${l.week}`, l]));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="w-44 text-left font-medium text-muted">Line</th>
            {weeks.map((w) => <th key={w} className="font-medium text-subtle">{weekLabel(w)}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(lines).sort().map((line) => (
            <tr key={line}>
              <th className="text-left font-medium text-text">{lines[line]}</th>
              {weeks.map((w) => {
                const l = by.get(`${line}|${w}`);
                const u = l?.utilization ?? 0;
                return (
                  <td key={w} className={cn("num rounded-md px-1 py-1.5 text-center font-medium", cellTone(u))}
                    title={l ? `${lines[line]}, week of ${weekLabel(w)}: ${qty(l.planned_hours)} of ${qty(l.capacity_hours)} hours` : undefined}>
                    {Math.round(u * 100)}%
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
