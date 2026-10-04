"use client";

import { Check, ChevronDown, Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { inputClass } from "@/components/ui";
import { cn } from "@/lib/utils";

export interface ComboOption {
  value: string;
  label: string;
  /** Secondary text shown under the label and included in search. */
  detail?: string;
  /** Right-aligned tag, e.g. an approval status. */
  badge?: ReactNode;
  group?: string;
}

const MAX_VISIBLE = 100;

/**
 * Searchable dropdown. Typing filters the list; the typed text is kept as the
 * value so a part that is not in the list (e.g. from an uploaded notice) still
 * shows and can be corrected.
 */
export function Combobox({ id, value, onChange, options, placeholder, required, emptyText = "No matches" }: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  options: ComboOption[];
  placeholder?: string;
  required?: boolean;
  emptyText?: string;
}) {
  const listId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null); // null = not filtering, show all
  const [active, setActive] = useState(0);

  const filtered = useMemo(() => {
    const q = query?.trim().toLowerCase();
    const hits = q
      ? options.filter((o) => `${o.value} ${o.label} ${o.detail ?? ""}`.toLowerCase().includes(q))
      : options;
    return hits.slice(0, MAX_VISIBLE);
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) { setOpen(false); setQuery(null); }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  useEffect(() => {
    if (open) list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function close() {
    setOpen(false);
    setQuery(null);
  }

  function pick(o: ComboOption) {
    onChange(o.value);
    close();
  }

  function openList() {
    if (open) return;
    setActive(Math.max(0, options.findIndex((o) => o.value === value)));
    setOpen(true);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return openList();
      const n = filtered.length;
      if (n) setActive((a) => (a + (e.key === "ArrowDown" ? 1 : -1) + n) % n);
    } else if (e.key === "Enter" && open && filtered[active]) {
      e.preventDefault();
      pick(filtered[active]);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      close();
    } else if (e.key === "Tab") {
      close();
    }
  }

  const selected = options.find((o) => o.value === value);

  return (
    <div ref={wrap} className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && filtered[active] ? `${listId}-${active}` : undefined}
        autoComplete="off"
        required={required}
        className={cn(inputClass, "pl-9 pr-9")}
        value={query ?? value}
        placeholder={placeholder}
        onFocus={openList}
        onClick={openList}
        onChange={(e) => { setQuery(e.target.value); onChange(e.target.value); setOpen(true); setActive(0); }}
        onKeyDown={onKeyDown}
      />
      <button type="button" tabIndex={-1} aria-label="Show options"
        className="absolute right-1.5 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-subtle hover:text-text"
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => { if (open) close(); else { document.getElementById(id)?.focus(); openList(); } }}>
        <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {selected && !open && selected.label !== selected.value && (
        <span className="pointer-events-none absolute right-10 top-1/2 max-w-[45%] -translate-y-1/2 truncate text-xs text-subtle">
          {selected.label}
        </span>
      )}
      {open && (
        <ul ref={list} id={listId} role="listbox"
          className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-surface py-1 shadow-lg">
          {filtered.length === 0 && <li className="px-3 py-2 text-sm text-subtle">{emptyText}</li>}
          {filtered.map((o, i) => {
            const header = o.group && o.group !== filtered[i - 1]?.group ? o.group : null;
            return (
              <li key={o.value} role="presentation">
                {header && <div className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-subtle">{header}</div>}
                <div id={`${listId}-${i}`} role="option" aria-selected={o.value === value} data-index={i}
                  className={cn("flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm", i === active && "bg-primary-soft")}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(o)}>
                  <Check className={cn("size-4 shrink-0 text-primary", o.value !== value && "invisible")} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-text">
                      {o.label === o.value ? o.value : <>{o.value} <span className="font-normal text-muted">· {o.label}</span></>}
                    </span>
                    {o.detail && <span className="block truncate text-xs text-subtle">{o.detail}</span>}
                  </span>
                  {o.badge}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
