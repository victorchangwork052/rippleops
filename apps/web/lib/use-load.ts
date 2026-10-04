"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { errorMessage } from "./api";

/**
 * Load data on mount / when `key` changes, and refetch after "Reset Demo".
 * Loaders derived from other loaded data should pass `refetchOnReset: false`;
 * they update through their key instead.
 */
export function useLoad<T>(fn: (() => Promise<T>) | null, key: string, { refetchOnReset = true } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(fn !== null);
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  const reload = useCallback(async () => {
    const f = fnRef.current;
    if (!f) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await f());
    } catch (err) {
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [key, reload]);

  useEffect(() => {
    if (!refetchOnReset) return;
    const onReset = () => void reload();
    window.addEventListener("rippleops:reset", onReset);
    return () => window.removeEventListener("rippleops:reset", onReset);
  }, [reload, refetchOnReset]);

  return { data, error, loading, reload, setData };
}
