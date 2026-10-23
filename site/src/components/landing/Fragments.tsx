// Real pieces of the Kario interface, drawn in HTML for the "How it works" steps (taste-skill: for
// software, the product itself is the picture). The job is a real posting from the 2026-10-23 run
// with its real evidence; the profile behind the fit, the people and the resume lines is an example,
// and each fragment says so.
import { Check, Copy, Mail, MapPin, Minus, Plus, UserRound } from "lucide-react";

export const JOB = {
  company: "Palantir",
  title: "Forward Deployed Software Engineer, New Grad",
  place: "New York · Onsite · Relocation offered",
  salary: "$135,000 - $145,000/year",
  evidence: "Must be graduating in December 2026 or Spring 2027",
  via: "Lever",
};

const panel = "rounded-lg bg-night-surface p-5 text-night-ink sm:p-6";
const example = <p className="mt-5 text-[13px] text-night-muted">Example profile</p>;

export function JobFragment() {
  return (
    <div data-ui className={panel}>
      <div className="flex items-start gap-3">
        <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-md bg-night-raised text-[15px] font-semibold">P</span>
        <div className="min-w-0">
          <p className="text-[17px] font-medium leading-snug">{JOB.title}</p>
          <p className="mt-1 flex items-center gap-1.5 text-[14px] text-night-muted"><MapPin aria-hidden className="size-3.5" strokeWidth={1.75} />{JOB.company}, {JOB.place}</p>
          <p className="mt-1 text-[14px] text-night-muted">{JOB.salary}</p>
        </div>
      </div>
      <div className="mt-5 rounded-md bg-night-raised p-4">
        <p className="text-[14px] font-semibold text-night-accent">Fresher, 2026 batch</p>
        <p className="mt-1.5 text-[15px] leading-relaxed">&ldquo;{JOB.evidence}&rdquo;</p>
        <p className="mt-2 text-[13px] text-night-muted">The line in the posting that decided the label</p>
      </div>
    </div>
  );
}

export function FitFragment() {
  const rows: [string, string, boolean][] = [
    ["Python", "“Strong coder … Python, Java, C++, TypeScript/JavaScript”", true],
    ["Graduating 2026", "“Must be graduating in December 2026 or Spring 2027”", true],
    ["AI projects", "“the latest advancements in AI”", true],
    ["Customer-facing work", "You haven't shown it yet; one project line would help", false],
  ];
  return (
    <div data-ui className={panel}>
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-[17px] font-medium">Your fit</p>
        <p className="text-[28px] font-semibold tracking-tight text-night-accent">3 of 4</p>
      </div>
      <ul className="mt-4 grid gap-3">
        {rows.map(([skill, why, ok]) => (
          <li key={skill} className="flex gap-3">
            <span aria-hidden className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${ok ? "bg-night-good text-night-bg" : "bg-night-miss text-night-bg"}`}>
              {ok ? <Check className="size-3.5" strokeWidth={2.5} /> : <Minus className="size-3.5" strokeWidth={2.5} />}
            </span>
            <span className="min-w-0">
              <span className="block text-[15px] font-medium">{skill}<span className="sr-only">{ok ? ", matched" : ", missing"}</span></span>
              <span className="block text-[14px] text-night-muted">{why}</span>
            </span>
          </li>
        ))}
      </ul>
      {example}
    </div>
  );
}

export function PeopleFragment() {
  return (
    <div data-ui className={panel}>
      <p className="text-[17px] font-medium">2 people to ask at {JOB.company}</p>
      <ul className="mt-4 grid gap-2">
        {[
          ["Software Engineer, your college's 2023 batch", "From your LinkedIn connections"],
          ["Forward Deployed Engineer, Warp Speed team", "From the company's team page"],
        ].map(([who, from]) => (
          <li key={who} className="flex items-center gap-3 rounded-md bg-night-raised p-3">
            <UserRound aria-hidden className="size-5 shrink-0 text-night-muted" strokeWidth={1.75} />
            <span className="min-w-0"><span className="block text-[15px]">{who}</span><span className="block text-[13px] text-night-muted">{from}</span></span>
          </li>
        ))}
      </ul>
      <div className="mt-4 rounded-md bg-night-raised p-4">
        <p className="flex items-center gap-2 text-[14px] text-night-muted"><Mail aria-hidden className="size-4" strokeWidth={1.75} />Draft in your Gmail</p>
        <p className="mt-2 text-[15px] leading-relaxed">Hi, I&rsquo;m a 2026 CS graduate and I&rsquo;ve applied for the Warp Speed FDSE role. I built a retrieval assistant for factory manuals and would love ten minutes on what the team looks for.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-night-accent px-3.5 py-1.5 text-[14px] font-semibold text-night-on-accent">Approve and send</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-night-bg px-3.5 py-1.5 text-[14px]"><Copy aria-hidden className="size-3.5" strokeWidth={1.75} />Copy LinkedIn note</span>
        </div>
      </div>
      {example}
    </div>
  );
}

export function ApplyFragment() {
  return (
    <div data-ui className={panel}>
      <p className="text-[17px] font-medium">Resume for this job</p>
      <div className="mt-4 grid gap-2 text-[15px] leading-relaxed">
        <p className="flex gap-2 rounded-md bg-night-raised p-3 text-night-muted"><Minus aria-hidden className="mt-1 size-4 shrink-0 text-night-miss" strokeWidth={2} /><span className="line-through decoration-night-miss/70">Built a chatbot using Python and LangChain</span></p>
        <p className="flex gap-2 rounded-md bg-night-raised p-3"><Plus aria-hidden className="mt-1 size-4 shrink-0 text-night-good" strokeWidth={2} /><span>Built a retrieval assistant in Python and FastAPI that answers questions over 2,000 factory manuals, used by 40 people on a shop floor</span></p>
      </div>
      <p className="mt-3 text-[14px] text-night-muted">Reworded toward the posting. Nothing added that isn&rsquo;t on your resume.</p>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-md bg-night-raised p-4">
        <span className="text-[15px]">Application ready on {JOB.via}: resume tailored, 6 answers filled</span>
        <span className="rounded-full bg-night-accent px-3.5 py-1.5 text-[14px] font-semibold text-night-on-accent">Review and submit</span>
      </div>
      {example}
    </div>
  );
}
