"use client";
// The bar across the top of a page: what the page is, its own controls (search, a view switch),
// then theme and the profile button, top right on every page.
import { use } from "react";
import { ProfileButton } from "@/components/ProfileButton";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LogoContext } from "./AppChrome";

export function PageBar({ title, sub, children }: { title: string; sub?: React.ReactNode; children?: React.ReactNode }) {
  const logo = use(LogoContext);
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-canvas/90 px-4 backdrop-blur-md lg:px-6">
      <span className="shrink-0 lg:hidden">{logo}</span>
      <h1 className="text-base font-semibold max-lg:sr-only">{title}</h1>
      {sub && <p className="min-w-0 truncate text-body text-muted max-lg:hidden" aria-live="polite">{sub}</p>}
      <div className="ml-auto flex min-w-0 items-center gap-2">
        {children}
        <ThemeToggle />
        <ProfileButton />
      </div>
    </header>
  );
}

/** Two or three views of the same thing (Board, List). The dark pill slides to the chosen one. */
export function ViewSwitch<T extends string>({ label, options, value, onChange }: {
  label: string; options: readonly { v: T; label: string }[]; value: T; onChange: (v: T) => void;
}) {
  const i = Math.max(options.findIndex((o) => o.v === value), 0);
  return (
    <div role="group" aria-label={label} className="relative grid h-9 shrink-0 rounded-lg border border-line bg-card p-0.5 text-meta font-medium"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      <span aria-hidden className="absolute inset-y-0.5 left-0.5 rounded-md bg-ink transition-transform duration-move ease-out-soft"
        style={{ width: `calc((100% - 4px) / ${options.length})`, transform: `translateX(${i * 100}%)` }} />
      {options.map((o) => (
        <button key={o.v} type="button" aria-pressed={o.v === value} onClick={() => onChange(o.v)}
          className={`relative px-3.5 transition-colors duration-move ${o.v === value ? "text-canvas" : "text-muted hover:text-ink"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
