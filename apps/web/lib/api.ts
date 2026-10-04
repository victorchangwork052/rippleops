import type {
  Action,
  ActionPlan,
  ActionStatus,
  ActionsSummary,
  AgentNode,
  AgentStep,
  AssistantAnswer,
  ChangeEvent,
  DataSummary,
  EventCreate,
  EventFormOptions,
  Explanation,
  Health,
  ImpactAnalysis,
  ParsedNotice,
  PlanningView,
  ProductionPlan,
  Reference,
  ScenarioRequest,
  ScenarioResult,
  SourcingView,
  TablePage,
  WorkflowRun,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

const FALLBACK_MESSAGE = "Something went wrong while contacting RippleOps. Please try again.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: init?.body instanceof FormData ? init.headers : { "content-type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("RippleOps is not reachable. Check your connection and try again.", 0, "network");
  }
  if (!res.ok) {
    let message = FALLBACK_MESSAGE;
    let code = "error";
    try {
      const body = await res.json();
      message = body?.error?.message ?? message;
      code = body?.error?.code ?? code;
    } catch {
      /* non-JSON error body: keep the generic message, never show raw output */
    }
    throw new ApiError(message, res.status, code);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/health"),
  events: () => request<ChangeEvent[]>("/events"),
  event: (id: string) => request<ChangeEvent>(`/events/${encodeURIComponent(id)}`),
  createEvent: (body: EventCreate) => post<ChangeEvent>("/events", body),
  eventOptions: () => request<EventFormOptions>("/events/options"),
  parseNotice: (body: { document_text: string; document_name?: string }) => post<ParsedNotice>("/events/parse", body),
  parseUpload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ParsedNotice>("/events/parse-upload", { method: "POST", body: form });
  },
  demoEventTemplate: () => request<EventCreate>("/demo/event-template"),
  analyze: (eventId: string, marginThreshold?: number) =>
    post<ImpactAnalysis>("/impact/analyze", { event_id: eventId, margin_threshold: marginThreshold }),
  impact: (eventId: string) => request<ImpactAnalysis>(`/impact/${encodeURIComponent(eventId)}`),
  runScenario: (body: ScenarioRequest) => post<ScenarioResult>("/scenarios/run", body),
  scenarios: (eventId?: string) =>
    request<ScenarioResult[]>(`/scenarios${eventId ? `?event_id=${encodeURIComponent(eventId)}` : ""}`),
  scenario: (id: string) => request<ScenarioResult>(`/scenarios/${encodeURIComponent(id)}`),
  reference: () => request<Reference>("/reference"),
  generateActions: (eventId: string, scenarioId?: string | null) =>
    post<ActionPlan>("/actions/generate", { event_id: eventId, scenario_id: scenarioId ?? null }),
  actions: (eventId: string) => request<ActionPlan | null>(`/actions?event_id=${encodeURIComponent(eventId)}`),
  actionsSummary: () => request<ActionsSummary>("/actions/summary"),
  updateAction: (id: string, body: { status?: ActionStatus; owner?: string }) =>
    request<Action>(`/actions/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }),
  ask: (body: { event_id: string; question: string; session_id: string; product_id?: string | null }) =>
    post<AssistantAnswer>("/assistant/ask", body),
  explain: (eventId: string, productId?: string | null) =>
    post<Explanation>(`/impact/${encodeURIComponent(eventId)}/explain`, { product_id: productId ?? null }),
  sampleNotice: () => request<{ filename: string; text: string }>("/demo/sample-notice"),
  loadDemo: () => post<{ event: ChangeEvent; analysis_id: string }>("/demo/load"),
  resetDemo: () => post<{ status: string }>("/demo/reset"),
  dataSummary: () => request<DataSummary>("/data/summary"),
  sourcing: (eventId: string) => request<SourcingView>(`/sourcing/${encodeURIComponent(eventId)}`),
  planning: (eventId: string) => request<PlanningView>(`/planning/${encodeURIComponent(eventId)}`),
  optimize: (eventId: string, bridgeBuyQty: number) =>
    post<ProductionPlan>(`/planning/${encodeURIComponent(eventId)}/optimize`, { bridge_buy_qty: bridgeBuyQty }),
  proposePlan: (planId: string) => post<ProductionPlan>(`/planning/plans/${encodeURIComponent(planId)}/propose`),
  decidePlan: (planId: string, decision: "APPROVED" | "REJECTED") =>
    post<ProductionPlan>(`/planning/plans/${encodeURIComponent(planId)}/decision`, { decision }),
  workflow: (eventId: string) => request<WorkflowRun | null>(`/workflow/${encodeURIComponent(eventId)}`),
  workflowTree: () => request<AgentNode>("/workflow/tree"),
  table: (name: string, q = "", offset = 0, limit = 50) =>
    request<TablePage>(
      `/data/tables/${encodeURIComponent(name)}?limit=${limit}&offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    ),
};

/**
 * Run the multi-agent change response and stream each agent / tool step.
 * Resolves with the finished run (findings, proposed plan) when the stream ends.
 */
export async function runWorkflow(
  eventId: string,
  handlers: {
    onRun?: (run: Pick<WorkflowRun, "run_id" | "mode" | "model" | "tree">) => void;
    onStep: (step: AgentStep) => void;
  },
  signal?: AbortSignal,
): Promise<WorkflowRun> {
  let res: Response;
  try {
    res = await fetch("/api/workflow/run", {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify({ event_id: eventId }),
      signal,
    });
  } catch {
    throw new ApiError("RippleOps is not reachable. Check your connection and try again.", 0, "network");
  }
  if (!res.ok || !res.body) {
    let message = FALLBACK_MESSAGE;
    try {
      message = (await res.json())?.error?.message ?? message;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(message, res.status, "error");
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let finished: WorkflowRun | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "run") handlers.onRun?.(parsed);
      else if (event === "step") handlers.onStep(parsed as AgentStep);
      else if (event === "done") finished = parsed as WorkflowRun;
    }
  }
  if (!finished) throw new ApiError("The agent run ended unexpectedly. Please try again.", 0, "stream");
  return finished;
}

export function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : FALLBACK_MESSAGE;
}
