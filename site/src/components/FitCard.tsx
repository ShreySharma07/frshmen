import { Check, Minus, X } from "lucide-react";
import type { JobDetail } from "@/lib/api";
import { FAMILY, earlyCareer, techMentioned } from "@/lib/describe";
import { years } from "@/lib/format";
import { Ruler, RulerScale, asks } from "./Ruler";

type State = "match" | "unknown" | "mismatch";
type Row = [State, string];
const STATE = {
  match: { Icon: Check, tone: "text-card-pass", label: "Matches" },
  unknown: { Icon: Minus, tone: "text-card-muted", label: "Not stated" },
  mismatch: { Icon: X, tone: "text-card-fail", label: "Against you" },
} as const;
const LEVEL: Record<string, string> = { fresher: "fresher", maybe: "unclear", experienced: "experienced" };

// The words inside the quoted line that carry the decision: "3+ years of experience", "2026 batch".
const DECIDING = /\d+\s*(?:(?:[–-]|to)\s*\d+)?\+?\s*(?:years?|yrs?)(?:\s+of\s+(?:[a-z-]+\s+){0,2}experience)?|new[- ]grad(?:uate)?s?|fresh(?:er|\s+graduate)s?|20\d\d\s+(?:batch|graduates?)/i;

/** The quote with its deciding words under the highlighter. */
function Quote({ text }: { text: string }) {
  const m = DECIDING.exec(text);
  if (!m) return <>{text}</>;
  return <>{text.slice(0, m.index)}<mark className="hl bg-transparent text-inherit">{m[0]}</mark>{text.slice(m.index + m[0].length)}</>;
}

/** One sentence: what the posting asks against the years picked in the dial. */
function verdict(job: JobDetail, you: number | null): React.ReactNode {
  const a = asks(job);
  if (!a) return "The posting doesn't state years of experience, so check the description before applying.";
  const ask = a.min === 0 && a.max === 0 ? "Open to freshers." : a.open ? `Asks for ${a.min} or more years.` : a.max !== a.min ? `Asks for ${a.min} to ${a.max} years.` : `Asks for ${a.min} ${a.min === 1 ? "year" : "years"}.`;
  if (you == null) return ask;
  const have = `You have ${you}.`;
  return a.min <= you
    ? <>{ask} {have} <span className="font-medium text-card-pass">It fits.</span></>
    : <>{ask} {have} <span className="font-medium text-card-fail">It asks for more.</span></>;
}

/**
 * The evidence card: the years the posting asks for, the sentence that says so with the deciding
 * words highlighted, the same years on a ruler against yours, and a checklist of what else the
 * posting states. A missing fact is a grey dash, never a tick; one that works against you is a cross.
 */
export function FitCard({ job, you = null }: { job: JobDetail; you?: number | null }) {
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
    <div className="rounded-lg border border-card-line bg-card p-5 text-card-text sm:p-6">
      <div className="flex items-start gap-5">
        <div className="shrink-0 font-display text-hero text-card-accent">
          {y ?? "?"}
          <span className="block font-sans text-meta text-card-muted">{y == null ? "years not stated" : y === "1" ? "year" : "years"}</span>
        </div>
        {quote && (
          <figure className="min-w-0 border-l border-card-line pl-5">
            <blockquote className="font-display text-[1.25rem] leading-[1.35] sm:text-[1.375rem]">“<Quote text={quote} />”</blockquote>
            <figcaption className="mt-2 text-meta text-card-muted">The line in the posting that decided this.</figcaption>
          </figure>
        )}
      </div>

      <div className="mt-6">
        <Ruler job={job} you={you} size="lg" />
        <RulerScale />
        <p className="mt-3 text-body">{verdict(job, you)}</p>
      </div>

      <ul className="mt-5 grid gap-x-6 gap-y-2 border-t border-card-line pt-4 sm:grid-cols-2">
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
      <p className="mt-4 text-meta text-card-muted">
        Labelled <span className="font-medium text-card-text">{LEVEL[job.level]}</span>
        {job.level_reason ? <> because it {job.level_reason}</> : null}
      </p>
    </div>
  );
}
