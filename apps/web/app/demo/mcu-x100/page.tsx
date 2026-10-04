"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ErrorState, LoadingState, buttonVariants } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCurrentEvent } from "@/lib/current-event";

/** Acceptance route (handoff section 46): load the demo event and open its analysis. */
export default function DemoMcuX100() {
  const router = useRouter();
  const { setEventId } = useCurrentEvent();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api
      .loadDemo()
      .then(({ event }) => {
        setEventId(event.event_id);
        router.replace(`/analysis?event=${encodeURIComponent(event.event_id)}`);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [router, setEventId]);

  if (error) {
    return <ErrorState title="We couldn't load the demo scenario" message={error}
      action={<Link href="/" className={buttonVariants({ variant: "secondary", size: "sm" })}>Back to overview</Link>} />;
  }
  return <LoadingState label="Loading the MCU-X100 demo scenario…" />;
}
