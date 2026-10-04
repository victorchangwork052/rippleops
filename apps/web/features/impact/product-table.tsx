"use client";

import { ApprovalBadge, RiskBadge } from "@/components/ui";
import { days, money, moneyCompact, pct } from "@/lib/format";
import type { ProductImpact } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ProductTable({ products, partId, selectedId, onSelect, threshold }: {
  products: ProductImpact[];
  partId: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
  threshold: number;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[960px] text-sm">
        <caption className="sr-only">Finished products that use {partId}, sorted by risk</caption>
        <thead>
          <tr className="border-b border-border bg-surface-muted text-left text-xs font-medium text-subtle">
            <th scope="col" className="px-5 py-2.5 font-medium">Product</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Usage per unit</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Unit cost</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Gross margin</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Revenue exposure</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Coverage</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Alternative</th>
            <th scope="col" className="px-5 py-2.5 font-medium">Risk</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <tr
              key={p.product_id}
              onClick={() => onSelect(p.product_id)}
              className={cn("cursor-pointer border-b border-border last:border-0 hover:bg-surface-muted",
                selectedId === p.product_id && "bg-primary-soft hover:bg-primary-soft")}
            >
              <td className="px-5 py-2.5">
                <button type="button" className="text-left" onClick={(e) => { e.stopPropagation(); onSelect(p.product_id); }}
                  aria-label={`Show details for ${p.product_id} ${p.name}`}>
                  <span className="font-semibold text-text">{p.product_id}</span>{" "}
                  <span className="text-text">{p.name}</span>
                  <span className="block text-xs text-subtle">{p.product_family}</span>
                </button>
              </td>
              <td className="num px-3 py-2.5 text-right">
                <span className="font-semibold">{p.effective_component_qty}×</span>
                <span className="block text-xs text-subtle">{p.paths_to_component} path{p.paths_to_component > 1 ? "s" : ""}</span>
              </td>
              <td className="num px-3 py-2.5 text-right">{money(p.unit_cost)}</td>
              <td className={cn("num px-3 py-2.5 text-right", p.current_margin < threshold + 0.02 && "font-semibold text-high")}>
                {pct(p.current_margin)}
              </td>
              <td className="num px-3 py-2.5 text-right">{moneyCompact(p.revenue_exposure)}</td>
              <td className="num px-3 py-2.5 text-right">{days(p.inventory_coverage_days)}</td>
              <td className="px-3 py-2.5"><ApprovalBadge status={p.alternative?.approval_status} /></td>
              <td className="px-5 py-2.5"><RiskBadge level={p.risk_level} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
