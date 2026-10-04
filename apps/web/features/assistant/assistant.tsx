"use client";

import { ArrowRight, LoaderCircle, Send, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { Button, inputClass } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import type { AssistantAnswer } from "@/lib/types";
import { cn } from "@/lib/utils";

import { GroundingBadge, SourceBadge } from "./ai-badges";

type Turn = { role: "user"; text: string } | { role: "assistant"; answer: AssistantAnswer } | { role: "error"; text: string };

const TOOL_LABEL: Record<string, string> = {
  calculate_business_impact: "Business impact",
  trace_bom_impact: "BOM trace",
  get_product_impact: "Product impact",
  run_scenario: "Scenario",
  get_action_plan: "Action plan",
};

function suggestions(product: string | null): string[] {
  const base = ["What products are most exposed?", "What happens if copper rises 10%?", "Which actions should we prioritize?"];
  return product ? [`Why is ${product} at high risk?`, ...base] : ["Why is P300 high risk?", ...base];
}

/** Context-aware assistant, embedded as a side panel rather than a chat-first UI. */
export function Assistant() {
  const { eventId, productInView } = useCurrentEvent();
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const sessionId = useRef(`s${Math.random().toString(36).slice(2, 10)}`);
  const scroller = useRef<HTMLDivElement>(null);
  const inputId = useId();

  useEffect(() => {
    // New event: start a new conversation.
     
    setTurns([]);
    sessionId.current = `s${Math.random().toString(36).slice(2, 10)}`;
  }, [eventId]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  if (!eventId) return null;

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy || !eventId) return;
    setDraft("");
    setTurns((t) => [...t, { role: "user", text: q }]);
    setBusy(true);
    try {
      const answer = await api.ask({ event_id: eventId, question: q, session_id: sessionId.current, product_id: productInView });
      setTurns((t) => [...t, { role: "assistant", answer }]);
    } catch (err) {
      setTurns((t) => [...t, { role: "error", text: errorMessage(err) }]);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-medium text-white shadow-lg shadow-primary/25 hover:bg-primary-hover">
        <Sparkles className="size-[18px]" aria-hidden /> Ask RippleOps
      </button>
    );
  }

  return (
    <aside aria-label="Ask RippleOps" className="fade-in fixed bottom-6 right-6 z-40 flex h-[min(640px,calc(100vh-48px))] w-[420px] max-w-[calc(100vw-48px)] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-md bg-primary-soft text-primary"><Sparkles className="size-4" aria-hidden /></span>
          <div>
            <p className="text-sm font-semibold">Ask RippleOps</p>
            <p className="text-[11.5px] text-subtle">Answers use calculated results for {eventId}{productInView ? ` · viewing ${productInView}` : ""}</p>
          </div>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close assistant" onClick={() => setOpen(false)}><X aria-hidden /></Button>
      </div>

      <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {turns.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-muted">Ask about exposure, risk, or what-if changes. Every figure comes from the deterministic engine.</p>
            {suggestions(productInView).map((s) => (
              <button key={s} type="button" onClick={() => ask(s)}
                className="block w-full rounded-lg border border-border px-3 py-2 text-left text-sm text-text hover:border-primary-border hover:bg-primary-soft/50">
                {s}
              </button>
            ))}
          </div>
        )}
        {turns.map((t, i) =>
          t.role === "user" ? (
            <div key={i} className="ml-10 rounded-xl bg-primary-soft px-3 py-2 text-sm text-text">{t.text}</div>
          ) : t.role === "error" ? (
            <div key={i} role="alert" className="rounded-xl border border-critical-border bg-critical-soft px-3 py-2 text-sm text-critical">{t.text}</div>
          ) : (
            <AnswerCard key={i} answer={t.answer} eventId={eventId} />
          ),
        )}
        {busy && (
          <div role="status" className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle className="size-4 animate-spin text-primary" aria-hidden /> Checking the calculated results…
          </div>
        )}
      </div>

      <form className="flex items-center gap-2 border-t border-border p-3" onSubmit={(e) => { e.preventDefault(); void ask(draft); }}>
        <label htmlFor={inputId} className="sr-only">Ask a question</label>
        <input id={inputId} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask RippleOps…" className={inputClass} maxLength={1000} />
        <Button type="submit" size="icon" aria-label="Send question" disabled={busy || !draft.trim()}><Send aria-hidden /></Button>
      </form>
    </aside>
  );
}

function AnswerCard({ answer, eventId }: { answer: AssistantAnswer; eventId: string }) {
  const tools = [...new Set(answer.tool_calls.map((c) => TOOL_LABEL[c.name] ?? c.name))];
  return (
    <div className="space-y-2 rounded-xl border border-border px-3 py-2.5">
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-text">{answer.answer}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <SourceBadge ai={answer.method === "adk_gemini"} model={answer.model} />
        <GroundingBadge grounding={answer.grounding} />
      </div>
      {tools.length > 0 && <p className="text-[11.5px] text-subtle">Tools used: {tools.join(", ")}</p>}
      {answer.notice && <p className="text-[11.5px] text-subtle">{answer.notice}</p>}
      {answer.scenario_id && (
        <Link href={`/scenarios?event=${encodeURIComponent(eventId)}`}
          className={cn("inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline")}>
          Open in Scenario Simulator <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      )}
    </div>
  );
}
