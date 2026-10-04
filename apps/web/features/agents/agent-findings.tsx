"use client";

import { Bot, CircleCheck, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { Badge, Card, CardHeader } from "@/components/ui";
import type { WorkflowRun } from "@/lib/types";

/** The findings selected agents wrote for this event, with their provenance. */
export function AgentFindings({ run, agents, title = "What the agents found" }: {
  run: WorkflowRun | null;
  agents: string[];
  title?: string;
}) {
  const findings = agents.map((a) => run?.findings.find((f) => f.agent === a)).filter((f) => !!f);
  if (!run || !findings.length) return null;
  return (
    <Card className="fade-in">
      <CardHeader icon={Bot} title={title}
        description={run.mode === "adk_gemini" ? `Google ADK agents · ${run.model}` : "Agents in deterministic mode"}
        action={<Link href={`/agents?event=${encodeURIComponent(run.event_id)}`} className="text-sm font-medium text-primary hover:underline">Agent activity</Link>} />
      <ul className="divide-y divide-border">
        {findings.map((f) => (
          <li key={f.agent} className="px-5 py-3.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-text">{f.label}</span>
              {f.method === "adk_gemini" ? <Badge tone="primary">Gemini</Badge> : <Badge tone="neutral">Calculated summary</Badge>}
              {f.grounded ? <Badge tone="success"><CircleCheck aria-hidden /> Figures verified</Badge>
                : <Badge tone="warning"><TriangleAlert aria-hidden /> Replaced unverified figures</Badge>}
            </div>
            <p className="mt-1 max-w-4xl text-sm leading-relaxed text-text">{f.text}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}
