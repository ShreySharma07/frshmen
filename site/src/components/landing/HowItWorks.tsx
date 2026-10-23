"use client";

// Four steps on the left; on wide screens the matching piece of Kario stays in view on the right
// and changes as each step reaches the middle of the screen. On phones each piece sits under its
// step. All four fragments follow one job, so the steps read as one application, start to end.
import { useEffect, useRef, useState } from "react";
import { ApplyFragment, FitFragment, JobFragment, PeopleFragment } from "./Fragments";

const STEPS = [
  {
    title: "You find a job you like.",
    body: "Every posting is labelled by the years it really asks for, with the line that decided it. No more opening twenty listings to find the two that take freshers.",
    Fragment: JobFragment,
  },
  {
    title: "The agent checks your fit.",
    body: "Your resume against the posting: what matches, what's missing, and the one line that would make your case stronger.",
    Fragment: FitFragment,
  },
  {
    title: "It finds people to ask for a referral.",
    body: "Your own connections at the company first, from your LinkedIn export, then engineers on the team's public pages. Once someone accepts, you write the message; Kario sends email from your Gmail after you approve it, and hands you the LinkedIn note to send yourself.",
    Fragment: PeopleFragment,
  },
  {
    title: "It prepares the application, referral or not.",
    body: "A resume reworded for this posting, never padded, and the form's answers filled in. You read it and press submit.",
    Fragment: ApplyFragment,
  },
];

export function HowItWorks() {
  const [active, setActive] = useState(0);
  const steps = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const seen = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(Number((e.target as HTMLElement).dataset.step))),
      { rootMargin: "-45% 0px -45% 0px" },
    );
    steps.current.forEach((el) => el && seen.observe(el));
    return () => seen.disconnect();
  }, []);

  return (
    <section id="how" aria-labelledby="how-title" className="grid-page scroll-mt-20 pt-[clamp(6rem,14vw,12rem)]">
      <h2 id="how-title" className="col-span-full font-display text-[clamp(2.5rem,5.6vw,5rem)] leading-[0.95] font-semibold tracking-[-0.045em]">How it works</h2>
      <ol className="col-span-full mt-10 lg:col-span-5 lg:mt-0">
        {STEPS.map(({ title, body, Fragment }, i) => (
          <li
            key={title}
            ref={(el) => { steps.current[i] = el; }}
            data-step={i}
            className={`grid gap-4 py-10 transition-opacity duration-move lg:min-h-[78svh] lg:content-center lg:py-0 ${active === i ? "" : "lg:opacity-40"}`}
          >
            <h3 className="font-display text-[clamp(1.75rem,3vw,2.75rem)] leading-[1.02] font-semibold tracking-[-0.035em] text-balance">{title}</h3>
            <p className="max-w-[32rem] text-[17px] leading-relaxed">{body}</p>
            <div className="mt-4 lg:hidden"><Fragment /></div>
          </li>
        ))}
      </ol>
      <div className="relative hidden lg:col-span-6 lg:col-start-7 lg:block">
        <div className="sticky top-0 grid h-svh items-center">
          {STEPS.map(({ title, Fragment }, i) => (
            <div
              key={title}
              aria-hidden={active !== i}
              className={`col-start-1 row-start-1 transition-[opacity,translate] duration-layout ease-out-expo ${active === i ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-6 opacity-0"}`}
            >
              <Fragment />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
