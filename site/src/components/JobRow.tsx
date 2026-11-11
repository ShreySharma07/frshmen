import type { JobSummary } from "@/lib/api";
import { place, shortDate, years } from "@/lib/format";
import { CompanyMark } from "./CompanyMark";
import { Ruler } from "./Ruler";

/** One job in the list: title, company, place and date, and on the right the years it asks for,
 *  as a number and on the ruler (`you` = the years picked in the dial, drawn as the tick). */
export function JobRow({ job, selected, isNew, you, onSelect }: { job: JobSummary; selected: boolean; isNew: boolean; you: number | null; onSelect: () => void }) {
  const y = years(job);
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? "true" : undefined}
        className={`flex w-full items-start gap-3 rounded-lg px-4 py-3.5 text-left transition-colors duration-quick ${selected ? "max-lg:hover:bg-surface lg:bg-selected" : "hover:bg-surface"}`}
      >
        <CompanyMark company={job.company} />
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-body font-medium">
            {isNew && <span className="mr-1.5 rounded-sm bg-mark px-1 text-caption font-semibold">New</span>}
            {job.title}
          </span>
          <span className="mt-0.5 block truncate text-meta text-muted">
            {[job.company, place(job), shortDate(job.posted_at ?? job.first_seen_at)].filter(Boolean).join(" · ")}
          </span>
          {job.salary && <span className="mt-0.5 block truncate text-meta text-ink/80">{job.salary}</span>}
        </span>
        <span className="w-16 shrink-0">
          <span className={`mb-1.5 block text-right ${y == null ? "pt-1 text-caption text-muted" : "font-display text-[1.375rem] leading-none"}`}>
            {y == null ? "Not stated" : <>{y} <span className="font-sans text-caption text-muted">{y === "1" ? "yr" : "yrs"}</span></>}
          </span>
          <Ruler job={job} you={you} />
        </span>
      </button>
    </li>
  );
}
