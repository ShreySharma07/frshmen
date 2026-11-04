import { Check, Minus, X } from "lucide-react";
import type { JobDetail } from "@/lib/api";
import { FAMILY, earlyCareer, techMentioned } from "@/lib/describe";
import { years } from "@/lib/format";

type State = "match" | "unknown" | "mismatch";
type Row = [State, string];
const STATE = {
  match: { Icon: Check, tone: "text-card-pass", label: "Matches" },
  unknown: { Icon: Minus, tone: "text-card-muted", label: "Not stated" },
  mismatch: { Icon: X, tone: "text-card-fail", label: "Against you" },
} as const;
const LEVEL: Record<string, string> = { fresher: "fresher", maybe: "unclear", experienced: "experienced" };

/**
 * The dark card: the years the posting asks for, the sentence that says so, and a checklist of
 * what the posting states. A missing fact is a grey dash, never a tick;
 * one that works against you is a red cross.
 */
export function FitCard({ job }: { job: JobDetail }) {
  const y = years(job);
  const quote = job.yoe_evidence ?? (job.batch_years.length ? `For the ${job.batch_years.join(", ")} batch` : null);
  const tech = techMentioned(job.description_text);
  const early = earlyCareer(job.description_text);
  const where = [job.location_raw, job.location_type && job.location_type[0].toUpperCase() + job.location_type.slice(1)].filter(Boolean).join(" · ");
  // Each fact is a match (the posting states it, in your favour), unknown (it doesn't say) or a
  // mismatch (it states something against you). Colour and icon both carry the state.
  const visa: Row = job.visa_sponsorship === "yes" ? ["match", "Visa sponsorship offered"]
    : job.visa_sponsorship === "no" ? ["mismatch", "No visa sponsorship"] : ["unknown", "Visa not mentioned"];
  const rows: Row[] = [
    job.role_family ? ["match", `${FAMILY[job.role_family] ?? job.role_family} role`] : ["mismatch", "Not one of your roles"],
    where ? ["match", where] : ["unknown", "Location not stated"],
    job.batch_years.length ? ["match", `${job.batch_years.join(", ")} batch`] : ["unknown", "Batch not stated"],
    ...(early ? [["match", "Early-career candidates considered"] as Row] : []),
    tech.length ? ["match", `Mentions ${tech.slice(0, 4).join(", ")}`] : ["unknown", "No tech stack named"],
    visa,
  ];
  return (
    <div className="grid gap-5 rounded-lg bg-card p-5 text-card-text sm:grid-cols-2">
      <div className="flex flex-col">
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
        {/* Why the label, at the foot of the column: the reason the rules gave. */}
        <p className="mt-4 border-t border-card-line pt-3 text-meta text-card-muted sm:mt-auto">
          Labelled <span className="font-medium text-card-text">{LEVEL[job.level]}</span>
          {job.level_reason ? <> · {job.level_reason}</> : null}
        </p>
      </div>
      <ul className="space-y-2 sm:border-l sm:border-card-line sm:pl-5">
        {rows.map(([state, text]) => {
          const { Icon, tone, label } = STATE[state];
          return (
            <li key={text} className={`flex items-start gap-2 text-body ${state === "unknown" ? "text-card-muted" : ""}`}>
              <Icon aria-label={label} className={`mt-0.5 size-4 shrink-0 ${tone}`} />
              {text}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
