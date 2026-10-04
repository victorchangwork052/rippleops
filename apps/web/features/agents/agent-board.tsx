"use client";

import {
  CircleCheck,
  ClipboardList,
  Factory,
  Gauge,
  LoaderCircle,
  Network,
  Newspaper,
  Scale,
  Search,
  ShieldCheck,
  TrendingUp,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui";
import type { AgentFinding, AgentNode, AgentStep } from "@/lib/types";
import { cn } from "@/lib/utils";

export type AgentStatus = "idle" | "running" | "done";

export interface ToolActivity {
  tool: string;
  args: Record<string, unknown> | null;
  summary: string | null;
  done: boolean;
}

export interface AgentState {
  status: AgentStatus;
  tools: ToolActivity[];
  text: string | null;
}

const AGENT_ICON: Record<string, LucideIcon> = {
  impact_analyst: Network,
  sourcing_scout: Search,
  performance_auditor: Gauge,
  compliance_screener: ShieldCheck,
  risk_news_monitor: Newspaper,
  supplier_evaluator: Scale,
  demand_planner: TrendingUp,
  production_planner: Factory,
  response_coordinator: ClipboardList,
};

export const TOOL_LABEL: Record<string, string> = {
  analyze_change_impact: "BOM trace and impact (BigQuery Graph)",
  find_sourcing_options: "Approved vendors + distributor catalog",
  get_supplier_performance: "Supplier KPIs (ERP)",
  screen_suppliers: "Sanctions screening",
  search_supplier_news: "Supplier news",
  score_suppliers: "Weighted scorecard",
  forecast_demand: "Demand forecast",
  calculate_material_requirements: "Material requirements",
  get_bridge_supply_options: "Broker stock",
  optimize_production_plan: "OR-Tools optimizer",
  propose_production_plan: "Submit for approval",
  generate_action_plan: "Cross-functional action plan",
};

/** Fold the step stream into one state per agent. */
export function reduceSteps(steps: AgentStep[]): Record<string, AgentState> {
  const out: Record<string, AgentState> = {};
  const get = (name: string) => (out[name] ??= { status: "idle", tools: [], text: null });
  for (const s of steps) {
    if (!s.agent) continue;
    const a = get(s.agent);
    if (s.type === "agent_started") a.status = "running";
    else if (s.type === "agent_finished") {
      a.status = "done";
      a.text = s.text;
    } else if (s.type === "tool_call" && s.tool) a.tools.push({ tool: s.tool, args: s.args, summary: null, done: false });
    else if (s.type === "tool_result" && s.tool) {
      const open = [...a.tools].reverse().find((t) => t.tool === s.tool && !t.done);
      if (open) {
        open.done = true;
        open.summary = s.summary;
      }
    }
  }
  return out;
}

export function countAgents(node: AgentNode): number {
  return node.kind === "llm" ? 1 : node.children.reduce((n, c) => n + countAgents(c), 0);
}

function argLabel(args: Record<string, unknown> | null): string {
  if (!args) return "";
  const q = args.bridge_buy_qty;
  if (typeof q === "number") return q ? ` · bridge buy ${q.toLocaleString("en-US")}` : " · no bridge buy";
  if (typeof args.plan_id === "string") return ` · ${args.plan_id}`;
  return "";
}

function AgentCard({ node, state, finding }: { node: AgentNode; state?: AgentState; finding?: AgentFinding }) {
  const Icon = AGENT_ICON[node.name] ?? Network;
  const status = state?.status ?? "idle";
  const text = finding?.text ?? state?.text;
  return (
    <div
      className={cn(
        "rounded-xl border bg-surface p-3.5 transition-colors",
        status === "running" && "border-primary ring-2 ring-primary/15",
        status === "done" && "border-success-border",
        status === "idle" && "border-border opacity-70",
      )}
    >
      <div className="flex items-center gap-2.5">
        <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg",
          status === "done" ? "bg-success-soft text-success" : status === "running" ? "bg-primary text-white" : "bg-surface-muted text-muted")}>
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-text">{node.label}</p>
          <p className="truncate text-xs text-subtle">{node.description}</p>
        </div>
        {status === "running" && <LoaderCircle className="size-4 shrink-0 animate-spin text-primary" aria-label="Working" />}
        {status === "done" && <CircleCheck className="size-4 shrink-0 text-success" aria-label="Done" />}
      </div>
      {!!state?.tools.length && (
        <ul className="mt-2.5 space-y-1.5">
          {state.tools.map((t, i) => (
            <li key={i} className="rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs">
              <span className="flex items-center gap-1.5 font-medium text-text">
                {t.done ? <CircleCheck className="size-3.5 shrink-0 text-success" aria-hidden />
                  : <LoaderCircle className="size-3.5 shrink-0 animate-spin text-primary" aria-hidden />}
                <span className="truncate">{TOOL_LABEL[t.tool] ?? t.tool}{argLabel(t.args)}</span>
              </span>
              {t.summary && <span className="num mt-0.5 block pl-5 text-muted">{t.summary}</span>}
            </li>
          ))}
        </ul>
      )}
      {text && status === "done" && (
        <div className="mt-2.5 border-t border-border pt-2.5">
          <p className="text-[13px] leading-relaxed text-text">{text}</p>
          {finding && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {finding.method === "adk_gemini" ? <Badge tone="primary">Gemini</Badge> : <Badge tone="neutral">Calculated summary</Badge>}
              {finding.grounded ? (
                <Badge tone="success"><CircleCheck aria-hidden /> Figures verified</Badge>
              ) : (
                <Badge tone="warning" title={finding.unverified_values.join(", ")}>
                  <TriangleAlert aria-hidden /> Replaced unverified figures
                </Badge>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Group({ node, children }: { node: AgentNode; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-border-strong bg-surface-muted/40 p-3">
      <div className="mb-2.5 flex items-center gap-2 px-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">{node.label}</span>
        <Badge tone="neutral">{node.kind === "parallel" ? "Parallel" : "Sequential"}</Badge>
      </div>
      {children}
    </div>
  );
}

function NodeView({ node, states, findings, root = false }: {
  node: AgentNode;
  states: Record<string, AgentState>;
  findings: Record<string, AgentFinding>;
  root?: boolean;
}) {
  if (node.kind === "llm") return <AgentCard node={node} state={states[node.name]} finding={findings[node.name]} />;
  const inner = node.kind === "parallel" ? (
    <div className={cn("grid gap-3", node.children.length === 2 && "lg:grid-cols-2")}>
      {node.children.map((c) => <NodeView key={c.name} node={c} states={states} findings={findings} />)}
    </div>
  ) : (
    <div className="space-y-3">
      {node.children.map((c) => <NodeView key={c.name} node={c} states={states} findings={findings} />)}
    </div>
  );
  return root ? inner : <Group node={node}>{inner}</Group>;
}

/** The ADK agent hierarchy with live status, tool calls and findings. */
export function AgentBoard({ tree, steps, findings = [] }: { tree: AgentNode; steps: AgentStep[]; findings?: AgentFinding[] }) {
  const states = reduceSteps(steps);
  const byAgent = Object.fromEntries(findings.map((f) => [f.agent, f]));
  return <NodeView node={tree} states={states} findings={byAgent} root />;
}
