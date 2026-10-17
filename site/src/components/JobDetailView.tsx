import { ArrowUpRight, Briefcase, ChevronLeft, Clock, MapPin } from "lucide-react";
import type { JobDetail } from "@/lib/api";
import { ATS, blocks, highlightParts, techMentioned } from "@/lib/describe";
import { shortDate } from "@/lib/format";
import { FitCard } from "./FitCard";

/** The right-hand panel (full screen on phones): who, what, where, why it fits, and the posting. */
export function JobDetailView({ job, onBack }: { job: JobDetail; onBack: () => void }) {
  const tech = techMentioned(job.description_text);
  const mode = job.location_type && job.location_type[0].toUpperCase() + job.location_type.slice(1);
  return (
    <article>
      <button type="button" onClick={onBack} className="mb-4 inline-flex items-center gap-1 text-body text-muted lg:hidden">
        <ChevronLeft className="size-4" /> Jobs
      </button>
      <p className="text-body text-muted">
        <span className="font-medium text-ink">{job.company}</span> · via {ATS[job.source] ?? job.source}
      </p>
      <h1 className="mt-2 text-title font-medium tracking-tight">{job.title}</h1>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-body text-muted">
        <span className="inline-flex items-center gap-1.5"><MapPin className="size-3.5" />{[job.location_raw, mode].filter(Boolean).join(" · ") || "Location not stated"}</span>
        {job.employment_type && <span className="inline-flex items-center gap-1.5"><Briefcase className="size-3.5" />{job.employment_type.replace(/([a-z])([A-Z])/, "$1-$2").replace(/-T/, "-t")}</span>}
        <span className="inline-flex items-center gap-1.5"><Clock className="size-3.5" />Posted {shortDate(job.posted_at ?? job.first_seen_at)}</span>
      </div>

      <div className="mt-5"><FitCard job={job} /></div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <a href={job.url} target="_blank" rel="noopener" className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2.5 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
          Apply on {job.company} <ArrowUpRight className="size-3.5" />
          <kbd className="ml-1 hidden rounded-sm border border-on-accent/30 px-1 font-mono text-caption leading-4 opacity-70 lg:inline">A</kbd>
        </a>
      </div>

      <div className="mt-7 space-y-3 border-t border-line pt-6 text-body text-ink/85">
        {tech.length > 0 && (
          <div className="mb-5 flex flex-wrap gap-1.5">
            {tech.map((t) => <code key={t} className="rounded-sm border border-line bg-code px-1.5 font-mono text-caption leading-5">{t}</code>)}
          </div>
        )}
        {blocks(job.description_text).map((b, i) =>
          b.kind === "heading" ? <h2 key={i} className="pt-3 text-meta font-medium text-muted">{b.text}</h2>
          : b.kind === "list" ? (
            <ul key={i} className="list-disc space-y-1.5 pl-4 marker:text-faint">
              {b.items.map((item, k) => <li key={k}><Marked text={item} tech={tech} /></li>)}
            </ul>
          ) : <p key={i}><Marked text={b.text} tech={tech} /></p>,
        )}
      </div>
    </article>
  );
}

function Marked({ text, tech }: { text: string; tech: string[] }) {
  return highlightParts(text, tech).map((p, i) =>
    p.mark ? <code key={i} className="rounded-sm border border-line bg-code px-1 font-mono text-caption">{p.text}</code> : p.text,
  );
}
