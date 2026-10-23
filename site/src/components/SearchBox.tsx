"use client";
import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/** Search title or company. Waits for a pause in typing before asking the API; "/" focuses it. */
export function SearchBox({ value, onSearch }: { value: string; onSearch: (q: string) => void }) {
  const [draft, setDraft] = useState(value);
  const [seen, setSeen] = useState(value);
  if (value !== seen) { setSeen(value); setDraft(value); } // the URL changed (Back, Clear): follow it
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (draft === value) return;
    const t = setTimeout(() => onSearch(draft), 300);
    return () => clearTimeout(t);
  }, [draft, value, onSearch]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || (e.target instanceof HTMLElement && e.target.closest("input, textarea, select"))) return;
      e.preventDefault();
      input.current?.focus();
    };
    addEventListener("keydown", onKey);
    // Arrived from the landing page's "/": the reader wants to type straight away.
    try {
      if (sessionStorage.getItem("kario:search")) { sessionStorage.removeItem("kario:search"); input.current?.focus(); }
    } catch {}
    return () => removeEventListener("keydown", onKey);
  }, []);

  return (
    <label className="flex h-9 w-full max-w-[380px] items-center gap-2 rounded-md border border-line bg-canvas px-3 text-body text-muted focus-within:border-ink/40">
      <Search aria-hidden className="size-4 shrink-0" />
      <input ref={input} type="search" value={draft} maxLength={100} aria-label="Search jobs by title or company"
        placeholder="Search title or company…" onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") e.currentTarget.blur(); }}
        className="w-full bg-transparent text-ink outline-none placeholder:text-muted" />
      <kbd className="hidden rounded-sm border border-line bg-surface px-1.5 font-mono text-caption sm:inline">/</kbd>
    </label>
  );
}
