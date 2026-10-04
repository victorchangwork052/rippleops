"use client";

import {
  ArrowLeft,
  CircleCheck,
  CloudUpload,
  FileText,
  PenLine,
  Play,
  Sparkles,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useId, useMemo, useRef, useState, type DragEvent } from "react";

import { AgentRunLive } from "@/features/agents/agent-run-live";
import { Combobox, type ComboOption } from "@/components/combobox";
import { ApprovalBadge, Badge, Button, Card, CardHeader, ErrorState, Field, LoadingState, PageHeader, inputClass } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import type { EventCreate, EventFormOptions, EventType, ParsedNotice } from "@/lib/types";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

type Mode = "upload" | "demo" | "manual";
const ACCEPT = ".pdf,.txt,.docx";
const MAX_BYTES = 2 * 1024 * 1024;

const EMPTY: EventCreate = {
  event_type: "COMPONENT_EOL",
  supplier_name: "",
  part_id: "",
  last_time_buy_date: "",
  last_ship_date: "",
  recommended_alternative_part_id: "",
};

export default function NewEventPage() {
  const { setEventId } = useCurrentEvent();
  const [mode, setMode] = useState<Mode | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedNotice | null>(null);
  const [noticeText, setNoticeText] = useState<string | null>(null);
  const [fields, setFields] = useState<EventCreate | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [analyzingEvent, setAnalyzingEvent] = useState<string | null>(null);

  async function parse(run: () => Promise<ParsedNotice>, source: EventCreate["source"]) {
    setParsing(true);
    setParseError(null);
    setParsed(null);
    try {
      const res = await run();
      setParsed(res);
      setFields({ ...res.fields, source, source_document_name: res.document_name, extraction_method: res.extraction_method });
    } catch (err) {
      setParseError(errorMessage(err));
    } finally {
      setParsing(false);
    }
  }

  async function chooseDemo() {
    setMode("demo");
    setFields(null);
    setParsed(null);
    try {
      const notice = await api.sampleNotice();
      setNoticeText(notice.text);
      await parse(() => api.parseNotice({ document_text: notice.text, document_name: notice.filename }), "demo");
    } catch (err) {
      setParseError(errorMessage(err));
    }
  }

  async function useDemoData() {
    const template = await api.demoEventTemplate();
    setParseError(null);
    setFields(template);
  }

  function chooseManual() {
    setMode("manual");
    setParsed(null);
    setParseError(null);
    setFields({ ...EMPTY, source: "manual", extraction_method: "manual" });
  }

  async function submit() {
    if (!fields) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const clean = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);
      const event = await api.createEvent({
        ...fields,
        supplier_name: clean(fields.supplier_name),
        last_time_buy_date: clean(fields.last_time_buy_date),
        last_ship_date: clean(fields.last_ship_date),
        recommended_alternative_part_id: clean(fields.recommended_alternative_part_id),
      });
      setEventId(event.event_id);
      setAnalyzingEvent(event.event_id);
    } catch (err) {
      setSubmitError(errorMessage(err));
      setSubmitting(false);
    }
  }

  if (analyzingEvent) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow={<Link href="/events" className="inline-flex items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft className="size-4" aria-hidden /> Events</Link>}
          title="Change Response"
          description="A team of Google ADK agents traces the impact, evaluates sourcing, re-plans production and drafts the response. Every number comes from a tool."
        />
        <AgentRunLive eventId={analyzingEvent} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={<Link href="/events" className="inline-flex items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft className="size-4" aria-hidden /> Events</Link>}
        title="New Change Event"
        description="Start from a supplier notice or describe the change yourself. RippleOps extracts the key facts for you to review."
      />

      <div className="grid gap-3 md:grid-cols-3">
        <ModeCard icon={CloudUpload} title="Upload Supplier Notice" text="PDF, TXT, or DOCX up to 2 MB" active={mode === "upload"}
          onClick={() => { setMode("upload"); setFields(null); setParsed(null); setParseError(null); }} />
        <ModeCard icon={PenLine} title="Enter Change Manually" text="Type the part and dates yourself" active={mode === "manual"} onClick={chooseManual} />
        <ModeCard icon={FileText} title="Use Demo Notice" text="NovaChip MCU-X100 discontinuation" active={mode === "demo"} onClick={chooseDemo} />
      </div>

      {mode === "upload" && !fields && (
        <UploadZone disabled={parsing} onFile={(file) => parse(() => api.parseUpload(file), "upload")} onError={setParseError} />
      )}

      {mode === "demo" && noticeText && (
        <Card>
          <CardHeader icon={FileText} title="Supplier notice" description="novachip_mcu_x100_eol_notice.txt" />
          <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap px-5 py-4 font-sans text-[13px] leading-relaxed text-muted">{noticeText}</pre>
        </Card>
      )}

      {parsing && <Card><LoadingState label="Reading the notice and extracting the change…" /></Card>}

      {parseError && (
        <ErrorState title="We couldn't read this notice" message={parseError}
          action={<div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={useDemoData}>Use Extracted Demo Data</Button>
            <Button variant="ghost" size="sm" onClick={chooseManual}>Enter the part manually</Button>
          </div>} />
      )}

      {fields && (
        <ExtractedFields fields={fields} parsed={parsed} onChange={setFields} submitting={submitting}
          submitError={submitError} onSubmit={submit} onUseDemoData={useDemoData} />
      )}
    </div>
  );
}

