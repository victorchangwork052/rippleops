"use client";

import {
  ArrowLeft,
  CircleDollarSign,
  Cog,
  Cpu,
  Factory,
  ListChecks,
  RotateCcw,
  Sparkles,
  User,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, buttonVariants } from "@/components/ui";
import { GroundingBadge, SourceBadge } from "@/features/assistant/ai-badges";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import type { Action, ActionPlan, ActionStatus, Department } from "@/lib/types";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

const DEPARTMENTS: { name: Department; icon: LucideIcon }[] = [
  { name: "Procurement", icon: Factory },
  { name: "Engineering", icon: Cpu },
  { name: "Operations", icon: Cog },
  { name: "Finance", icon: CircleDollarSign },
  { name: "Sales / Product", icon: Users },
];

const STATUS: { value: ActionStatus; label: string }[] = [
  { value: "PROPOSED", label: "Proposed" },
  { value: "ACCEPTED", label: "Accepted" },
  { value: "IN_PROGRESS", label: "In Progress" },
  { value: "DONE", label: "Done" },
];

/** Load the saved plan; when arriving from the simulator with a newer scenario, plan against it. */
async function loadPlan(eventId: string, scenarioId: string | null): Promise<ActionPlan | null> {
  const plan = await api.actions(eventId);
  if (scenarioId && plan?.scenario_id !== scenarioId) return api.generateActions(eventId, scenarioId);
  return plan;
}

function ActionsView() {
  const params = useSearchParams();
  const { eventId: current, setEventId } = useCurrentEvent();
  const eventId = params.get("event") ?? current;
  const scenarioId = params.get("scenario");
  const plan = useLoad(eventId ? () => loadPlan(eventId, scenarioId) : null, `${eventId}|${scenarioId}`);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  useEffect(() => {
    if (eventId && eventId !== current) setEventId(eventId);
  }, [eventId, current, setEventId]);

  async function generate() {
    if (!eventId) return;
    setGenerating(true);
    setGenError(null);
    try {
      plan.setData(await api.generateActions(eventId, scenarioId));
    } catch (err) {
      setGenError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  if (!eventId) {
    return (
      <Card>
        <EmptyState icon={ListChecks} title="No change event selected"
          description="Analyze a change first; RippleOps then turns the results into a cross-functional plan."
          actions={<Link href="/events/new" className={buttonVariants()}>Analyze a Change</Link>} />
      </Card>
    );
  }

  const q = `?event=${encodeURIComponent(eventId)}`;
  const header = (
    <PageHeader
      eyebrow={<Link href={`/scenarios${q}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft className="size-4" aria-hidden /> Scenario Simulator</Link>}
      title="Recommended Response"
      description="Turn analysis into a coordinated cross-functional plan."
      actions={plan.data && (
        <Button variant="secondary" onClick={generate} disabled={generating}>
          <RotateCcw aria-hidden className={cn(generating && "animate-spin")} /> {generating ? "Regenerating…" : "Regenerate"}
        </Button>
      )}
    />
  );

  if (plan.loading || (generating && !plan.data)) {
    return <div className="space-y-6">{header}<Card><LoadingState label="Preparing recommendations from the calculated results…" /></Card></div>;
  }
  if (plan.error) return <div className="space-y-6">{header}<ErrorState message={plan.error} /></div>;

  return (
    <div className="space-y-6">
      {header}
      {genError && <ErrorState title="We couldn't generate the plan" message={genError} />}
      {!plan.data ? (
        <Card>
          <EmptyState icon={ListChecks} title="No action plan yet"
            description="Generate a response grounded in the latest scenario. Every action cites the calculated facts behind it."
            actions={<Button onClick={generate} disabled={generating}><Sparkles aria-hidden /> Generate Response</Button>} />
        </Card>
      ) : (
        <PlanView plan={plan.data} onUpdate={(a) => plan.setData({ ...plan.data!, actions: plan.data!.actions.map((x) => (x.action_id === a.action_id ? a : x)) })} />
      )}
    </div>
  );
}

function PlanView({ plan, onUpdate }: { plan: ActionPlan; onUpdate: (a: Action) => void }) {
  const open = plan.actions.filter((a) => a.status !== "DONE").length;
  return (
    <>
      <Card className="fade-in px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge ai={plan.method === "gemini"} model={plan.model} />
          <GroundingBadge grounding={plan.grounding} />
          <Badge tone="neutral">Scenario: {plan.scenario_name}</Badge>
          <Badge tone="neutral">{open} of {plan.actions.length} open</Badge>
        </div>
        <p className="mt-3 max-w-4xl text-[15px] leading-relaxed text-text">{plan.summary}</p>
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        {DEPARTMENTS.map((d) => {
          const items = plan.actions.filter((a) => a.department === d.name);
          if (!items.length) return null;
          return (
            <Card key={d.name} className="fade-in">
              <div className="flex items-center gap-2.5 border-b border-border px-5 py-3.5">
                <span className="grid size-8 place-items-center rounded-lg bg-primary-soft text-primary"><d.icon className="size-[18px]" aria-hidden /></span>
                <h2 className="text-[15px] font-semibold">{d.name}</h2>
                <span className="text-xs text-subtle">{items.length} action{items.length > 1 ? "s" : ""}</span>
              </div>
              <ul className="divide-y divide-border">
                {items.map((a) => <ActionItem key={a.action_id} action={a} onUpdate={onUpdate} />)}
              </ul>
            </Card>
          );
        })}
      </div>
    </>
  );
}

function ActionItem({ action, onUpdate }: { action: Action; onUpdate: (a: Action) => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function setStatus(status: ActionStatus) {
    setSaving(true);
    setError(null);
    try {
      onUpdate(await api.updateAction(action.action_id, { status }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }
  const done = action.status === "DONE";
  return (
    <li className={cn("px-5 py-4", done && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Badge tone={action.priority === "HIGH" ? "critical" : action.priority === "MEDIUM" ? "warning" : "neutral"}>
            {action.priority === "HIGH" ? "High priority" : action.priority === "MEDIUM" ? "Medium priority" : "Low priority"}
          </Badge>
          <h3 className={cn("mt-1.5 font-semibold text-text", done && "line-through")}>{action.title}</h3>
        </div>
        <label className="sr-only" htmlFor={`status-${action.action_id}`}>Status for {action.title}</label>
        <select id={`status-${action.action_id}`} value={action.status} disabled={saving}
          onChange={(e) => setStatus(e.target.value as ActionStatus)}
          className="h-8 shrink-0 rounded-lg border border-border-strong bg-surface px-2 text-[13px] font-medium text-text">
          {STATUS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">{action.reason}</p>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {action.facts.map((f) => <span key={f} className="num rounded-md bg-surface-muted px-2 py-0.5 text-xs text-text">{f}</span>)}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-subtle">
        <span className="inline-flex items-center gap-1"><User className="size-3.5" aria-hidden /> {action.owner}</span>
        {action.related_products.length > 0 && <span>Products: {action.related_products.join(", ")}</span>}
      </div>
      {error && <p role="alert" className="mt-2 text-xs text-critical">{error}</p>}
    </li>
  );
}

export default function ActionsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading actions…" />}>
      <ActionsView />
    </Suspense>
  );
}
