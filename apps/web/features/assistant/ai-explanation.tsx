"use client";

import { LoaderCircle, Sparkles } from "lucide-react";

import { api } from "@/lib/api";
import { useLoad } from "@/lib/use-load";

import { GroundingBadge, SourceBadge } from "./ai-badges";

/** Gemini's explanation of one product's calculated impact (deterministic text if Gemini is unavailable). */
export function AiExplanation({ eventId, productId }: { eventId: string; productId: string }) {
  const res = useLoad(() => api.explain(eventId, productId), `${eventId}|${productId}`, { refetchOnReset: false });
  return (
    <div className="mt-3 rounded-lg border border-primary-border bg-primary-soft/40 p-3">
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-primary">
        <Sparkles className="size-3.5" aria-hidden /> Why this matters
      </p>
      {res.loading ? (
        <p role="status" className="flex items-center gap-2 text-sm text-muted">
          <LoaderCircle className="size-4 animate-spin" aria-hidden /> Explaining the calculated results…
        </p>
      ) : res.error || !res.data ? (
        <p className="text-sm text-muted">An explanation is not available right now. The calculated results above are unaffected.</p>
      ) : (
        <>
          <p className="text-sm leading-relaxed text-text">{res.data.text}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <SourceBadge ai={res.data.method === "gemini"} model={res.data.model} />
            <GroundingBadge grounding={res.data.grounding} />
          </div>
        </>
      )}
    </div>
  );
}
