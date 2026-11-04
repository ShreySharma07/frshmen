"use client";
// The header's sections (docs/decisions.md, 2026-11-04): Jobs is the list; Board and Insights are
// the signed-in person's own pages, so they show only once signed in. Beside the logo from sm up;
// on phones the same links sit in the profile menu, where there's room.
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { readSession, subscribeSession } from "@/lib/session";
import { IntentLink } from "./IntentLink";

export const SECTIONS = [
  { href: "/", label: "Jobs", signedIn: false },
  { href: "/profile", label: "Board", signedIn: true },
  { href: "/insights", label: "Insights", signedIn: true },
] as const;

export function SiteNav() {
  const session = useSyncExternalStore(subscribeSession, readSession, () => null);
  const path = usePathname();
  if (!session) return null; // signed out, "Jobs" alone isn't navigation
  return (
    <nav aria-label="Sections" className="hidden items-center gap-1 sm:flex">
      {SECTIONS.map((s) => {
        const current = s.href === "/" ? path === "/" : path.startsWith(s.href);
        return (
          <IntentLink key={s.href} href={s.href} aria-current={current ? "page" : undefined}
            className={`rounded-md px-2.5 py-1.5 text-meta font-medium transition-colors duration-quick ${current ? "bg-surface text-ink" : "text-muted hover:text-ink"}`}>
            {s.label}
          </IntentLink>
        );
      })}
    </nav>
  );
}
