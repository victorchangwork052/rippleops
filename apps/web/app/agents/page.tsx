"use client";

import { Bot, ListTree, Play, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, buttonVariants } from "@/components/ui";
import { AgentBoard, TOOL_LABEL } from "@/features/agents/agent-board";
import { AgentRunLive, ModeBadge } from "@/features/agents/agent-run-live";
import { api } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import type { AgentStep, WorkflowRun } from "@/lib/types";
import { useLoad } from "@/lib/use-load";

const STEP_LABEL: Record<AgentStep["type"], string> = {
  run_started: "Run started",
  agent_started: "Agent started",
  tool_call: "Tool call",
  tool_result: "Tool result",
  agent_finished: "Agent finished",
  run_finished: "Run finished",
  error: "Error",
};

function AgentsPage() {
  const params = useSearchParams();
  const { eventId: current, setEventId } = useCurrentEvent();
  const eventId = params.get("event") ?? current;
  const run = useLoad(eventId ? () => api.workflow(eventId) : null, eventId ?? "");
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (eventId && eventId !== current) setEventId(eventId);
  }, [eventId, current, setEventId]);

  const header = (
    <PageHeader title="Agent Activity"
      description="How the Google ADK agents worked through this change: which agent ran, which tool it called, and what it concluded."
      actions={eventId && run.data && !live && (
        <Button variant="secondary" onClick={() => setLive(true)}><RotateCcw aria-hidden /> Run Agents Again</Button>
      )} />
  );
  if (!eventId) {
    return (
      <div className="space-y-6">{header}
        <Card><EmptyState icon={Bot} title="No change event selected" description="Analyze a change to see the agents at work."
          actions={<Link href="/events/new" className={buttonVariants()}>Analyze a Change</Link>} /></Card>
      </div>
    );
  }
  if (live) return <div className="space-y-6">{header}<AgentRunLive eventId={eventId} onFinished={(r) => run.setData(r)} /></div>;
  if (run.loading) return <div className="space-y-6">{header}<Card><LoadingState label="Loading agent activity…" /></Card></div>;
  if (run.error) return <div className="space-y-6">{header}<ErrorState message={run.error} /></div>;
  if (!run.data) {
    return (
      <div className="space-y-6">{header}
        <Card><EmptyState icon={Bot} title="The agents have not run for this event"
          description="Run the change-response agents to trace the impact, evaluate sourcing and re-plan production."
          actions={<Button onClick={() => setLive(true)}><Play aria-hidden /> Run Agents</Button>} /></Card>
      </div>
    );
  }
  return <div className="space-y-6">{header}<RunView run={run.data} /></div>;
}

function RunView({ run }: { run: WorkflowRun }) {
  const tools = run.steps.filter((s) => s.type === "tool_call").length;
  const agents = new Set(run.steps.filter((s) => s.type === "agent_started").map((s) => s.agent)).size;
  return (
    <>
      <Card className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
        <ModeBadge mode={run.mode} model={run.model} />
        <Badge tone={run.status === "COMPLETED" ? "success" : run.status === "FAILED" ? "critical" : "warning"}>{run.status.toLowerCase()}</Badge>
        <span className="num text-sm text-muted">{run.run_id} · {agents} agents and groups · {tools} tool calls
          {run.duration_ms != null ? ` · ${(run.duration_ms / 1000).toFixed(1)} s` : ""}</span>
        {run.notice && <span className="w-full text-xs text-subtle">{run.notice}</span>}
      </Card>
      <AgentBoard tree={run.tree} steps={run.steps} findings={run.findings} />
      <Card>
        <CardHeader icon={ListTree} title="Step timeline" description="Every agent and tool step, in order" />
        <div className="max-h-[480px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-muted text-left text-xs font-medium text-muted">
              <tr><th className="px-5 py-2">Time</th><th className="px-3 py-2">Step</th><th className="px-3 py-2">Agent</th><th className="px-5 py-2">Detail</th></tr>
            </thead>
            <tbody>
              {run.steps.map((s) => (
                <tr key={s.seq} className="border-t border-border align-top">
                  <td className="num px-5 py-2 text-xs text-subtle">{(s.at_ms / 1000).toFixed(2)} s</td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-muted">{STEP_LABEL[s.type]}</td>
                  <td className="px-3 py-2 text-xs font-medium text-text">{s.agent ?? ""}</td>
                  <td className="px-5 py-2 text-xs text-text">
                    {s.tool && <span className="font-medium">{TOOL_LABEL[s.tool] ?? s.tool}</span>}
                    {s.args && Object.keys(s.args).length > 0 && <code className="ml-1.5 rounded bg-surface-muted px-1 text-[11px] text-muted">{JSON.stringify(s.args)}</code>}
                    {s.summary && <span className="num ml-1.5 text-muted">{s.summary}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Loading agent activity…" />}>
      <AgentsPage />
    </Suspense>
  );
}
