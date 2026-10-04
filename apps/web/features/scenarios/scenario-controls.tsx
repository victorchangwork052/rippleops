"use client";

import { Cpu, FlaskConical, PackageOpen, Percent, Plus, Ship, Trash2 } from "lucide-react";
import { useId, type ReactNode } from "react";

import { Button, inputClass } from "@/components/ui";
import { APPROVAL_LABEL, signedPct } from "@/lib/format";
import type { AlternativeComparison, Reference, ScenarioRequest } from "@/lib/types";

export interface AdjustmentRow {
  key: string; // material code or lane id
  pct: string; // user input in percent, e.g. "12"
}

export interface ScenarioForm {
  replacement: string; // "" = keep current part
  materials: AdjustmentRow[];
  freight: AdjustmentRow[];
  threshold: string; // percent
}

export const toFraction = (pct: string) => (Number.isFinite(Number(pct)) ? Number(pct) / 100 : 0);

const toPct = (fraction: number) => String(Math.round(fraction * 1000) / 10);

/** Rebuild the form from a stored scenario so inputs always match the result shown. */
export function formFromInputs(inputs: ScenarioRequest): ScenarioForm {
  const rows = (adj: Record<string, number>, fallback: string) => {
    const entries = Object.entries(adj);
    return entries.length ? entries.map(([key, v]) => ({ key, pct: toPct(v) })) : [{ key: fallback, pct: "0" }];
  };
  return {
    replacement: inputs.replacement_part_id ?? "",
    materials: rows(inputs.commodity_adjustments, "COPPER"),
    freight: rows(inputs.freight_adjustments, "TW-US-OCEAN"),
    threshold: toPct(inputs.margin_threshold),
  };
}

function Group({ icon: Icon, title, children }: { icon: typeof Cpu; title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-2.5 border-t border-border px-5 py-4 first:border-t-0">
      <legend className="sr-only">{title}</legend>
      <div className="flex items-center gap-2 text-[13px] font-semibold text-text">
        <Icon className="size-4 text-subtle" aria-hidden /> {title}
      </div>
      {children}
    </fieldset>
  );
}

function PercentInput({ id, value, onChange, label }: { id: string; value: string; onChange: (v: string) => void; label: string }) {
  return (
    <div className="relative w-24 shrink-0">
      <input id={id} aria-label={label} inputMode="decimal" type="number" step="1" min="-90" max="300" value={value}
        onChange={(e) => onChange(e.target.value)} className={`${inputClass} num pr-7 text-right`} />
      <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-sm text-subtle">%</span>
    </div>
  );
}

function AdjustmentRows({ rows, options, onChange, addLabel, kind }: {
  rows: AdjustmentRow[];
  options: { value: string; label: string }[];
  onChange: (rows: AdjustmentRow[]) => void;
  addLabel: string;
  kind: string;
}) {
  const id = useId();
  const used = new Set(rows.map((r) => r.key));
  const next = options.find((o) => !used.has(o.value));
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <select aria-label={`${kind} ${i + 1}`} value={row.key} className={inputClass}
            onChange={(e) => onChange(rows.map((r, j) => (j === i ? { ...r, key: e.target.value } : r)))}>
            {options.filter((o) => o.value === row.key || !used.has(o.value)).map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <PercentInput id={`${id}-${i}`} label={`${kind} ${i + 1} change in percent`} value={row.pct}
            onChange={(v) => onChange(rows.map((r, j) => (j === i ? { ...r, pct: v } : r)))} />
          <Button variant="ghost" size="icon" aria-label={`Remove ${kind} ${i + 1}`} className="shrink-0"
            onClick={() => onChange(rows.filter((_, j) => j !== i))}>
            <Trash2 aria-hidden />
          </Button>
        </div>
      ))}
      {next && (
        <Button variant="ghost" size="sm" onClick={() => onChange([...rows, { key: next.value, pct: "0" }])}>
          <Plus aria-hidden /> {addLabel}
        </Button>
      )}
    </div>
  );
}

export function ScenarioControls({ form, onChange, partId, alternatives, reference, running, onRun }: {
  form: ScenarioForm;
  onChange: (f: ScenarioForm) => void;
  partId: string;
  alternatives: AlternativeComparison[];
  reference: Reference;
  running: boolean;
  onRun: () => void;
}) {
  const ids = { rep: useId(), thr: useId() };
  const materialOptions = reference.materials.map((m) => ({
    value: m.material_code,
    label: m.material_code.charAt(0) + m.material_code.slice(1).toLowerCase(),
  }));
  const laneOptions = reference.shipping_lanes.map((l) => ({
    value: l.shipping_lane_id,
    // Compact label ("TW → US · Ocean") so it fits next to the percent input.
    label: `${l.shipping_lane_id.split("-")[0]} → ${l.shipping_lane_id.split("-")[1]} · ${l.mode}`,
  }));

  return (
    <form onSubmit={(e) => { e.preventDefault(); onRun(); }}>
      <Group icon={Cpu} title="Component">
        <label htmlFor={ids.rep} className="block text-[13px] text-muted">Replace {partId} with</label>
        <select id={ids.rep} value={form.replacement} className={inputClass}
          onChange={(e) => onChange({ ...form, replacement: e.target.value })}>
          <option value="">Keep {partId} (no replacement)</option>
          {alternatives.map((a) => (
            <option key={a.part_id} value={a.part_id}>
              {a.part_id} · {APPROVAL_LABEL[a.default_approval]}
              {a.unit_price_delta_pct != null ? ` · ${signedPct(a.unit_price_delta_pct)} price` : ""}
            </option>
          ))}
        </select>
      </Group>
      <Group icon={PackageOpen} title="Commodity">
        <AdjustmentRows kind="Material" rows={form.materials} options={materialOptions} addLabel="Add material"
          onChange={(materials) => onChange({ ...form, materials })} />
      </Group>
      <Group icon={Ship} title="Freight">
        <AdjustmentRows kind="Shipping lane" rows={form.freight} options={laneOptions} addLabel="Add shipping lane"
          onChange={(freight) => onChange({ ...form, freight })} />
      </Group>
      <Group icon={Percent} title="Threshold">
        <div className="flex items-center justify-between gap-3">
          <label htmlFor={ids.thr} className="text-[13px] text-muted">Target gross margin</label>
          <PercentInput id={ids.thr} label="Target gross margin in percent" value={form.threshold}
            onChange={(threshold) => onChange({ ...form, threshold })} />
        </div>
      </Group>
      <div className="border-t border-border px-5 py-4">
        <Button type="submit" size="lg" className="w-full" disabled={running}>
          <FlaskConical aria-hidden /> {running ? "Calculating…" : "Run Scenario"}
        </Button>
      </div>
    </form>
  );
}
