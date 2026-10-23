"use client";

// Four steps, on a white chapter. A sticky row of four pills shows where you are and jumps to any
// step; on wide screens the matching piece of Kario stays in view on the right and changes as each
// step reaches the middle of the screen (or its pill is pressed). On phones each piece sits under
// its step. All four follow one job, so the steps read as one application, start to end.
import { useEffect, useRef, useState } from "react";
import { ApplyFragment, FitFragment, JobFragment, PeopleFragment } from "./Fragments";
import { scrollToMiddle } from "./scroll";

const STEPS = [
  {
    pill: "Verify YOE",
    title: "You find a job you like.",
    body: "Every posting is labelled by the years it really asks for, with the line that decided it. No more opening twenty listings to find the two that take freshers.",
    Fragment: JobFragment,
  },
  {
    pill: "Check Fit",
    title: "The agent checks your fit.",
    body: "Your resume against the posting: what matches, what's missing, and the one line that would make your case stronger.",
    Fragment: FitFragment,
  },
  {
    pill: "Warm Referral",
    title: "It finds people to ask for a referral.",
    body: "Your own connections at the company first, from your LinkedIn export, then engineers on the team's public pages. Once someone accepts, you write the message; Kario sends email from your Gmail after you approve it, and hands you the LinkedIn note to send yourself.",
    Fragment: PeopleFragment,
  },
  {
    pill: "Tailor & Apply",
    title: "It prepares the application, referral or not.",
    body: "A resume reworded for this posting, never padded, and the form's answers filled in. You read it and press submit.",
    Fragment: ApplyFragment,
  },
];

export function HowItWorks() {
  const [active, setActive] = useState(0);
  const steps = useRef<(HTMLLIElement | null)[]>([]);
  const pills = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const seen = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(Number((e.target as HTMLElement).dataset.step))),
      { rootMargin: "-45% 0px -45% 0px" },
    );
    steps.current.forEach((el) => el && seen.observe(el));
    return () => seen.disconnect();
  }, []);

  // On phones the pill row scrolls sideways; keep the current step's pill in view.
  useEffect(() => {
    const row = pills.current;
    const pill = row?.children[active] as HTMLElement | undefined;
    if (row && pill && row.scrollWidth > row.clientWidth) row.scrollTo({ left: pill.offsetLeft - 16, behavior: "smooth" });
  }, [active]);

  const go = (i: number) => {
    setActive(i);
    const el = steps.current[i];
    if (el) scrollToMiddle(el);
  };

  return (
    <section id="how" aria-labelledby="how-title" className="lp-light bg-lp-bg pt-[clamp(6rem,12vw,10rem)] pb-[clamp(4rem,8vw,6rem)] text-lp-ink">
      <div className="grid-page">
        <h2 id="how-title" className="col-span-full text-[clamp(2.5rem,5.6vw,5rem)] leading-[0.95] font-semibold tracking-[-0.05em]">How it works</h2>
      </div>

      <nav aria-label="Steps" className="sticky top-[calc(max(0.75rem,env(safe-area-inset-top,0px))+4rem)] z-20 mt-8 px-[var(--gutter)] lg:mt-12">
        <ol ref={pills} className="flex items-center gap-0 overflow-x-auto rounded-full bg-lp-bg/85 py-2 backdrop-blur-md [scrollbar-width:none]">
          {STEPS.map(({ pill }, i) => (
            <li key={pill} className="flex shrink-0 items-center lg:flex-1 lg:last:flex-none">
              <button
                type="button"
                onClick={() => go(i)}
                aria-current={active === i ? "step" : undefined}
                className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-[14px] whitespace-nowrap transition-colors duration-move ${
                  active === i ? "border-lp-ink bg-lp-ink text-lp-bg" : i < active ? "border-lp-line bg-lp-surface text-lp-ink" : "border-lp-line bg-lp-bg text-lp-muted hover:text-lp-ink"
                }`}
              >
                <span className="font-mono text-[12px]">{String(i + 1).padStart(2, "0")}</span>
                {pill}
              </button>
              {i < STEPS.length - 1 && (
                <span aria-hidden className={`mx-2 h-px w-6 transition-colors duration-move lg:mx-3 lg:w-auto lg:flex-1 ${i < active ? "bg-lp-ink" : "bg-lp-line"}`} />
              )}
            </li>
          ))}
        </ol>
      </nav>

      <div className="grid-page">
        <ol className="col-span-full lg:col-span-5">
          {STEPS.map(({ title, body, Fragment }, i) => (
            <li
              key={title}
              ref={(el) => { steps.current[i] = el; }}
              data-step={i}
              className={`grid scroll-mt-40 gap-4 py-10 transition-opacity duration-move lg:min-h-[76svh] lg:content-center lg:py-0 ${active === i ? "" : "lg:opacity-40"}`}
            >
              <h3 className="text-[clamp(1.75rem,3vw,2.75rem)] leading-[1.02] font-semibold tracking-[-0.04em] text-balance">{title}</h3>
              <p className="max-w-[32rem] text-[17px] leading-relaxed">{body}</p>
              <div className="mt-4 lg:hidden"><Fragment /></div>
            </li>
          ))}
        </ol>
        <div className="relative hidden lg:col-span-6 lg:col-start-7 lg:block">
          <div className="sticky top-32 grid h-[calc(100svh-8rem)] items-center">
            {STEPS.map(({ title, Fragment }, i) => (
              <div
                key={title}
                aria-hidden={active !== i}
                className={`col-start-1 row-start-1 transition-[opacity,translate,scale] duration-layout ease-out-expo ${active === i ? "translate-y-0 scale-100 opacity-100" : "pointer-events-none translate-y-6 scale-[0.98] opacity-0"}`}
              >
                <Fragment />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
