"use client";

import { ArrowRight, Plus, Radio } from "lucide-react";
import Link from "next/link";

import { Badge, Card, EmptyState, ErrorState, LoadingState, PageHeader, buttonVariants } from "@/components/ui";
import { useCurrentEvent } from "@/lib/current-event";
import { api } from "@/lib/api";
import { EVENT_TYPE_LABEL, date } from "@/lib/format";
import { useLoad } from "@/lib/use-load";

const SOURCE_LABEL = { seed: "Monitoring feed", demo: "Demo notice", upload: "Uploaded notice", manual: "Manual entry" };

export default function EventsPage() {
  const events = useLoad(() => api.events(), "events");
  const { setEventId } = useCurrentEvent();

  return (
    <div className="space-y-6">
      <PageHeader title="Events" description="Business changes reported by suppliers, markets and logistics partners."
        actions={<Link href="/events/new" className={buttonVariants()}><Plus aria-hidden /> Analyze a Change</Link>} />
      <Card>
        {events.loading ? (
          <LoadingState label="Loading events…" />
        ) : events.error ? (
          <div className="p-4"><ErrorState message={events.error} /></div>
        ) : !events.data?.length ? (
          <EmptyState icon={Radio} title="No change events yet"
            description="Upload a supplier notice or load the demo scenario to see how RippleOps maps business impact." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <caption className="sr-only">Change events</caption>
              <thead>
                <tr className="border-b border-border bg-surface-muted text-left text-xs text-subtle">
                  <th scope="col" className="px-5 py-2.5 font-medium">Event</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Type</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Supplier</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Source</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Date</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                  <th scope="col" className="px-5 py-2.5"><span className="sr-only">Open</span></th>
                </tr>
              </thead>
              <tbody>
                {events.data.map((e) => (
                  <tr key={e.event_id} className="border-b border-border last:border-0">
                    <td className="px-5 py-3">
                      <p className="font-semibold text-text">{e.title}</p>
                      <p className="line-clamp-1 max-w-md text-xs text-subtle">{e.event_id} · {e.summary}</p>
                    </td>
                    <td className="px-3 py-3 text-muted">{EVENT_TYPE_LABEL[e.event_type]}</td>
                    <td className="px-3 py-3 text-muted">{e.supplier_name ?? "—"}</td>
                    <td className="px-3 py-3 text-muted">{SOURCE_LABEL[e.source]}</td>
                    <td className="px-3 py-3 text-muted">{date(e.event_date)}</td>
                    <td className="px-3 py-3">
                      <Badge tone={e.status === "ANALYZED" ? "primary" : e.status === "NEW" ? "warning" : "neutral"}>
                        {e.status === "ANALYZED" ? "Analyzed" : e.status === "NEW" ? "New" : "Monitoring"}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 text-right">
                      {e.analyzable ? (
                        <Link href={`/analysis?event=${e.event_id}`} onClick={() => setEventId(e.event_id)}
                          className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
                          {e.status === "ANALYZED" ? "Open analysis" : "Analyze Impact"} <ArrowRight className="size-4" aria-hidden />
                        </Link>
                      ) : (
                        <span className="text-xs text-subtle">Model in Scenario Simulator</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
