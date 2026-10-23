// Real pieces of the Kario interface, drawn in HTML for the "How it works" steps (taste-skill: for
// software, the product itself is the picture). The job is a real posting from the 2026-10-23 run
// with its real evidence. The resume behind the fit, people and rewrite is a sample, and the file
// bar on those cards names it as one.
import { Check, Copy, FileText, Mail, MapPin, Minus } from "lucide-react";
import type { ReactNode } from "react";

export const JOB = {
  company: "Palantir",
  title: "Forward Deployed Software Engineer, New Grad",
  place: "New York · Onsite · Relocation offered",
  salary: "$135,000 - $145,000/year",
  evidence: ["Must be graduating in ", "December 2026 or Spring 2027", ""] as const,
  via: "Lever",
};

function Card({ file = false, children }: { file?: boolean; children: ReactNode }) {
  return (
    <div data-ui className="overflow-hidden rounded-xl border border-lp-line bg-lp-surface text-lp-ink">
      {file && (
        <div className="flex items-center gap-2 border-b border-lp-line bg-lp-bg px-4 py-2.5 font-mono text-[11px] text-lp-muted">
          <FileText aria-hidden className="size-3.5" strokeWidth={1.75} />
          <span>resume_2026.pdf · B.Tech CS &rsquo;26</span>
          <span className="ml-auto">sample</span>
        </div>
      )}
      <div className="p-5 sm:p-6">{children}</div>
    </div>
  );
}

export function JobFragment() {
  const [before, hit, after] = JOB.evidence;
  return (
    <Card>
      <div className="flex items-start gap-3">
        <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-md bg-lp-raised text-[15px] font-semibold">P</span>
        <div className="min-w-0">
          <p className="text-[17px] font-medium leading-snug">{JOB.title}</p>
          <p className="mt-1 flex items-center gap-1.5 text-[14px] text-lp-muted"><MapPin aria-hidden className="size-3.5" strokeWidth={1.75} />{JOB.company}, {JOB.place}</p>
          <p className="mt-1 text-[14px] text-lp-muted">{JOB.salary}</p>
        </div>
      </div>
      <div className="mt-5 rounded-lg bg-lp-raised p-4">
        <p className="text-[14px] font-semibold text-lp-accent-text">Fresher, 2026 batch</p>
        <p className="mt-1.5 text-[15px] leading-relaxed">&ldquo;{before}<mark>{hit}</mark>{after}&rdquo;</p>
        <p className="mt-2 text-[13px] text-lp-muted">The line in the posting that decided the label</p>
      </div>
    </Card>
  );
}

export function FitFragment() {
  const rows: [string, string, boolean][] = [
    ["Python", "“Strong coder … Python, Java, C++, TypeScript/JavaScript”", true],
    ["Graduating 2026", "“Must be graduating in December 2026 or Spring 2027”", true],
    ["AI projects", "“the latest advancements in AI”", true],
    ["Customer-facing work", "Not on your resume yet; one project line would help", false],
  ];
  return (
    <Card file>
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-[17px] font-medium">Your fit</p>
        <p className="font-mono text-[26px] font-medium tracking-tight text-lp-accent-text">3/4</p>
      </div>
      <ul className="mt-4 grid gap-3">
        {rows.map(([skill, why, ok]) => (
          <li key={skill} className="flex gap-3">
            <span aria-hidden className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${ok ? "bg-lp-add-bg text-lp-add" : "bg-lp-del-bg text-lp-del"}`}>
              {ok ? <Check className="size-3.5" strokeWidth={2.5} /> : <Minus className="size-3.5" strokeWidth={2.5} />}
            </span>
            <span className="min-w-0">
              <span className="block text-[15px] font-medium">{skill}<span className="sr-only">{ok ? ", matched" : ", missing"}</span></span>
              <span className="block text-[14px] text-lp-muted">{why}</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function PeopleFragment() {
  const people: [string, string, string, string | null][] = [
    ["AS", "Software Engineer, your college's 2023 batch", "From your LinkedIn connections", "Alumni · 2023 batch"],
    ["RK", "Forward Deployed Engineer, Warp Speed team", "From the company's team page", null],
  ];
  return (
    <Card file>
      <p className="text-[17px] font-medium">2 people to ask at {JOB.company}</p>
      <ul className="mt-4 grid gap-2">
        {people.map(([initials, who, from, badge]) => (
          <li key={who} className="flex items-center gap-3 rounded-lg bg-lp-bg p-3">
            <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-lp-raised font-mono text-[12px] font-medium">{initials}</span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[15px]">
                {who}
                {badge && <span className="rounded-full bg-lp-add-bg px-2 py-0.5 text-[12px] font-medium text-lp-add">{badge}</span>}
              </span>
              <span className="block text-[13px] text-lp-muted">{from}</span>
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 rounded-lg bg-lp-bg p-4">
        <p className="flex items-center gap-2 text-[14px] text-lp-muted"><Mail aria-hidden className="size-4" strokeWidth={1.75} />Draft in your Gmail</p>
        <p className="mt-2 text-[15px] leading-relaxed">Hi, I&rsquo;m a 2026 CS graduate and I&rsquo;ve applied for the Warp Speed FDSE role. I built a retrieval assistant for factory manuals and would love ten minutes on what the team looks for.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="btn-primary btn-tactile btn-sm">Approve and send</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-lp-line bg-lp-surface px-3.5 py-2 text-[14px]"><Copy aria-hidden className="size-3.5" strokeWidth={1.75} />Copy LinkedIn note</span>
        </div>
      </div>
    </Card>
  );
}

export function ApplyFragment() {
  return (
    <Card file>
      <p className="text-[17px] font-medium">Resume for this job</p>
      <div className="mt-4 overflow-hidden rounded-lg border border-lp-line font-mono text-[13px] leading-relaxed">
        <p className="flex gap-3 bg-lp-del-bg px-3 py-2.5">
          <span aria-hidden className="select-none text-lp-del">-</span>
          <span className="text-lp-muted line-through decoration-lp-del/60"><span className="sr-only">Removed: </span>Built a chatbot using Python and LangChain</span>
        </p>
        <p className="flex gap-3 border-l-2 border-lp-add bg-lp-add-bg px-3 py-2.5">
          <span aria-hidden className="select-none text-lp-add">+</span>
          <span><span className="sr-only">Added: </span>Built a <mark>retrieval assistant</mark> in <mark>Python and FastAPI</mark> that answers questions over <mark>2,000 factory manuals</mark>, used by <mark>40 people</mark> on a shop floor</span>
        </p>
      </div>
      <p className="mt-3 text-[14px] text-lp-muted">Reworded toward the posting. Nothing added that isn&rsquo;t on your resume.</p>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-lp-bg p-4">
        <span className="text-[15px]">Application ready on {JOB.via}: resume tailored, 6 answers filled</span>
        <span className="btn-primary btn-tactile btn-sm">Review and submit</span>
      </div>
    </Card>
  );
}
