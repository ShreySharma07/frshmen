import type { JobSummary } from "@/lib/api";
import { place, shortDate, years } from "@/lib/format";

/** One job in the list: title, company · place · date, and the years it asks for. */
export function JobRow({ job, selected, isNew, onSelect }: { job: JobSummary; selected: boolean; isNew: boolean; onSelect: () => void }) {
  const y = years(job);
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? "true" : undefined}
        className={`flex w-full items-start gap-3 rounded-lg px-4 py-3.5 text-left transition-colors duration-quick ${selected ? "lg:bg-selected" : ""} hover:bg-surface`}
      >
        <span aria-hidden className="grid size-8 shrink-0 place-items-center text-body font-semibold text-muted">{job.company[0]}</span>
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-body font-medium">{job.title}</span>
          <span className="mt-0.5 block truncate text-meta text-muted">
            {isNew && <span className="font-medium text-accent">New · </span>}
            {job.company} · {place(job)} · {shortDate(job.posted_at ?? job.first_seen_at)}
          </span>
          {job.salary && <span className="mt-0.5 block truncate text-meta text-ink/80">{job.salary}</span>}
        </span>
        <span className={`shrink-0 pt-0.5 font-mono text-caption ${y == null ? "text-muted" : "font-medium text-accent"}`}>
          {y == null ? "Not stated" : `${y} yrs`}
        </span>
      </button>
    </li>
  );
}
