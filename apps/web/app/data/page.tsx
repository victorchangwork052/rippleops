"use client";

import { ChevronLeft, ChevronRight, Database, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, Card, CardHeader, ErrorState, LoadingState, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { date } from "@/lib/format";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

const PAGE = 50;
const TABLE_LABEL: Record<string, string> = {
  item_master: "Item master",
  bom_edges: "BOM edges",
  suppliers: "Suppliers",
  supplier_parts: "Supplier parts",
  alternate_parts: "Alternate parts",
  inventory: "Inventory",
  product_demand: "Product demand",
  product_price: "Product price",
  material_exposure: "Material exposure",
  material_price: "Material price",
  shipping_lanes: "Shipping lanes",
  change_events: "Change events",
};

export default function DataPage() {
  const summary = useLoad(() => api.dataSummary(), "summary");
  const [table, setTable] = useState("item_master");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(query); setOffset(0); }, 250);
    return () => clearTimeout(t);
  }, [query]);

  const page = useLoad(() => api.table(table, debounced, offset, PAGE), `${table}|${debounced}|${offset}`);

  return (
    <div className="space-y-6">
      <PageHeader title="Data" description="The fictional demo dataset behind every calculation. Read-only."
        actions={summary.data && <Badge tone="neutral"><Database aria-hidden /> {summary.data.data_source === "bigquery" ? "BigQuery" : "Local seed data"} · as of {date(summary.data.as_of_date)}</Badge>} />
      <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader title="Tables" />
          <nav aria-label="Tables" className="p-2">
            {summary.loading ? <LoadingState label="Loading…" className="py-6" /> : summary.data?.tables.map((t) => (
              <button key={t.name} type="button" onClick={() => { setTable(t.name); setOffset(0); setQuery(""); }}
                aria-current={table === t.name ? "true" : undefined}
                className={cn("flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-left text-sm",
                  table === t.name ? "bg-primary-soft font-medium text-primary" : "text-muted hover:bg-surface-muted")}>
                {TABLE_LABEL[t.name] ?? t.name}
                <span className="num text-xs text-subtle">{t.rows}</span>
              </button>
            ))}
          </nav>
        </Card>
        <Card className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
            <h2 className="font-semibold">{TABLE_LABEL[table] ?? table} <span className="font-mono text-xs font-normal text-subtle">{table}</span></h2>
            <div className="relative w-64">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
              <input aria-label="Search this table" placeholder="Search…" value={query} onChange={(e) => setQuery(e.target.value)} className={`${inputClass} pl-8`} />
            </div>
          </div>
          {page.loading ? <LoadingState label="Loading rows…" /> : page.error ? <div className="p-4"><ErrorState message={page.error} /></div> : page.data && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <caption className="sr-only">{table} rows</caption>
                  <thead>
                    <tr className="border-b border-border bg-surface-muted text-left text-xs text-subtle">
                      {page.data.columns.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>)}
                    </tr>
                  </thead>
                  <tbody className="num">
                    {page.data.rows.map((r, i) => (
                      <tr key={i} className="border-b border-border last:border-0">
                        {page.data!.columns.map((c) => (
                          <td key={c} className="max-w-[280px] truncate whitespace-nowrap px-3 py-1.5 text-text" title={String(r[c] ?? "")}>
                            {r[c] === null || r[c] === undefined ? <span className="text-subtle">null</span> : String(r[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t border-border px-5 py-2.5 text-sm text-muted">
                <span className="num">{page.data.total ? `${offset + 1}–${Math.min(offset + PAGE, page.data.total)} of ${page.data.total}` : "No matching rows"}</span>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}><ChevronLeft aria-hidden /></Button>
                  <Button variant="ghost" size="icon" aria-label="Next page" disabled={offset + PAGE >= page.data.total} onClick={() => setOffset(offset + PAGE)}><ChevronRight aria-hidden /></Button>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
