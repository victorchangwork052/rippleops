const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const int = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export const money = (x: number) => usd.format(x);
export const money0 = (x: number) => usd0.format(x);

/** $4.2M, $83.5K */
export function moneyCompact(x: number): string {
  const abs = Math.abs(x);
  if (abs >= 1_000_000) return `${x < 0 ? "-" : ""}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${x < 0 ? "-" : ""}$${(abs / 1_000).toFixed(1)}K`;
  return usd0.format(x);
}

export const signedMoney = (x: number) => `${x > 0 ? "+" : x < 0 ? "-" : ""}${usd.format(Math.abs(x))}`;

/** 0.2537 -> "25.4%" */
export const pct = (fraction: number, digits = 1) => `${(fraction * 100).toFixed(digits)}%`;

/** Percentage-point change: -1.89 -> "-1.9 pts" (never "%"). */
export const pts = (points: number, digits = 1) =>
  `${points > 0 ? "+" : points < 0 ? "−" : ""}${Math.abs(points).toFixed(digits)} pts`;

export const signedPct = (fraction: number, digits = 0) =>
  `${fraction > 0 ? "+" : fraction < 0 ? "−" : ""}${Math.abs(fraction * 100).toFixed(digits)}%`;

export const qty = (x: number) => int.format(x);

/** Coverage is reported in whole days, rounded down (conservative). */
export const days = (x: number) => `${Math.floor(x)} days`;

export function date(iso: string | null | undefined): string {
  if (!iso) return "Not specified";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

export const EVENT_TYPE_LABEL: Record<string, string> = {
  COMPONENT_EOL: "Component End-of-Life",
  SUPPLIER_PRICE_INCREASE: "Supplier Price Increase",
  MATERIAL_PRICE_CHANGE: "Material Price Change",
  FREIGHT_CHANGE: "Freight Change",
  OTHER: "Other Change",
};

export const APPROVAL_LABEL: Record<string, string> = {
  APPROVED: "Approved",
  VALIDATION_REQUIRED: "Validation required",
  NOT_APPROVED: "Not approved",
  NONE: "No alternative",
};

export const ITEM_TYPE_LABEL: Record<string, string> = {
  FINISHED_GOOD: "Finished product",
  ASSEMBLY: "Assembly",
  COMPONENT: "Component",
};

export const TRACE_METHOD_LABEL: Record<string, string> = {
  bigquery_graph: "BigQuery Graph",
  recursive_sql: "BigQuery recursive SQL",
  in_memory: "Local seed data",
};
