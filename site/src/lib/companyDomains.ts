// Company name -> website domain, for logos (scripts/export_logos.py writes the file). Fetched
// once, after the page is up, so it never delays the list; until it arrives, tints show.
import { useSyncExternalStore } from "react";

let domains: Record<string, string> = {};
const listeners = new Set<() => void>();
let started = false;

function load() {
  if (started) return;
  started = true;
  fetch("/company-domains.json")
    .then((r) => (r.ok ? r.json() : {}))
    .then((d: Record<string, string>) => { domains = d; listeners.forEach((l) => l()); })
    .catch(() => {});
}

function subscribe(onChange: () => void) {
  load();
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

export function useCompanyDomain(company: string): string | null {
  return useSyncExternalStore(subscribe, () => domains[company] ?? null, () => null);
}
