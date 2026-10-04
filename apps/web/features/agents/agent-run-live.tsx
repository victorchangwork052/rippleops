"use client";

import { Bot, ClipboardCheck, Factory, Network, Scale, Timer } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Badge, Card, ErrorState, LoadingState, buttonVariants } from "@/components/ui";
import { AgentBoard, countAgents, reduceSteps } from "@/features/agents/agent-board";
import { errorMessage, runWorkflow } from "@/lib/api";
import type { AgentNode, AgentStep, WorkflowRun } from "@/lib/types";

export function ModeBadge({ mode, model }: { mode: WorkflowRun["mode"]; model: string | null }) {
  return mode === "adk_gemini" ? (
    <Badge tone="primary" title={model ?? undefined}><Bot aria-hidden /> Google ADK · {model ?? "Gemini"}</Badge>
  ) : (
    <Badge tone="neutral"><Bot aria-hidden /> Agents in deterministic mode</Badge>
  );
}

/** Starts the multi-agent change response and shows every agent and tool step as it happens. */
export function AgentRunLive({ eventId, onFinished }: { eventId: string; onFinished?: (run: WorkflowRun) => void }) {
  const started = useRef(false);
  const [tree, setTree] = useState<AgentNode | null>(null);
  const [mode, setMode] = useState<{ mode: WorkflowRun["mode"]; model: string | null } | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const finishedRef = useRef(onFinished);

  useEffect(() => {
    finishedRef.current = onFinished;
  });

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const t0 = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 500);
    runWorkflow(eventId, {
      onRun: (r) => {
        setTree(r.tree);
        setMode({ mode: r.mode, model: r.model });
      },
      onStep: (s) => setSteps((prev) => [...prev, s]),
    })
      .then((r) => {
        setRun(r);
        finishedRef.current?.(r);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => window.clearInterval(timer));
  }, [eventId]);

  if (error) return <ErrorState title="The agents couldn't finish" message={error} />;
  if (!tree) return <Card><LoadingState label="Starting the RippleOps agents…" /></Card>;

  const states = reduceSteps(steps);
  const total = countAgents(tree);
  const done = Object.entries(states).filter(([name, s]) => s.status === "done" && isLlm(tree, name)).length;
  const tools = steps.filter((s) => s.type === "tool_call").length;
  const q = `?event=${encodeURIComponent(eventId)}`;
  const brief = run?.findings.find((f) => f.agent === "response_coordinator");

  return (
    <div className="space-y-5">
      <Card className="px-5 py-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 className="text-[17px] font-semibold text-text">
            {run ? (run.status === "COMPLETED" ? "Change response ready" : "The response did not finish") : "RippleOps agents are working…"}
          </h2>
          {mode && <ModeBadge mode={mode.mode} model={mode.model} />}
          <span className="num flex items-center gap-1.5 text-sm text-muted"><Timer className="size-4" aria-hidden />
            {run?.duration_ms != null ? `${(run.duration_ms / 1000).toFixed(1)} s` : `${elapsed} s`}</span>
          <span className="num text-sm text-muted">{done} of {total} agents · {tools} tool calls</span>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-muted" role="progressbar" aria-valuemin={0}
          aria-valuemax={total} aria-valuenow={done} aria-label="Agents finished">
          <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${(done / total) * 100}%` }} />
        </div>
        {run?.notice && <p className="mt-2 text-xs text-subtle">{run.notice}</p>}
      </Card>

      {run?.status === "COMPLETED" && (
        <Card className="fade-in border-primary-border px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Executive brief</p>
          {brief && <p className="mt-1.5 max-w-4xl text-[15px] leading-relaxed text-text">{brief.text}</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href={`/planning${q}`} className={buttonVariants()}><Factory aria-hidden /> Review Plan {run.proposed_plan_id}</Link>
            <Link href={`/sourcing${q}`} className={buttonVariants({ variant: "secondary" })}><Scale aria-hidden /> Sourcing Options</Link>
            <Link href={`/analysis${q}`} className={buttonVariants({ variant: "secondary" })}><Network aria-hidden /> Impact Analysis</Link>
            <Link href={`/actions${q}`} className={buttonVariants({ variant: "secondary" })}><ClipboardCheck aria-hidden /> Action Plan</Link>
          </div>
        </Card>
      )}

      <AgentBoard tree={tree} steps={steps} findings={run?.findings} />
    </div>
  );
}

function isLlm(node: AgentNode, name: string): boolean {
  if (node.name === name) return node.kind === "llm";
  return node.children.some((c) => isLlm(c, name));
}
