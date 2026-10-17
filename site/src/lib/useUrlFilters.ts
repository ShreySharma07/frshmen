"use client";
// The URL is the one place filters live. Components read them through this hook and change them
// with navigate(); Back/Forward (popstate) re-read the URL, so history just works.
import { useCallback, useMemo, useSyncExternalStore } from "react";
import { fromSearch, toSearch, type Filters } from "./filters";

const EVENT = "kario:navigate";

function subscribe(onChange: () => void) {
  addEventListener("popstate", onChange);
  addEventListener(EVENT, onChange);
  return () => { removeEventListener("popstate", onChange); removeEventListener(EVENT, onChange); };
}

/** null while the page is being printed at build time (there is no URL then). */
export function useUrlFilters(): [Filters | null, (f: Filters, how?: "push" | "replace") => void] {
  const search = useSyncExternalStore(subscribe, () => location.search, () => null);
  const filters = useMemo(() => (search === null ? null : fromSearch(search)), [search]);
  const navigate = useCallback((f: Filters, how: "push" | "replace" = "push") => {
    const next = toSearch(f);
    if (next === location.search) return;
    history[how === "push" ? "pushState" : "replaceState"](null, "", next || location.pathname);
    dispatchEvent(new Event(EVENT));
  }, []);
  return [filters, navigate];
}
