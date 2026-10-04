import { CircleCheck, Sparkles, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui";
import type { Grounding } from "@/lib/types";

export function SourceBadge({ ai, model }: { ai: boolean; model?: string | null }) {
  return ai ? (
    <Badge tone="primary" title={model ?? undefined}><Sparkles aria-hidden /> Gemini</Badge>
  ) : (
    <Badge tone="neutral">Calculated summary</Badge>
  );
}

/** Shows whether every figure in the text matches a calculated result. */
export function GroundingBadge({ grounding }: { grounding: Grounding }) {
  return grounding.verified ? (
    <Badge tone="success"><CircleCheck aria-hidden /> Figures match calculated results</Badge>
  ) : (
    <Badge tone="warning" title={grounding.unverified_values.join(", ")}>
      <TriangleAlert aria-hidden /> Unverified figures: {grounding.unverified_values.join(", ")}
    </Badge>
  );
}
