"use client";

import { ArrowDown, Box, Boxes, Cpu, Warehouse, X } from "lucide-react";
import type { ReactNode } from "react";

import { ApprovalBadge, Button, RiskBadge } from "@/components/ui";
import { days, money, pct, pts } from "@/lib/format";
import type { ImpactAnalysis, ProductImpact } from "@/lib/types";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-border px-5 py-4">
      <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-subtle">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5 text-sm">
      <span className="text-muted">{label}</span>
      <span className="num font-medium text-text">{value}</span>
    </div>
  );
}

export function ProductPanel({ analysis, product, onClose, children }: {
  analysis: ImpactAnalysis;
  product: ProductImpact;
  onClose: () => void;
  children?: ReactNode; // AI explanation slot
}) {
  const part = analysis.component.part_id;
  const paths = analysis.paths.filter((p) => p.product_id === product.product_id);
  const componentDays = analysis.summary.inventory_coverage_days;
  const repMarginDelta = product.replacement_margin != null ? (product.replacement_margin - product.current_margin) * 100 : null;

  return (
    <div className="fade-in flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Box className="size-4 text-primary" aria-hidden />
            <span className="text-xs font-medium text-subtle">{product.product_family}</span>
          </div>
          <h2 className="mt-1 text-lg font-semibold leading-tight">
            {product.product_id} <span className="font-normal text-muted">{product.name}</span>
          </h2>
          <div className="mt-2"><RiskBadge level={product.risk_level} suffix=" risk" /></div>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close product details" onClick={onClose}><X aria-hidden /></Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <Section title="Why this product is at risk">
          <ul className="space-y-1.5 text-sm text-text">
            {product.risk_reasons.map((r) => (
              <li key={r} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-subtle" aria-hidden />{r}</li>
            ))}
          </ul>
          {children}
        </Section>

        <Section title={`Dependency path${paths.length > 1 ? "s" : ""}`}>
          <div className="space-y-3">
            {paths.map((p, i) => (
              <div key={i} className="rounded-lg border border-border bg-surface-muted p-3">
                <ol className="space-y-0.5" aria-label={`Path ${i + 1}`}>
                  {p.nodes.map((n, j) => {
                    const Icon = j === 0 ? Box : j === p.nodes.length - 1 ? Cpu : Boxes;
                    return (
                      <li key={n}>
                        <div className="flex items-center gap-2 text-sm">
                          <Icon className={j === p.nodes.length - 1 ? "size-4 text-critical" : "size-4 text-subtle"} aria-hidden />
                          <span className="font-medium">{n}</span>
                        </div>
                        {j < p.edge_qtys.length && (
                          <div className="num ml-[7px] flex items-center gap-1.5 border-l border-dashed border-border-strong py-0.5 pl-3 text-xs text-subtle">
                            <ArrowDown className="size-3" aria-hidden /> Qty {p.edge_qtys[j]}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ol>
                <p className="num mt-2 text-xs text-muted">Path quantity = {p.edge_qtys.join(" × ")} = <strong className="text-text">{p.path_qty}</strong></p>
              </div>
            ))}
          </div>
          <p className="num mt-3 rounded-lg bg-primary-soft px-3 py-2 text-sm text-primary">
            Effective {part} quantity = {paths.map((p) => p.path_qty).join(" + ")} = <strong>{product.effective_component_qty}</strong>
          </p>
        </Section>

        <Section title="Cost and margin">
          <Row label="Selling price" value={money(product.selling_price)} />
          <Row label="Unit cost" value={money(product.unit_cost)} />
          <Row label="Gross margin" value={pct(product.current_margin)} />
          <Row label={`${part} share of unit cost`} value={pct(product.component_cost_share)} />
          <div className="mt-2 grid grid-cols-4 gap-1 text-center text-[11px] text-subtle">
            {(["purchase", "material", "freight", "processing"] as const).map((k) => (
              <div key={k} className="rounded-md bg-surface-muted px-1 py-1.5">
                <div className="num text-[12.5px] font-semibold text-text">{money(product.cost_breakdown[k])}</div>
                <div className="capitalize">{k}</div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Inventory coverage">
          <Row label={`Shared ${part} stock`} value={days(componentDays)} />
          <Row label="Finished-goods stock" value={days(product.finished_goods_days)} />
          <Row label={<span className="flex items-center gap-1.5"><Warehouse className="size-4" aria-hidden /> Total coverage</span>}
            value={days(product.inventory_coverage_days)} />
        </Section>

        {product.alternative && (
          <Section title="Approved alternatives">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{product.alternative.part_id}</span>
              <ApprovalBadge status={product.alternative.approval_status} />
            </div>
            {product.alternative.notes && <p className="mt-1.5 text-xs text-muted">{product.alternative.notes}</p>}
            {product.alternative.approval_status === "VALIDATION_REQUIRED" && (
              <p className="mt-1 text-xs text-muted">Qualification lead time: {product.alternative.qualification_lead_time_days} days</p>
            )}
            {product.replacement_unit_cost_delta != null && product.replacement_margin != null && repMarginDelta != null && (
              <div className="mt-2.5">
                <Row label="Unit cost with replacement" value={`+${money(product.replacement_unit_cost_delta)}`} />
                <Row label="Margin with replacement" value={`${pct(product.replacement_margin)} (${pts(repMarginDelta)})`} />
              </div>
            )}
          </Section>
        )}
      </div>
    </div>
  );
}