function ModeCard({ icon: Icon, title, text, active, onClick }: { icon: LucideIcon; title: string; text: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      className={cn("flex items-start gap-3 rounded-xl border bg-surface p-4 text-left transition-colors hover:border-primary-border",
        active ? "border-primary ring-2 ring-primary/15" : "border-border")}>
      <span className={cn("grid size-10 shrink-0 place-items-center rounded-lg", active ? "bg-primary text-white" : "bg-primary-soft text-primary")}>
        <Icon className="size-5" aria-hidden />
      </span>
      <span>
        <span className="block font-semibold text-text">{title}</span>
        <span className="block text-sm text-muted">{text}</span>
      </span>
    </button>
  );
}

function UploadZone({ onFile, onError, disabled }: { onFile: (f: File) => void; onError: (m: string) => void; disabled: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function accept(file: File | undefined) {
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["pdf", "txt", "docx"].includes(ext)) return onError("Please upload a PDF, TXT, or DOCX file.");
    if (file.size > MAX_BYTES) return onError("This file is larger than 2 MB. Please upload a smaller notice.");
    onFile(file);
  }

  return (
    <div
      onDragOver={(e: DragEvent) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e: DragEvent) => { e.preventDefault(); setOver(false); accept(e.dataTransfer.files[0]); }}
      className={cn("flex flex-col items-center rounded-xl border-2 border-dashed bg-surface px-6 py-12 text-center transition-colors",
        over ? "border-primary bg-primary-soft/40" : "border-border-strong")}
    >
      <CloudUpload className="size-8 text-primary" aria-hidden />
      <p className="mt-3 font-semibold">Drop a supplier notice here</p>
      <p className="text-sm text-muted">PDF, TXT, or DOCX</p>
      <Button variant="secondary" className="mt-4" disabled={disabled} onClick={() => input.current?.click()}>Choose file</Button>
      <input ref={input} type="file" accept={ACCEPT} className="sr-only" aria-label="Upload supplier notice"
        onChange={(e) => accept(e.target.files?.[0])} />
    </div>
  );
}

const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: "COMPONENT_EOL", label: "Component End-of-Life" },
  { value: "SUPPLIER_PRICE_INCREASE", label: "Supplier Price Increase" },
];

