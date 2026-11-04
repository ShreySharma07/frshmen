"use client";
// Cmd+K (Ctrl+K): jump anywhere, apply a common filter, or search jobs by typing
// (docs/decisions.md, 2026-11-04). Loaded the first time someone opens it, so the job list
// doesn't carry it. A combobox: type to filter, arrows to move, Enter to go, Escape to close.
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { DEFAULTS, toSearch, type Filters } from "@/lib/filters";
import { readSession, signOut } from "@/lib/session";

interface Command { id: string; label: string; group: string; run: () => void }

const jobs = (patch: Partial<Filters>) => "/" + toSearch({ ...DEFAULTS, ...patch });

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => { onClose(); router.push(href); };
    const signedIn = Boolean(readSession());
    return [
      { id: "jobs", label: "Jobs", group: "Go to", run: go("/") },
      ...(signedIn ? [
        { id: "board", label: "Board", group: "Go to", run: go("/profile") },
        { id: "insights", label: "Insights", group: "Go to", run: go("/insights") },
        { id: "details", label: "Your details", group: "Go to", run: go("/profile/edit") },
      ] : [{ id: "login", label: "Sign in", group: "Go to", run: go("/login") }]),
      { id: "f-fresher", label: "Jobs for freshers (0 years)", group: "Filter jobs", run: go(jobs({ years: 0 })) },
      { id: "f-1yr", label: "Jobs asking up to 1 year", group: "Filter jobs", run: go(jobs({ years: 1 })) },
      { id: "f-aiml", label: "AI/ML roles", group: "Filter jobs", run: go(jobs({ role: "ai_ml" })) },
      { id: "f-backend", label: "Backend roles", group: "Filter jobs", run: go(jobs({ role: "backend" })) },
      { id: "f-remote", label: "Remote jobs", group: "Filter jobs", run: go(jobs({ workplace: "remote" })) },
      { id: "f-india", label: "Jobs in India", group: "Filter jobs", run: go(jobs({ country: "India" })) },
      { id: "f-today", label: "New today", group: "Filter jobs", run: go(jobs({ posted: "24h" })) },
      { id: "theme", label: "Switch light / dark", group: "Actions", run: () => { onClose(); toggleTheme(); } },
      ...(signedIn ? [{ id: "signout", label: "Sign out", group: "Actions", run: async () => { onClose(); await signOut(); router.push("/"); } }] : []),
    ];
  }, [onClose, router]);

  const q = query.trim().toLowerCase();
  const shown = useMemo(() => {
    const hits = commands.filter((c) => !q || c.label.toLowerCase().includes(q));
    // Typing always offers a plain job search for the words, first.
    return q ? [{ id: "search", label: `Search jobs for "${query.trim()}"`, group: "Search", run: () => { onClose(); router.push(jobs({ q: query.trim() })); } }, ...hits] : hits;
  }, [commands, q, query, onClose, router]);
  const current = Math.min(active, Math.max(shown.length - 1, 0));

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    input.current?.focus();
    return () => before?.focus();
  }, []);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((current + 1) % Math.max(shown.length, 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((current - 1 + shown.length) % Math.max(shown.length, 1)); }
    else if (e.key === "Enter") { e.preventDefault(); shown[current]?.run(); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 px-4 pt-[12vh] motion-safe:animate-[fade-in_150ms_var(--ease-out-soft)]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-label="Command palette" className="w-full max-w-lg overflow-hidden rounded-lg border border-line bg-canvas shadow-menu">
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search aria-hidden className="size-4 text-muted" />
          <input ref={input} value={query} onChange={(e) => { setQuery(e.target.value); setActive(0); }} onKeyDown={onKey}
            role="combobox" aria-expanded="true" aria-controls={listId} aria-activedescendant={shown[current] ? `${listId}-${shown[current].id}` : undefined}
            placeholder="Go to, filter, or search jobs…" aria-label="Command"
            className="h-12 w-full bg-transparent text-base outline-none placeholder:text-muted" />
          <kbd className="rounded-sm border border-line px-1.5 font-mono text-caption text-muted">Esc</kbd>
        </div>
        <ul id={listId} role="listbox" className="max-h-[50vh] overflow-y-auto py-1">
          {shown.map((c, i) => (
            <li key={c.id} id={`${listId}-${c.id}`} role="option" aria-selected={i === current}
              onMouseMove={() => setActive(i)} onClick={() => c.run()}
              className={`flex cursor-pointer items-center justify-between px-3 py-2 text-body ${i === current ? "bg-selected text-ink" : ""}`}>
              {c.label}
              <span className="text-caption text-muted">{c.group}</span>
            </li>
          ))}
          {shown.length === 0 && <li className="px-3 py-3 text-body text-muted">Nothing matches.</li>}
        </ul>
      </div>
    </div>
  );
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("aventra.theme", next); } catch {}
  dispatchEvent(new Event("aventra:theme")); // ThemeToggle's icon follows
}
