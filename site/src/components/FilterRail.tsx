import type { Meta, Role } from "@/lib/api";
import { DEFAULTS, isDefault, type Filters, type Posted, type Workplace } from "@/lib/filters";

type Option<T extends string> = { value: T; label: string; n?: number };

/**
 * Wide screens: every filter open in a column beside the list, each choice with the number of open
 * jobs behind it where the pipeline's snapshot has one, so nobody clicks into an empty list.
 * Phones keep the chips (FilterBar), which use the phone's own picker.
 */
export function FilterRail({ filters, meta, onChange }: { filters: Filters; meta: Meta | null; onChange: (f: Filters) => void }) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const roles: Option<Role>[] = [
    { value: "target", label: "Target roles", n: meta?.roles.target },
    { value: "ai_ml", label: "AI/ML", n: meta?.roles.ai_ml },
    { value: "backend", label: "Backend", n: meta?.roles.backend },
    { value: "mobile", label: "Mobile", n: meta?.roles.mobile },
    { value: "all", label: "All roles", n: meta?.roles.all ?? meta?.total },
  ];
  // Keep a country from the URL selectable even if it isn't in the top of the list.
  const top = meta?.countries.slice(0, 8) ?? [];
  const countries: Option<string>[] = [
    { value: "", label: "Anywhere" },
    ...(filters.country && !top.some((c) => c.country === filters.country) ? [{ value: filters.country, label: filters.country }] : []),
    ...top.map((c) => ({ value: c.country, label: c.country, n: c.n })),
  ];
  const work: Option<Workplace>[] = [{ value: "any", label: "Any" }, { value: "remote", label: "Remote" }, { value: "hybrid", label: "Hybrid" }, { value: "onsite", label: "Onsite" }];
  const posted: Option<Posted>[] = [{ value: "any", label: "Any time" }, { value: "24h", label: "New today" }, { value: "7d", label: "Past week" }, { value: "30d", label: "Past month" }];
  return (
    <nav aria-label="Filters" className="sticky top-[72px] hidden max-h-[calc(100vh-88px)] space-y-5 overflow-y-auto pb-4 pl-4 pr-3 lg:block">
      <Group title="Role" options={roles} value={filters.role} onPick={(v) => set({ role: v })} />
      <Group title="Where" options={countries} value={filters.country} onPick={(v) => set({ country: v })} />
      <Group title="Workplace" options={work} value={filters.workplace} onPick={(v) => set({ workplace: v })} />
      <Group title="Posted" options={posted} value={filters.posted} onPick={(v) => set({ posted: v })} />
      {!isDefault({ ...filters, q: "", years: null }) && (
        <button type="button" onClick={() => onChange({ ...DEFAULTS, q: filters.q, years: filters.years })}
          className="px-2 text-meta font-medium text-accent-text underline underline-offset-2">Clear filters</button>
      )}
    </nav>
  );
}

function Group<T extends string>({ title, options, value, onPick }: { title: string; options: Option<T>[]; value: T; onPick: (v: T) => void }) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1 px-2 text-meta text-muted">{title}</legend>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <label key={o.value} className={`flex cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1.5 text-body transition-colors duration-quick has-focus-visible:outline-2 has-focus-visible:outline-ink ${on ? "bg-selected font-medium text-ink shadow-[inset_2px_0_var(--accent)]" : "text-ink/80 hover:bg-surface"}`}>
            <input type="radio" name={title} checked={on} onChange={() => onPick(o.value)} className="sr-only" />
            <span className="truncate">{o.label}</span>
            {o.n != null && <span className="shrink-0 font-mono text-caption text-muted">{o.n.toLocaleString("en")}</span>}
          </label>
        );
      })}
    </fieldset>
  );
}
