"use client";

import { ArrowLeft, FlaskConical, History, ListChecks, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, buttonVariants } from "@/components/ui";
import { ScenarioControls, formFromInputs, toFraction, type ScenarioForm } from "@/features/scenarios/scenario-controls";
import { ScenarioResults } from "@/features/scenarios/scenario-results";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";
import { pct } from "@/lib/format";
import type { ScenarioResult } from "@/lib/types";
import { useLoad } from "@/lib/use-load";
import { cn } from "@/lib/utils";

async function loadContext(eventId: string) {
  const [event, reference] = await Promise.all([api.event(eventId), api.reference()]);
  const analysis = event.latest_analysis_id ? await api.impact(eventId) : await api.analyze(eventId);
  const history = await api.scenarios(eventId);
  return { event, reference, analysis, history };
}

function Simulator() {
  const params = useSearchParams();
  const { eventId: current, setEventId } = useCurrentEvent();
  const eventId = params.get("event") ?? current;
  const ctx = useLoad(eventId ? () => loadContext(eventId) : null, eventId ?? "none");
  const [form, setForm] = useState<ScenarioForm | null>(null);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [history, setHistory] = useState<ScenarioResult[]>([]);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (eventId && eventId !== current) setEventId(eventId);
  }, [eventId, current, setEventId]);

  // Initialise the form from the analysis once it loads.
  useEffect(() => {
    if (!ctx.data) return;
    const recommended = ctx.data.analysis.alternatives.find((a) => a.recommended)?.part_id ?? "";
    const latest = ctx.data.history[0];
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm(latest ? formFromInputs(latest.inputs) : {
      replacement: recommended,
      materials: [{ key: "COPPER", pct: "0" }],
      freight: [{ key: "TW-US-OCEAN", pct: "0" }],
      threshold: String(Math.round(ctx.data.analysis.summary.margin_threshold * 100)),
    });
    setHistory(ctx.data.history);
    setResult(latest ?? null);
  }, [ctx.data]);

  if (!eventId) {
    return (
      <Card>
        <EmptyState icon={SlidersHorizontal} title="No change event selected"
          description="Scenarios are modelled on the products affected by a change event. Load the demo scenario or analyze a change first."
          actions={<Link href="/events/new" className={buttonVariants()}>Analyze a Change</Link>} />
      </Card>
    );
  }
  if (ctx.loading || (!form && !ctx.error)) return <Card><LoadingState label="Loading scenario inputs…" /></Card>;
  if (ctx.error || !ctx.data || !form) return <ErrorState title="We couldn't load the scenario inputs" message={ctx.error ?? "Unknown error"} />;

  const { event, analysis, reference } = ctx.data;
  const part = analysis.component.part_id;

  async function run(f: ScenarioForm) {
    setRunning(true);
    setRunError(null);
    const rows = (r: ScenarioForm["materials"]) =>
      Object.fromEntries(r.filter((x) => toFraction(x.pct) !== 0).map((x) => [x.key, toFraction(x.pct)]));
    try {
      const res = await api.runScenario({
        event_id: event.event_id,
        replacement_part_id: f.replacement || null,
        commodity_adjustments: rows(f.materials),
        freight_adjustments: rows(f.freight),
        margin_threshold: toFraction(f.threshold),
      });
      setResult(res);
      setHistory((h) => [res, ...h]);
    } catch (err) {
      setRunError(errorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  function preset(copper: string, freight: string) {
    const recommended = analysis.alternatives.find((a) => a.recommended)?.part_id ?? "";
    const next: ScenarioForm = {
      ...form!,
      replacement: recommended,
      materials: [{ key: "COPPER", pct: copper }],
      freight: [{ key: "TW-US-OCEAN", pct: freight }],
    };
    setForm(next);
    void run(next);
  }

  const q = `?event=${encodeURIComponent(event.event_id)}`;
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={<Link href={`/analysis${q}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft className="size-4" aria-hidden /> {part} End-of-Life</Link>}
        title="Scenario Simulator"
        description="Model multiple changes before committing to a decision."
        actions={result && (
          <Link href={`/actions${q}&scenario=${result.scenario_id}`} className={buttonVariants()}>
            <ListChecks aria-hidden /> Recommended Response
          </Link>
        )}
      />

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader icon={SlidersHorizontal} title="Scenario inputs" description={`Applied to the ${analysis.summary.affected_product_count} products that use ${part}`} />
            <ScenarioControls form={form} onChange={setForm} partId={part} alternatives={analysis.alternatives}
              reference={reference} running={running} onRun={() => run(form)} />
          </Card>
          <Card>
            <CardHeader title="Quick scenarios" />
            <div className="flex flex-col gap-2 p-4">
              <Button variant="secondary" size="sm" className="justify-start" onClick={() => preset("0", "0")} disabled={running}>Replacement only</Button>
              <Button variant="secondary" size="sm" className="justify-start" onClick={() => preset("12", "0")} disabled={running}>Replacement + copper +12%</Button>
              <Button variant="secondary" size="sm" className="justify-start" onClick={() => preset("12", "15")} disabled={running}>Replacement + copper + TW-US freight</Button>
            </div>
          </Card>
          {history.length > 0 && (
            <Card>
              <CardHeader icon={History} title="Recent scenarios" />
              <ul className="max-h-64 divide-y divide-border overflow-y-auto">
                {history.map((h) => (
                  <li key={h.scenario_id}>
                    <button type="button" onClick={() => { setResult(h); setForm(formFromInputs(h.inputs)); }}
                      className={cn("w-full px-5 py-2.5 text-left text-sm hover:bg-surface-muted", result?.scenario_id === h.scenario_id && "bg-primary-soft")}>
                      <span className="block font-medium text-text">{h.name}</span>
                      <span className="num text-xs text-subtle">{h.summary.products_below_margin_threshold} below {pct(h.inputs.margin_threshold, 0)} · {h.scenario_id}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="min-w-0 space-y-4">
          {runError && <ErrorState title="The scenario could not be calculated" message={runError} />}
          {running && !result ? (
            <Card><LoadingState label="Recalculating product cost and margin…" /></Card>
          ) : result ? (
            <div className={cn(running && "opacity-60 transition-opacity")}><ScenarioResults result={result} /></div>
          ) : (
            <Card>
              <EmptyState icon={FlaskConical} title="Run a scenario to compare with the current state"
                description={`Pick a replacement for ${part}, adjust raw-material and freight costs, then select Run Scenario.`} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ScenariosPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading scenarios…" />}>
      <Simulator />
    </Suspense>
  );
}
