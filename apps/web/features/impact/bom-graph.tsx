"use client";

import {
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getBezierPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Box, Boxes, Cpu, Maximize } from "lucide-react";
import { memo, useMemo, useState } from "react";

import { Button, RISK_META } from "@/components/ui";
import type { GraphEdgeData, GraphNodeData, ImpactAnalysis } from "@/lib/types";
import { cn } from "@/lib/utils";

const COL_W = 226;
const NODE_W = 192;
const ROW_H = 58;

type NodeData = GraphNodeData & { dimmed: boolean; selected: boolean; subtitle: string };
type EdgeData = { qty: number; dimmed: boolean; highlighted: boolean };

/** Layered left-to-right layout: component on the left, finished goods on the right. */
function layout(analysis: ImpactAnalysis): Map<string, { x: number; y: number }> {
  const nodes = analysis.graph.nodes;
  const maxDepth = Math.max(...nodes.map((n) => n.depth), 1);
  const parentsOf = new Map<string, string[]>();
  for (const e of analysis.graph.edges) {
    parentsOf.set(e.target, [...(parentsOf.get(e.target) ?? []), e.source]);
  }
  const col = (n: GraphNodeData) => (n.item_type === "FINISHED_GOOD" ? maxDepth : n.depth);
  const pos = new Map<string, { x: number; y: number }>();

  const family = new Map(analysis.products.map((p) => [p.product_id, p.product_family]));
  const fgs = nodes
    .filter((n) => n.item_type === "FINISHED_GOOD")
    .sort((a, b) => (family.get(a.id) ?? "").localeCompare(family.get(b.id) ?? "") || a.id.localeCompare(b.id));
  fgs.forEach((n, i) => pos.set(n.id, { x: maxDepth * COL_W, y: i * ROW_H }));
  const totalH = (fgs.length - 1) * ROW_H;

  for (let d = maxDepth - 1; d >= 0; d--) {
    const column = nodes.filter((n) => n.item_type !== "FINISHED_GOOD" && col(n) === d);
    const wanted = column.map((n) => {
      const ys = (parentsOf.get(n.id) ?? []).map((p) => pos.get(p)?.y).filter((y): y is number => y !== undefined);
      return { n, y: ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : totalH / 2 };
    });
    wanted.sort((a, b) => a.y - b.y);
    // Keep barycentric order but enforce spacing, then shift the column back so
    // its centre matches the centre of the desired positions.
    const mean = (ys: number[]) => (ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : 0);
    const desiredMean = mean(wanted.map((w) => w.y));
    const gap = ROW_H * 1.25;
    for (let i = 1; i < wanted.length; i++) wanted[i].y = Math.max(wanted[i].y, wanted[i - 1].y + gap);
    const shift = mean(wanted.map((w) => w.y)) - desiredMean;
    wanted.forEach((w) => pos.set(w.n.id, { x: d * COL_W, y: w.y - shift }));
  }
  return pos;
}

function ImpactNode({ data }: NodeProps<Node<NodeData>>) {
  const isFg = data.item_type === "FINISHED_GOOD";
  const isComp = data.item_type === "COMPONENT";
  const Icon = isComp ? Cpu : isFg ? Box : Boxes;
  const risk = data.risk_level ? RISK_META[data.risk_level] : null;
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border bg-white px-2.5 py-1.5 shadow-sm transition-[opacity,box-shadow]",
        isComp ? "border-critical bg-critical-soft ring-4 ring-critical/10" : "border-border-strong",
        data.selected && "ring-2 ring-primary",
        data.dimmed && "opacity-25",
      )}
      style={{ width: NODE_W, borderLeftWidth: isFg && risk ? 4 : undefined, borderLeftColor: isFg && risk ? risk.color : undefined }}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !min-h-0 !min-w-0 !border-0 !bg-border-strong" isConnectable={false} />
      <span className={cn("grid size-7 shrink-0 place-items-center rounded-md",
        isComp ? "bg-critical text-white" : isFg ? "bg-primary-soft text-primary" : "bg-surface-muted text-muted")}>
        <Icon className="size-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 leading-tight">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-[12.5px] font-semibold text-text">{data.id}</span>
          {isComp && <span className="rounded bg-critical px-1 text-[9.5px] font-semibold text-white">EOL</span>}
        </div>
        <div className="truncate text-[11px] text-subtle">{data.subtitle}</div>
      </div>
      {isFg && data.effective_component_qty != null && (
        <span className="num shrink-0 rounded-md bg-surface-muted px-1.5 py-0.5 text-[11px] font-semibold text-text"
          title={`Uses ${data.effective_component_qty} units of the affected component`}>
          {data.effective_component_qty}×
        </span>
      )}
      <Handle type="source" position={Position.Right} className="!size-1.5 !min-h-0 !min-w-0 !border-0 !bg-border-strong" isConnectable={false} />
    </div>
  );
}

function QtyEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<Edge<EdgeData>>) {
  const [hover, setHover] = useState(false);
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const qty = data?.qty ?? 1;
  const stroke = data?.highlighted ? "var(--primary)" : "#98a2b3";
  return (
    <>
      <BaseEdge id={id} path={path} style={{ stroke, strokeWidth: data?.highlighted ? 2.25 : 1.25, opacity: data?.dimmed ? 0.15 : 1 }} />
      <path d={path} fill="none" stroke="transparent" strokeWidth={14}
        onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} />
      {(hover || (qty !== 1 && !data?.dimmed)) && (
        <EdgeLabelRenderer>
          <div
            className={cn("nodrag nopan pointer-events-none absolute rounded-md border px-1.5 py-0.5 text-[10.5px] font-semibold num",
              hover ? "border-primary bg-primary text-white" : "border-border bg-white text-muted")}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {hover ? `Qty per parent: ${qty}` : `×${qty}`}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { impact: memo(ImpactNode) };
const edgeTypes = { qty: QtyEdge };

export interface GraphSelection {
  nodeId: string;
  itemType: GraphNodeData["item_type"];
}

function GraphInner({ analysis, selection, onSelect }: {
  analysis: ImpactAnalysis;
  selection: GraphSelection | null;
  onSelect: (s: GraphSelection | null) => void;
}) {
  const flow = useReactFlow();
  const positions = useMemo(() => layout(analysis), [analysis]);

  // Nodes / edges on the selected product's paths (or through the selected assembly).
  const highlight = useMemo(() => {
    if (!selection) return null;
    const paths = analysis.paths.filter((p) =>
      selection.itemType === "FINISHED_GOOD" ? p.product_id === selection.nodeId : p.nodes.includes(selection.nodeId));
    const nodes = new Set(paths.flatMap((p) => p.nodes));
    const edges = new Set(paths.flatMap((p) => p.nodes.slice(0, -1).map((n, i) => `${n}->${p.nodes[i + 1]}`)));
    return { nodes, edges };
  }, [analysis, selection]);

  const productName = useMemo(() => new Map(analysis.products.map((p) => [p.product_id, p])), [analysis]);

  const nodes: Node<NodeData>[] = analysis.graph.nodes.map((n) => {
    const p = productName.get(n.id);
    const subtitle = n.item_type === "FINISHED_GOOD" ? p?.name ?? n.label : n.label;
    return {
      id: n.id,
      type: "impact",
      position: positions.get(n.id) ?? { x: 0, y: 0 },
      data: { ...n, subtitle, selected: selection?.nodeId === n.id, dimmed: highlight ? !highlight.nodes.has(n.id) : false },
      draggable: false,
      connectable: false,
      ariaLabel: `${n.id}, ${subtitle}${n.risk_level ? `, ${RISK_META[n.risk_level].label} risk` : ""}`,
    };
  });

  // Draw impact flowing from the component outward: child -> parent.
  const edges: Edge<EdgeData>[] = analysis.graph.edges.map((e: GraphEdgeData) => ({
    id: e.id,
    source: e.target,
    target: e.source,
    type: "qty",
    data: { qty: e.qty_per_parent, dimmed: highlight ? !highlight.edges.has(e.id) : false, highlighted: !!highlight?.edges.has(e.id) },
  }));

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.08 }}
        minZoom={0.3}
        maxZoom={1.75}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, n) => onSelect({ nodeId: n.id, itemType: (n.data as NodeData).item_type })}
        onPaneClick={() => onSelect(null)}
        attributionPosition="top-left"
      >
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
      <div className="absolute right-3 top-3 flex gap-2">
        <Button variant="secondary" size="sm" onClick={() => { onSelect(null); void flow.fitView({ padding: 0.08, duration: 300 }); }}>
          <Maximize aria-hidden /> Reset View
        </Button>
      </div>
      <Legend />
    </div>
  );
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-3 right-3 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-white/95 px-3 py-1.5 text-[11px] text-muted">
      <span className="flex items-center gap-1"><Cpu className="size-3.5 text-critical" aria-hidden /> Affected component</span>
      <span className="flex items-center gap-1"><Boxes className="size-3.5" aria-hidden /> Assembly</span>
      <span className="flex items-center gap-1"><Box className="size-3.5 text-primary" aria-hidden /> Finished product</span>
      <span className="num">×n = qty per parent</span>
    </div>
  );
}

export function BomGraph(props: {
  analysis: ImpactAnalysis;
  selection: GraphSelection | null;
  onSelect: (s: GraphSelection | null) => void;
}) {
  return (
    <ReactFlowProvider>
      <GraphInner {...props} />
    </ReactFlowProvider>
  );
}
