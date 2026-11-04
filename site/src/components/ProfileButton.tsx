"use client";
// Top right of every page: "Sign in", or the person's initial opening Profile and Sign out.
// Reads the stored session itself (lib/session.ts), so the job list stays free of supabase-js.
import { IntentLink } from "./IntentLink";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { readSession, signOut, subscribeSession } from "@/lib/session";
import { SECTIONS } from "./SiteNav";

export function ProfileButton() {
  const session = useSyncExternalStore(subscribeSession, readSession, () => null);
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Close on Escape or a click outside, like any menu.
  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); root.current?.querySelector("button")?.focus(); } };
    const onClick = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    addEventListener("keydown", onKey);
    addEventListener("mousedown", onClick);
    return () => { removeEventListener("keydown", onKey); removeEventListener("mousedown", onClick); };
  }, [open]);

  if (!session) {
    return (
      <IntentLink href="/login" className="inline-flex h-9 shrink-0 items-center rounded-md border border-line px-3 text-meta font-medium transition-colors duration-quick hover:bg-surface">
        Sign in
      </IntentLink>
    );
  }
  const initial = (session.name || session.email || "?").trim()[0]?.toUpperCase() ?? "?";
  return (
    <div ref={root} className="relative shrink-0">
      <button type="button" aria-haspopup="menu" aria-expanded={open} aria-label={`Account: ${session.email}`}
        onClick={() => setOpen((o) => !o)}
        className="grid size-9 place-items-center rounded-full bg-accent font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
        {initial}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-11 z-40 w-56 overflow-hidden rounded-lg border border-line bg-canvas py-1 shadow-menu">
          <p className="truncate px-3 py-2 text-meta text-muted">{session.email}</p>
          {/* The header's section links, for phones where the header has no room for them. */}
          {SECTIONS.map((s) => (
            <IntentLink key={s.href} role="menuitem" href={s.href} onClick={() => setOpen(false)} className="block px-3 py-2 text-body hover:bg-surface focus:bg-surface focus:outline-none sm:hidden">
              {s.label}
            </IntentLink>
          ))}
          <IntentLink role="menuitem" href="/profile/edit" onClick={() => setOpen(false)} className="block px-3 py-2 text-body hover:bg-surface focus:bg-surface focus:outline-none">
            Your details
          </IntentLink>
          <button role="menuitem" type="button" onClick={async () => { setOpen(false); await signOut(); router.push("/"); }}
            className="block w-full px-3 py-2 text-left text-body hover:bg-surface focus:bg-surface focus:outline-none">
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