function ExtractedFields({ fields, parsed, onChange, submitting, submitError, onSubmit, onUseDemoData }: {
  fields: EventCreate;
  parsed: ParsedNotice | null;
  onChange: (f: EventCreate) => void;
  submitting: boolean;
  submitError: string | null;
  onSubmit: () => void;
  onUseDemoData: () => void;
}) {
  const id = useId();
  const set = (k: keyof EventCreate) => (e: { target: { value: string } }) => onChange({ ...fields, [k]: e.target.value });
  const { data: options } = useLoad(api.eventOptions, "event-options", { refetchOnReset: false });
  const picks = usePickerOptions(options, fields);
  const v = parsed?.validation;

  return (
    <Card className="fade-in">
      <CardHeader icon={Sparkles} title={parsed ? "Extracted change" : "Change details"}
        description={parsed ? "Review and correct the fields before analyzing." : "Enter the affected part and key dates."}
        action={parsed && (
          parsed.extraction_method === "gemini"
            ? <Badge tone="primary"><Sparkles aria-hidden /> Extracted by Gemini{parsed.confidence != null ? ` · ${Math.round(parsed.confidence * 100)}% confidence` : ""}</Badge>
            : <Badge tone="neutral">Rule-based extraction{parsed.fallback_reason ? " (Gemini unavailable)" : ""}</Badge>
        )} />
      <form className="space-y-5 p-5" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
        {v && (
          <div className={cn("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm",
            v.part_found ? "border-success-border bg-success-soft" : "border-warning-border bg-warning-soft")}>
            {v.part_found ? <CircleCheck className="mt-0.5 size-4 text-success" aria-hidden /> : <TriangleAlert className="mt-0.5 size-4 text-warning" aria-hidden />}
            <div>
              {v.part_found
                ? <p className="text-text"><strong>{fields.part_id}</strong> matched <strong>{v.part_name}</strong> in the product data{v.supplier_matches ? ", supplied by " + v.supplier_name : ""}.</p>
                : <p className="text-text">We couldn&apos;t identify a valid part number in this notice. Review the extracted information or enter the part manually.</p>}
              {v.warnings.map((w) => <p key={w} className="mt-0.5 text-muted">{w}</p>)}
            </div>
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Event type" htmlFor={`${id}-type`}>
            <select id={`${id}-type`} className={inputClass} value={fields.event_type} onChange={set("event_type")}>
              {EVENT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </Field>
          <Field label="Supplier" htmlFor={`${id}-sup`}>
            <Combobox id={`${id}-sup`} value={fields.supplier_name ?? ""} options={picks.suppliers}
              onChange={(supplier_name) => onChange({ ...fields, supplier_name })} placeholder="Search suppliers" />
          </Field>
          <Field label="Affected part" htmlFor={`${id}-part`} hint="Part number as it appears in the BOM">
            <Combobox id={`${id}-part`} required value={fields.part_id} options={picks.parts}
              onChange={(part_id) => onChange({ ...fields, part_id, supplier_name: picks.supplierOf(part_id) ?? fields.supplier_name })}
              placeholder="Search part number or name" emptyText="No matching parts" />
          </Field>
          <Field label="Recommended replacement" htmlFor={`${id}-alt`}>
            <Combobox id={`${id}-alt`} value={fields.recommended_alternative_part_id ?? ""} options={picks.replacements}
              onChange={(alt) => onChange({ ...fields, recommended_alternative_part_id: alt })} placeholder="Optional · search parts" />
          </Field>
          <Field label="Last time buy" htmlFor={`${id}-ltb`}>
            <input id={`${id}-ltb`} type="date" className={inputClass} value={fields.last_time_buy_date ?? ""} onChange={set("last_time_buy_date")} />
          </Field>
          <Field label="Last ship date" htmlFor={`${id}-lsd`}>
            <input id={`${id}-lsd`} type="date" className={inputClass} value={fields.last_ship_date ?? ""} onChange={set("last_ship_date")} />
          </Field>
        </div>
        {submitError && (
          <ErrorState title="We couldn't create this event" message={submitError}
            action={<Button type="button" variant="secondary" size="sm" onClick={onUseDemoData}>Use Extracted Demo Data</Button>} />
        )}
        <div className="flex justify-end border-t border-border pt-4">
          <Button type="submit" size="lg" disabled={submitting || !fields.part_id.trim()}>
            <Play aria-hidden /> {submitting ? "Starting analysis…" : "Analyze Impact"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

/** Dropdown choices for the supplier, affected part and replacement pickers. */
function usePickerOptions(options: EventFormOptions | null, fields: EventCreate) {
  return useMemo(() => {
    const parts = options?.parts ?? [];
    const partById = new Map(parts.map((p) => [p.part_id, p]));
    const supplier = fields.supplier_name?.trim().toLowerCase();
    const supplierKnown = !!supplier && !!options?.suppliers.some((s) => s.supplier_name.toLowerCase() === supplier);
    const toOption = (p: EventFormOptions["parts"][number], group?: string): ComboOption => ({
      value: p.part_id, label: p.part_name, group,
      detail: [p.supplier_name, p.status !== "ACTIVE" ? p.status.replaceAll("_", " ").toLowerCase() : null].filter(Boolean).join(" · "),
    });

    const suppliers: ComboOption[] = (options?.suppliers ?? []).map((s) => ({
      value: s.supplier_name, label: s.supplier_name, detail: s.country,
    }));

    // With a known supplier selected, only list that supplier's parts.
    const partOptions = parts
      .filter((p) => !supplierKnown || p.supplier_name?.toLowerCase() === supplier)
      .map((p) => toOption(p));

    const source = fields.part_id.trim().toUpperCase();
    const alts = (options?.alternates ?? []).filter((a) => a.source_part_id === source);
    const altIds = new Set(alts.map((a) => a.alternative_part_id));
    const replacements: ComboOption[] = [
      ...alts.flatMap((a) => {
        const p = partById.get(a.alternative_part_id);
        return p ? [{ ...toOption(p, "Known alternates"), badge: <ApprovalBadge status={a.approval_status} /> }] : [];
      }),
      ...parts.filter((p) => p.part_id !== source && !altIds.has(p.part_id))
        .map((p) => toOption(p, alts.length ? "Other parts" : undefined)),
    ];

    const supplierOf = (partId: string) => partById.get(partId.trim().toUpperCase())?.supplier_name ?? null;
    return { suppliers, parts: partOptions, replacements, supplierOf };
  }, [options, fields.supplier_name, fields.part_id]);
}
