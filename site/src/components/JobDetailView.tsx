import { ArrowUpRight, Banknote, Briefcase, ChevronLeft, Clock, MapPin } from "lucide-react";
import type { JobDetail } from "@/lib/api";
import { ATS, blocks, bodyText, highlightParts, techMentioned } from "@/lib/describe";
import { shortDate } from "@/lib/format";
import { CompanyMark } from "./CompanyMark";
import { FitCard } from "./FitCard";
import dynamic from "next/dynamic";
import { useState } from "react";

// Save and fit check load after the page, so they don't count against the job list's first load.
const JobActions = dynamic(() => import("./JobActions").then((m) => m.JobActions), { ssr: false });

/** The right-hand panel (full screen on phones): who, what, where, why it fits, and the posting. */
export function JobDetailView({ job, fitCheck, you, onBack }: { job: JobDetail; fitCheck: boolean; you: number | null; onBack: () => void }) {
  const tech = techMentioned(job.description_text);
  const [panels, setPanels] = useState<HTMLDivElement | null>(null);
  const mode = job.location_type && job.location_type[0].toUpperCase() + job.location_type.slice(1);
  return (
    <article>
      <button type="button" onClick={onBack} className="mb-4 inline-flex items-center gap-1 text-body text-muted lg:hidden">
        <ChevronLeft className="size-4" /> Jobs
      </button>
      <p className="flex items-center gap-2.5 text-body text-muted">
        <CompanyMark company={job.company} size="sm" />
        <span><span className="font-medium text-ink">{job.company}</span> · via {ATS[job.source] ?? job.source}</span>
      </p>
      <h1 className="mt-2 max-w-[22ch] font-display text-headline tracking-[-0.01em] lg:text-[2.375rem] lg:leading-[1.08]">{job.title}</h1>
      {job.salary && (
        <p className="mt-2 inline-flex items-center gap-1.5 text-body font-medium text-ink"><Banknote className="size-3.5 text-muted" />{job.salary}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-body text-muted">
        <span className="inline-flex items-center gap-1.5"><MapPin className="size-3.5" />{[job.location_raw, mode].filter(Boolean).join(" · ") || "Location not stated"}</span>
        {job.employment_type && <span className="inline-flex items-center gap-1.5"><Briefcase className="size-3.5" />{job.employment_type.replace(/([a-z])([A-Z])/, "$1-$2").replace(/-T/, "-t")}</span>}
        <span className="inline-flex items-center gap-1.5"><Clock className="size-3.5" />Posted {shortDate(job.posted_at ?? job.first_seen_at)}</span>
      </div>

      {/* A new key per job replays the highlighter and the ruler: a different reason, shown again. */}
      <div className="mt-6"><FitCard key={job.id} job={job} you={you} /></div>

      {/* The actions stay in reach while a long posting scrolls under them. */}
      {/* Offset by the panel's own top padding (p-5 on phones, py-1 beside the list), so text
          doesn't show through the gap above the bar. */}
      <div className="sticky -top-5 z-10 -mx-1 mt-4 lg:-top-1 flex flex-wrap items-center gap-2 border-b border-line bg-canvas px-1 py-3">
        <a href={job.url} target="_blank" rel="noopener" className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2.5 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
          Apply on {job.company} <ArrowUpRight className="size-3.5" />
          <kbd className="ml-1 hidden rounded-sm border border-on-accent/30 px-1 font-mono text-caption leading-4 opacity-70 lg:inline">A</kbd>
        </a>
        {/* A new key per job: its saved state and fit verdict start fresh. */}
        <JobActions key={job.id} jobId={job.id} title={job.title} company={job.company} fitCheck={fitCheck} panels={panels} />
      </div>
      <div ref={setPanels} className="mt-3 empty:hidden" />

      <div className="mt-7 space-y-3 border-t border-line pt-6 text-body text-ink/85">
        {tech.length > 0 && (
          <div className="mb-5 flex flex-wrap gap-1.5">
            {tech.map((t) => <code key={t} className="rounded-sm border border-line bg-code px-1.5 font-mono text-caption leading-5">{t}</code>)}
          </div>
        )}
        {blocks(bodyText(job.description_text)).map((b, i) =>
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
