"use client";

// The middle and the end of the story (critique 2026-10-23: pain, proof, agent, trust, action).
// Proof: what the open jobs really ask for, from the live counts. Trust: the three promises the
// product keeps. Action: one last way in, with the live count.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight, MailCheck, ShieldCheck, ScrollText } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { fmt, type Counts } from "./places";

gsap.registerPlugin(ScrollTrigger);

export function Proof({ counts }: { counts: Counts }) {
  const root = useRef<HTMLElement>(null);
  const total = counts.fresher + counts.unclear + counts.experienced || 1;
  const parts = [
    { n: counts.fresher, label: "open to freshers", tone: "bg-lp-accent" },
    { n: counts.unclear, label: "never say how many years", tone: "bg-lp-line" },
    { n: counts.experienced, label: "ask for experience, and say how much", tone: "bg-lp-ink" },
  ];

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || !root.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo("[data-seg]", { scaleX: 0 }, { scaleX: 1, transformOrigin: "left center", ease: "power2.out", stagger: 0.12, scrollTrigger: { trigger: root.current, start: "top 70%", end: "center 55%", scrub: 0.6 } });
    }, root);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={root} aria-labelledby="proof-title" className="lp-light bg-lp-bg py-[clamp(6rem,12vw,10rem)] text-lp-ink">
      <div className="grid-page gap-y-10">
        <h2 id="proof-title" className="col-span-full max-w-[18ch] font-display text-[clamp(3rem,6.4vw,6rem)] leading-[0.92] tracking-[-0.02em] text-balance">
          The title says junior. The requirements say otherwise.
        </h2>
        <p className="col-span-full max-w-[38rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed lg:col-span-6">
          Kario has read {fmt(counts.total)} open jobs, every line of each. Here is what they really ask for, so you never open twenty tabs to find the two that take you.
        </p>
        <figure className="col-span-full grid gap-5">
          <div className="flex h-14 w-full overflow-hidden rounded-md" role="img" aria-label={parts.map((p) => `${fmt(p.n)} ${p.label}`).join(", ")}>
            {parts.map((p) => (
              <span key={p.label} data-seg className={`${p.tone} h-full`} style={{ width: `${(p.n / total) * 100}%` }} />
            ))}
          </div>
          <figcaption className="grid gap-4 sm:grid-cols-3">
            {parts.map((p) => (
              <span key={p.label} className="grid gap-1">
                <span className="flex items-center gap-2 font-mono text-[clamp(1.75rem,3vw,2.5rem)] leading-none tracking-[-0.03em] tabular-nums">
                  <i aria-hidden className={`size-3 rounded-[3px] ${p.tone}`} />{fmt(p.n)}
                </span>
                <span className="text-[16px] text-lp-muted">{p.label}</span>
              </span>
            ))}
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

const PROMISES = [
  { Icon: MailCheck, title: "Nothing goes out without you.", body: "Every email waits in your Gmail drafts until you approve it, and LinkedIn notes are yours to send. Kario never applies, messages or signs anything in your name on its own." },
  { Icon: ScrollText, title: "Your resume, never padded.", body: "Kario rewords what is already on your resume toward each posting. It does not add a skill, a number or a project you didn't give it." },
  { Icon: ShieldCheck, title: "Read at the source.", body: "Jobs come from each company's own hiring page. No LinkedIn, Indeed or Glassdoor scraping, and every label shows the line it came from." },
];

export function Trust() {
  return (
    <section aria-labelledby="trust-title" className="lp-light bg-lp-surface py-[clamp(6rem,12vw,10rem)] text-lp-ink">
      <div className="grid-page gap-y-12">
        <h2 id="trust-title" className="col-span-full font-display text-[clamp(3rem,6.4vw,6rem)] leading-[0.92] tracking-[-0.02em] text-balance lg:col-span-5">
          An agent you stay in charge of.
        </h2>
        <ul className="col-span-full grid gap-10 lg:col-span-6 lg:col-start-7">
          {PROMISES.map(({ Icon, title, body }) => (
            <li key={title} className="grid grid-cols-[2.5rem_1fr] gap-x-4 gap-y-2">
              <span aria-hidden className="grid size-10 place-items-center rounded-full bg-lp-accent text-lp-on-accent"><Icon className="size-5" strokeWidth={1.75} /></span>
              <h3 className="self-center font-display text-[clamp(1.75rem,2.6vw,2.5rem)] leading-[1.05]">{title}</h3>
              <p className="col-start-2 max-w-[34rem] text-[17px] leading-relaxed">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function FinalCall({ counts }: { counts: Counts }) {
  return (
    <section aria-labelledby="final-title" className="lp-light bg-lp-bg py-[clamp(6rem,14vw,12rem)] text-lp-ink">
      <div className="grid-page gap-y-8">
        <h2 id="final-title" className="col-span-full max-w-[14ch] font-display text-[clamp(3.5rem,9vw,9rem)] leading-[0.88] tracking-[-0.025em] italic">
          Your next job is in here.
        </h2>
        <div className="col-span-full flex flex-wrap items-center gap-x-8 gap-y-4">
          <Link href="/" className="btn-primary btn-tactile gap-2">
            Browse {fmt(counts.total)} open jobs <ArrowRight aria-hidden className="size-4" strokeWidth={2} />
          </Link>
          <span className="text-[16px] text-lp-muted">From {counts.companies} companies, read every three hours.</span>
        </div>
      </div>
    </section>
  );
}
