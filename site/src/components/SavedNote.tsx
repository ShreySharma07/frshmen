"use client";
// One line above the filters after someone saves their profile and lands here: what was saved and
// what the list now shows. Shown once per save (SAVED_KEY), dismissable.
import { X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Role } from "@/lib/api";
import { SAVED_KEY, type Filters } from "@/lib/filters";

const ROLE_LABEL: Record<Role, string> = {
  all: "all roles", target: "AI/ML, backend and mobile", ai_ml: "AI/ML", backend: "backend", mobile: "mobile",
};

export function SavedNote({ filters }: { filters: Filters }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    try {
      if (!sessionStorage.getItem(SAVED_KEY)) return;
      sessionStorage.removeItem(SAVED_KEY);
      // Read once from sessionStorage, which only exists in the browser, so it can't be initial state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShown(true);
    } catch {}
  }, []);
  if (!shown) return null;
  const years = filters.years === null ? "any years" : filters.years === 0 ? "freshers (0 years)" : `up to ${filters.years} ${filters.years === 1 ? "year" : "years"}`;
  return (
    <div role="status" className="mx-4 mt-3 flex items-center gap-3 rounded-md border border-line bg-surface px-3 py-2 text-body lg:mx-6">
      <p className="min-w-0 flex-1">
        <span className="font-medium">Profile saved.</span>{" "}
        <span className="text-muted">Showing {ROLE_LABEL[filters.role]} jobs for {years}.</span>{" "}
        <Link href="/profile" className="font-medium text-accent underline underline-offset-2">Edit profile</Link>
      </p>
      <button type="button" onClick={() => setShown(false)} aria-label="Dismiss"
        className="grid size-7 shrink-0 place-items-center rounded-sm text-muted transition-colors duration-quick hover:bg-canvas hover:text-ink">
        <X aria-hidden className="size-4" />
      </button>
    </div>
  );
}
