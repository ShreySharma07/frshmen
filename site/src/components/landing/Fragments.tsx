// Real pieces of the Kario interface for the "How it works" steps, each in an application window
// (stone frame, white window, 36px title bar). The job is a real posting from the 2026-10-23 run
// and every quote is verbatim from it; the resume, the people and the rewrite are a sample profile,
// which the section says above the steps.
import { Check, Copy, CornerDownLeft, ExternalLink, MapPin, Plus } from "lucide-react";
import type { ReactNode } from "react";

export const JOB = {
  company: "Palantir",
  title: "Forward Deployed Software Engineer, New Grad",
  url: "jobs.lever.co/palantir/66b4…add7",
  via: "Lever",
};

/** Stone frame, crisp white window, mono title bar: left is what the window shows, right its state. */
function Window({ left, right, children }: { left: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (
    <div data-ui className="min-w-0 rounded-2xl border border-lp-line bg-lp-surface p-2 shadow-sm">
      <div className="overflow-hidden rounded-xl border border-lp-window-line bg-lp-raised text-lp-ink">
        <div className="flex h-9 items-center justify-between gap-3 border-b border-lp-window-line bg-lp-window-bar px-4 font-mono text-[11px] text-lp-muted">
          <span className="flex min-w-0 items-center gap-2.5">
            <span aria-hidden className="flex gap-1"><i className="size-2 rounded-full bg-lp-line" /><i className="size-2 rounded-full bg-lp-line" /><i className="size-2 rounded-full bg-lp-line" /></span>
            <span className="truncate">{left}</span>
          </span>
          {right}
        </div>
        {children}
      </div>
    </div>
  );
}

const Pill = ({ children }: { children: ReactNode }) => (
  <span className="inline-flex items-center gap-1 rounded-full border border-lp-window-line bg-lp-window-bar px-2.5 py-1 text-[13px]">{children}</span>
);

export function JobFragment() {
  return (
    <Window left={JOB.url} right={<span className="shrink-0 rounded-full bg-lp-ok px-2 py-0.5 font-semibold text-lp-term uppercase">0 YOE verified</span>}>
      <div className="p-5">
        <div className="flex items-start gap-3">
          <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-md bg-lp-term text-[15px] font-semibold text-lp-term-ink">P</span>
          <div className="min-w-0">
            <p className="text-[17px] font-medium leading-snug">{JOB.title}</p>
            <p className="mt-0.5 text-[14px] text-lp-muted">{JOB.company} · Warp Speed</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Pill>$135,000 - $145,000/year</Pill>
          <Pill>Relocation assistance</Pill>
          <Pill><MapPin aria-hidden className="size-3" strokeWidth={2} />New York · Onsite</Pill>
        </div>
        {/* The line in the stored posting that decided the label, as Kario's inspector shows it. */}
        <div className="mt-5 overflow-hidden rounded-lg bg-lp-term font-mono text-[12.5px] leading-relaxed text-lp-term-muted">
          <div className="grid grid-cols-[2.25rem_1fr] gap-x-3 px-3 py-3">
            <span className="text-right opacity-60">11</span><span>Required</span>
            <span className="text-right text-lp-term-ink">12</span>
            <span className="text-lp-term-ink">- <mark className="term-mark">&ldquo;Must be graduating in December 2026 or Spring 2027&rdquo;</mark></span>
          </div>
          <div className="border-t border-lp-term-muted/20 px-3 py-2 text-[11.5px]">
            <span className="text-lp-term-ok">✓ batch 2026, 2027</span> → level fresher, 0 years required
          </div>
        </div>
      </div>
    </Window>
  );
}

export function FitFragment() {
  const rows: [string, string, boolean][] = [
    ["Python", "Python, Java, C++, TypeScript/JavaScript", true],
    ["Graduating 2026", "Must be graduating in December 2026 or Spring 2027", true],
    ["AI projects", "the latest advancements in AI", true],
    ["Customer-facing work", "Not on your resume yet", false],
  ];
  return (
    <Window
      left="shrey_resume_2026.pdf ↔ palantir_fdse"
      right={
        <span className="flex shrink-0 items-center gap-2">
          <span aria-hidden className="flex gap-0.5">{[0, 1, 2, 3].map((i) => <i key={i} className={`h-2 w-2.5 rounded-[2px] ${i < 3 ? "bg-lp-ok" : "bg-lp-window-line"}`} />)}</span>
          <span className="text-lp-ink">3/4 matched</span>
        </span>
      }
    >
      <ul className="divide-y divide-lp-window-line">
        {rows.map(([skill, quote, ok]) => (
          <li key={skill} className="grid grid-cols-[1.5rem_1fr] gap-x-3 gap-y-1.5 px-5 py-3.5">
            <span aria-hidden className={`mt-0.5 grid size-5 place-items-center rounded-full text-[12px] font-bold text-lp-term ${ok ? "bg-lp-ok" : "bg-lp-warn"}`}>
              {ok ? <Check className="size-3.5" strokeWidth={3} /> : "!"}
            </span>
            <span className="text-[15px] font-medium">{skill}<span className="sr-only">{ok ? ", matched" : ", missing"}</span></span>
            <span className="col-start-2">
              {ok ? (
                <span className="inline-block rounded-md bg-lp-window-bar px-2 py-0.5 font-mono text-[12px] text-lp-muted">&ldquo;{quote}&rdquo;</span>
              ) : (
                <span className="flex flex-wrap items-center gap-2 text-[13px] text-lp-warn-text">
                  {quote}
                  <span className="inline-flex items-center gap-1 rounded-full border border-lp-line bg-lp-window-bar px-2.5 py-1 text-[12.5px] font-medium text-lp-ink">
                    <Plus aria-hidden className="size-3" strokeWidth={2.5} />Add suggested project bullet
                  </span>
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </Window>
  );
}

export function PeopleFragment() {
  const people: [string, string, string][] = [
    ["RK", "Rohan K., Software Engineer", "IIT-M ’23 alumni · 1st degree"],
    ["AM", "A. Mehta, Forward Deployed Engineer", "Warp Speed team page"],
  ];
  return (
    <Window left={`2 warm paths found at ${JOB.company}`}>
      <ul className="divide-y divide-lp-window-line">
        {people.map(([initials, who, from]) => (
          <li key={who} className="flex items-center gap-3 px-5 py-3">
            <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-lp-term font-mono text-[12px] font-medium text-lp-term-ink">{initials}</span>
            <span className="min-w-0 flex-1 text-[15px]">{who}</span>
            <span className="shrink-0 rounded-full bg-lp-add-bg px-2 py-0.5 font-mono text-[11px] text-lp-add">{from}</span>
          </li>
        ))}
      </ul>
      {/* A Gmail draft as it lands in the student's own inbox, waiting for approval. */}
      <div className="border-t border-lp-window-line bg-lp-window-bar p-4">
        <div className="rounded-lg border border-lp-window-line bg-lp-raised">
          <div className="grid divide-y divide-lp-window-line text-[13.5px]">
            <p className="flex items-center gap-2 px-3 py-2"><span className="w-14 text-lp-muted">To</span><span className="rounded-full bg-lp-window-bar px-2 py-0.5">Rohan K.</span></p>
            <p className="flex items-center gap-2 px-3 py-2"><span className="w-14 text-lp-muted">Subject</span>2026 CS Grad — Warp Speed FDSE</p>
          </div>
          <p className="border-t border-lp-window-line px-3 py-3 text-[14px] leading-relaxed">
            Hi Rohan, I&rsquo;m a 2026 CS graduate from IIT-M and I&rsquo;ve applied for the Warp Speed FDSE role. I built a retrieval assistant for factory manuals and would love ten minutes on what the team looks for.
          </p>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="btn-term">Approve &amp; send via Gmail <CornerDownLeft aria-hidden className="size-3.5" strokeWidth={2} /></span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-lp-window-line bg-lp-raised px-3.5 py-2 text-[14px]"><Copy aria-hidden className="size-3.5" strokeWidth={1.75} />Copy LinkedIn note</span>
        </div>
      </div>
    </Window>
  );
}

export function ApplyFragment() {
  return (
    <Window left="resume_tailor.diff" right={<span className="shrink-0 rounded-full bg-lp-add-bg px-2 py-0.5 text-lp-add">Zero hallucination mode</span>}>
      <div className="font-mono text-[12px] leading-relaxed">
        <p className="grid grid-cols-[1.75rem_1rem_1fr] bg-lp-del-bg px-3 py-2 text-lp-del">
          <span className="text-right opacity-60">14</span><span aria-hidden className="text-center">-</span>
          <span className="line-through decoration-lp-del/50"><span className="sr-only">Removed: </span>Built a chatbot using Python and LangChain</span>
        </p>
        <p className="grid grid-cols-[1.75rem_1rem_1fr] border-l-2 border-lp-add bg-lp-add-bg py-2.5 pr-3 pl-[calc(0.75rem-2px)] text-lp-ink">
          <span className="text-right text-lp-add opacity-70">14</span><span aria-hidden className="text-center text-lp-add">+</span>
          <span><span className="sr-only">Added: </span>Built a <mark className="diff-mark">retrieval assistant</mark> in <mark className="diff-mark">Python and FastAPI</mark> that answers questions over <mark className="diff-mark">2,000 factory manuals</mark>, used by <mark className="diff-mark">40 people</mark> on a shop floor</span>
        </p>
      </div>
      <p className="px-5 py-3 text-[13.5px] text-lp-muted">Reworded toward the posting. Every fact is already on your resume.</p>
      <div className="flex flex-wrap items-center justify-between gap-3 bg-lp-term px-4 py-3 font-mono text-[12px] text-lp-term-ink">
        <span><span className="text-lp-term-ok">✓</span> {JOB.via} form auto-filled (6/6 fields)</span>
        <span className="btn-primary btn-tactile btn-sm gap-1.5 font-sans">Review &amp; submit <ExternalLink aria-hidden className="size-3.5" strokeWidth={2} /></span>
      </div>
    </Window>
  );
}
