import { Check, Minus } from "lucide-react";
import type { JobDetail } from "@/lib/api";
import { FAMILY, earlyCareer, techMentioned } from "@/lib/describe";
import { years } from "@/lib/format";

/**
 * The dark card: the years the posting asks for, the sentence that says so, and a checklist of
 * what the posting states. A missing fact is a grey dash, never a tick.
 */
export function FitCard({ job }: { job: JobDetail }) {
  const y = years(job);
  const quote = job.yoe_evidence ?? (job.batch_years.length ? `For the ${job.batch_years.join(", ")} batch` : null);
  const tech = techMentioned(job.description_text);
  const early = earlyCareer(job.description_text);
  const where = [job.location_raw, job.location_type && job.location_type[0].toUpperCase() + job.location_type.slice(1)].filter(Boolean).join(" · ");
  const rows: [boolean, string][] = [
    [Boolean(job.role_family), job.role_family ? `${FAMILY[job.role_family] ?? job.role_family} role` : "Role not matched"],
    [Boolean(where), where || "Location not stated"],
    [job.batch_years.length > 0, job.batch_years.length ? `${job.batch_years.join(", ")} batch` : "Batch not stated"],
    ...(early ? [[true, "Early-career candidates considered"] as [boolean, string]] : []),
    [tech.length > 0, tech.length ? `Mentions ${tech.slice(0, 4).join(", ")}` : "No tech stack named"],
    [job.visa_sponsorship === "yes", job.visa_sponsorship === "yes" ? "Visa sponsorship offered" : job.visa_sponsorship === "no" ? "No visa sponsorship" : "Visa not mentioned"],
  ];
  return (
    <div className="grid gap-5 rounded-lg bg-card p-5 text-card-text sm:grid-cols-2">
      <div>
        {y == null ? (
          <>
            <div className="font-mono text-display font-semibold text-card-muted">—</div>
            <p className="mt-1 text-meta text-card-muted">The posting doesn&apos;t state years of experience.</p>
          </>
        ) : (
          <div className="font-mono text-display font-semibold text-card-accent">
            {y} <span className="text-base">years</span>
          </div>
        )}
        {quote && <blockquote className="mt-3 border-l-2 border-card-accent/40 pl-3 text-meta italic text-card-muted">{quote}</blockquote>}
      </div>
      <ul className="space-y-2 sm:border-l sm:border-card-line sm:pl-5">
        {rows.map(([ok, text]) => (
          <li key={text} className={`flex items-start gap-2 text-body ${ok ? "" : "text-card-muted"}`}>
            {ok ? <Check aria-label="Stated" className="mt-0.5 size-4 shrink-0 text-card-accent" /> : <Minus aria-label="Not stated" className="mt-0.5 size-4 shrink-0 text-card-muted" />}
            {text}
          </li>
        ))}
      </ul>
    </div>
  );
}
