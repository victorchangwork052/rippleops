"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

const KEY = "rippleops.currentEvent";

interface CurrentEventCtx {
  eventId: string | null;
  setEventId: (id: string | null) => void;
  /** Product currently open in a detail panel, so the assistant can use it as context. */
  productInView: string | null;
  setProductInView: (id: string | null) => void;
}

const Ctx = createContext<CurrentEventCtx>({
  eventId: null,
  setEventId: () => {},
  productInView: null,
  setProductInView: () => {},
});

/** Remembers which change event the user is working on across pages. */
export function CurrentEventProvider({ children }: { children: ReactNode }) {
  const [eventId, setState] = useState<string | null>(null);
  const [productInView, setProductInView] = useState<string | null>(null);

  useEffect(() => {
    try {
      // Restoring browser-only state after hydration.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState(window.localStorage.getItem(KEY));
    } catch {
      /* storage unavailable: stay in-memory */
    }
  }, []);

  const setEventId = useCallback((id: string | null) => {
    setState(id);
    try {
      if (id) window.localStorage.setItem(KEY, id);
      else window.localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <Ctx.Provider value={{ eventId, setEventId, productInView, setProductInView }}>{children}</Ctx.Provider>
  );
}

export const useCurrentEvent = () => useContext(Ctx);
