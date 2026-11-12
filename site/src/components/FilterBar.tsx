import { ChevronDown } from "lucide-react";
import { DEFAULTS, isDefault, type Filters, type Posted, type Workplace } from "@/lib/filters";
import type { Role } from "@/lib/api";

/**
 * Filter chips above the job list. Each is a real <select> dressed as a chip: no extra JavaScript, keyboard and
 * screen-reader support for free, and the phone's own picker on mobile. `field-sizing: content`
 * sizes each to its current value (browsers without it fall back to the widest option).
 */
export function FilterBar({ filters, countries, onChange }: {
  filters: Filters;
  countries: string[];
  onChange: (f: Filters) => void;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  return (
    <div className="flex items-center gap-2 overflow-x-auto border-b border-line px-4 py-2.5 [scrollbar-width:none] lg:px-6">
      {/* Years first: the question Aventra answers. Filled marigold when set, like a highlighted word. */}
      <Chip label="I have" strong on={filters.years !== null} value={filters.years === null ? "" : String(filters.years)}
        onChange={(v) => set({ years: v === "" ? null : Number(v) })}>
        <option value="">any experience</option>
        <option value="0">0 years (fresher)</option>
        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} {n === 1 ? "year" : "years"}</option>)}
      </Chip>
      <Chip label="Role" on={filters.role !== DEFAULTS.role} value={filters.role} onChange={(v) => set({ role: v as Role })}>
        <option value="target">AI/ML, backend, mobile</option>
        <option value="ai_ml">AI/ML</option>
        <option value="backend">Backend</option>
        <option value="mobile">Mobile</option>
        <option value="all">All roles</option>
      </Chip>
      <Chip label="Where" on={filters.country !== ""} value={filters.country} onChange={(v) => set({ country: v })}>
        <option value="">Anywhere</option>
        {/* Keep a country from the URL selectable even if it isn't in the list. */}
        {[...new Set([...(filters.country ? [filters.country] : []), ...countries])].map((c) => <option key={c} value={c}>{c}</option>)}
      </Chip>
      <Chip label="Work" on={filters.workplace !== "any"} value={filters.workplace} onChange={(v) => set({ workplace: v as Workplace })}>
        <option value="any">Any</option>
        <option value="remote">Remote</option>
        <option value="hybrid">Hybrid</option>
        <option value="onsite">Onsite</option>
      </Chip>
      <Chip label="Posted" on={filters.posted !== "any"} value={filters.posted} onChange={(v) => set({ posted: v as Posted })}>
        <option value="any">Any time</option>
        <option value="24h">New today</option>
        <option value="7d">Past week</option>
        <option value="30d">Past month</option>
      </Chip>
      {!isDefault({ ...filters, q: "" }) && (
        <button type="button" onClick={() => onChange({ ...DEFAULTS, q: filters.q })}
          className="shrink-0 px-2 text-meta font-medium text-accent-text underline-offset-2 hover:underline">Clear all</button>
      )}
    </div>
  );
}

function Chip({ label, on, strong, value, onChange, children }: {
  label: string; on: boolean; strong?: boolean; value: string; onChange: (v: string) => void; children: React.ReactNode;
}) {
  return (
    // An active filter carries the accent (border, tint, value), so a glance shows what's narrowing the list.
    <label className={`relative inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border pl-2.5 transition-colors duration-quick focus-within:ring-2 focus-within:ring-accent/40 ${on ? (strong ? "border-accent bg-accent" : "border-ink bg-selected") : "border-line hover:bg-surface"}`}>
      <span className={`text-meta ${on && strong ? "text-on-accent/70" : "text-muted"}`}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className={`h-full cursor-pointer appearance-none bg-transparent pr-7 text-meta font-medium outline-none [field-sizing:content] [&>option]:bg-canvas [&>option]:text-ink ${on && strong ? "text-on-accent" : "text-ink"}`}>
        {children}
      </select>
      <ChevronDown aria-hidden className={`pointer-events-none absolute right-2 size-3.5 ${on && strong ? "text-on-accent" : on ? "text-ink" : "text-muted"}`} />
    </label>
  );
}
