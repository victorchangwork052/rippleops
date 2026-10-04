"use client";

import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { pct, pts } from "@/lib/format";
import type { ScenarioProduct } from "@/lib/types";

/** Current vs scenario gross margin per product, with the target as a reference line. */
export function MarginChart({ products, threshold }: { products: ScenarioProduct[]; threshold: number }) {
  const data = [...products]
    .sort((a, b) => a.scenario_margin - b.scenario_margin)
    .map((p) => ({
      id: p.product_id,
      name: p.name,
      current: +(p.current_margin * 100).toFixed(2),
      scenario: +(p.scenario_margin * 100).toFixed(2),
      delta: p.margin_delta_points,
      below: p.below_threshold,
    }));
  const min = Math.floor(Math.min(threshold * 100, ...data.map((d) => d.scenario)) / 5) * 5 - 5;
  const max = Math.ceil(Math.max(...data.map((d) => d.current)) / 5) * 5;
  const lo = Math.max(min, 0);
  const ticks = Array.from({ length: (max - lo) / 5 + 1 }, (_, i) => lo + i * 5);

  return (
    <figure>
      <div className="h-[300px]" role="img" aria-label={`Bar chart of current and scenario gross margin for ${data.length} products against a ${pct(threshold, 0)} target. Details are listed in the table below.`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 72, bottom: 0, left: -8 }} barGap={2} barCategoryGap="22%">
            <CartesianGrid vertical={false} stroke="#eaecf0" />
            <XAxis dataKey="id" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} />
            <YAxis domain={[lo, max]} ticks={ticks} tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={false}
              tick={{ fontSize: 12, fill: "#667085" }} width={48} />
            <Tooltip
              cursor={{ fill: "rgba(79,70,229,0.06)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as (typeof data)[number];
                return (
                  <div className="rounded-lg border border-border bg-white px-3 py-2 text-xs shadow-md">
                    <p className="font-semibold text-text">{d.id} {d.name}</p>
                    <p className="num mt-1 text-muted">Current {d.current.toFixed(1)}% → Scenario {d.scenario.toFixed(1)}%</p>
                    <p className="num text-muted">Change {pts(d.delta)}{d.below ? " · below target" : ""}</p>
                  </div>
                );
              }}
            />
            <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12, color: "#475467" }} />
            <ReferenceLine y={threshold * 100} stroke="#b42318" strokeDasharray="5 4"
              label={{ value: `Target ${pct(threshold, 0)}`, position: "right", fill: "#b42318", fontSize: 11 }} />
            <Bar dataKey="current" name="Current margin" fill="#c7d2fe" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="scenario" name="Scenario margin" fill="#4f46e5" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
