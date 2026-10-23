"use client";

// The first three screens as one scroll scene: the tagline with the globe on the right; the globe
// rolls left and turns to India while the places light up; then the globe gives way to the sources
// band. Without script, or with reduced motion, the three panels simply stack (mode "flow"), so
// nothing is ever hidden behind an animation that didn't run.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import Link from "next/link";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { Globe, type GlobeView } from "./Globe";
import { fmt, type Counts } from "./places";

gsap.registerPlugin(ScrollTrigger, SplitText);

// What we read, as the band shows it: the hiring systems first, then companies with open jobs now.
// Indian cities sit close together on the globe, so only places far apart get a label.
const LABELLED = new Set(["blr", "us", "uk", "jp", "sg"]);
const SYSTEMS = ["Greenhouse", "Lever", "Ashby", "Workday", "Workable", "SmartRecruiters", "Oracle Recruiting", "Eightfold", "Company career sites", "Hacker News"];
const COMPANIES = ["Anthropic", "OpenAI", "Databricks", "NVIDIA", "Razorpay", "Sarvam AI", "Meesho", "Paytm", "Groww", "CRED", "PhonePe", "Zomato", "Stripe", "Cloudflare", "Scale AI", "Perplexity", "Glean", "Atlan", "Postman", "BrowserStack", "Freshworks", "Notion"];

export function GlobeStory({ counts }: { counts: Counts }) {
  const root = useRef<HTMLElement>(null);
  const view = useRef<GlobeView>({ focus: 0 });
  const mode = useSyncExternalStore(onMotionChange, () => (reducedMotion().matches ? "flow" : "scroll"), () => "flow");

  useEffect(() => {
    if (mode !== "scroll" || !root.current) return;
    const ctx = gsap.context(() => {
      const q = gsap.utils.selector(root);
      // The tagline rises line by line from behind a mask, once, on load: the page's signature move.
      const split = SplitText.create(q("[data-tagline]"), { type: "lines", mask: "lines", autoSplit: true });
      gsap.from(split.lines, { yPercent: 110, duration: 0.9, ease: "expo.out", stagger: 0.08, delay: 0.15 });
      gsap.from(q("[data-hero-after]"), { y: 20, opacity: 0, duration: 0.7, ease: "expo.out", stagger: 0.08, delay: 0.45 });

      const mm = gsap.matchMedia();
      mm.add({ wide: "(min-width: 64rem)", narrow: "(max-width: 63.99rem)" }, (c) => {
        const wide = c.conditions?.wide;
        const tl = gsap.timeline({
          defaults: { ease: "power2.inOut" },
          scrollTrigger: { trigger: root.current, start: "top top", end: "bottom bottom", scrub: 0.6 },
        });
        tl.set(q("[data-panel=places], [data-panel=sources]"), { autoAlpha: 0 }, 0)
          .to({}, { duration: 0.1 })
          .to(q("[data-panel=hero]"), { autoAlpha: 0, y: -48, duration: 0.16 }, 0.1)
          .to(q("[data-globe]"), wide ? { x: () => -window.innerWidth * 0.46, duration: 0.34 } : { y: () => -window.innerHeight * 0.4, scale: 0.6, duration: 0.34 }, 0.1)
          .to(view.current, { focus: 1, duration: 0.34 }, 0.1)
          .fromTo(q("[data-panel=places]"), { autoAlpha: 0, y: 48 }, { autoAlpha: 1, y: 0, duration: 0.16 }, 0.3)
          .to({}, { duration: 0.14 })
          .to(q("[data-globe], [data-panel=places]"), { autoAlpha: 0, scale: 0.9, duration: 0.14 }, 0.62)
          .fromTo(q("[data-panel=sources]"), { autoAlpha: 0, y: 48 }, { autoAlpha: 1, y: 0, duration: 0.16 }, 0.7)
          .to({}, { duration: 0.14 });
        return () => { view.current.focus = 0; };
      });
    }, root);
    return () => ctx.revert();
  }, [mode]);

  const india = counts.cities.slice(0, 4);
  const abroad = counts.abroad.slice(0, 4);
  const labelled = [...counts.cities, ...counts.abroad].filter((p) => LABELLED.has(p.id));

  return (
    <section ref={root} data-mode={mode} aria-label="Kario" className="story relative">
      <div className="story-frame relative">
        <div data-globe className="globe-box pointer-events-none absolute">
          <div className="pointer-events-auto relative">
            <Globe places={[...counts.cities, ...counts.abroad]} view={view} />
            {labelled.map((p) => (
              <span key={p.id} className="globe-label" style={{ ["--a" as string]: `--cobe-${p.id}`, ["--v" as string]: `var(--cobe-visible-${p.id}, 0)` }}>
                {p.name} <b>{fmt(p.n)}</b>
              </span>
            ))}
          </div>
        </div>

        <div data-panel="hero" className="panel">
          <div className="col-span-full grid gap-7 lg:col-span-6">
            <h1 data-tagline className="font-display text-[clamp(2.75rem,6.4vw,5.75rem)] leading-[0.95] font-semibold tracking-[-0.045em] text-balance">
              Not another job board. An agent that gets you your next job.
            </h1>
            <p data-hero-after className="max-w-[34rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed text-night-ink">
              Kario finds the jobs that really take freshers, checks your fit, finds people to ask for a referral and prepares each application with you.
            </p>
            <div data-hero-after className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <Link href="/?yrs=0" className="btn-primary">Find fresher jobs</Link>
              <span className="text-[15px] text-night-muted">{fmt(counts.fresher)} open right now</span>
            </div>
          </div>
        </div>

        <div data-panel="places" className="panel">
          <div className="col-span-full grid gap-7 lg:col-span-5 lg:col-start-8">
            <h2 className="font-display text-[clamp(2.5rem,5vw,4.5rem)] leading-[0.95] font-semibold tracking-[-0.045em] text-balance">Find jobs all around the globe.</h2>
            <p className="max-w-[30rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed">
              {fmt(counts.total)} open jobs from {counts.companies} companies, {fmt(counts.india)} of them in India. Roles abroad show whether they sponsor a visa or help you relocate.
            </p>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-[16px] tabular-nums sm:max-w-[30rem]">
              {[...india, ...abroad.slice(0, 2)].map((p) => (
                <div key={p.id} className="flex items-baseline justify-between gap-3 rounded-md bg-night-surface px-3 py-2">
                  <dt className="text-night-muted">{p.name}</dt>
                  <dd className="font-medium">{fmt(p.n)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        <div data-panel="sources" className="panel">
          <div className="col-span-full grid gap-10 lg:col-span-7">
            <h2 className="font-display max-w-[16ch] text-[clamp(2.5rem,5.6vw,5rem)] leading-[0.95] font-semibold tracking-[-0.045em] text-balance">
              Every opening, straight from the companies hiring.
            </h2>
            <p className="max-w-[36rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed">
              Kario reads each company&rsquo;s own hiring page every three hours, so you see new roles the day they open. We never scrape LinkedIn, Indeed or Glassdoor.
            </p>
          </div>
          <dl className="col-span-full mt-10 grid grid-cols-2 gap-8 self-center lg:col-span-4 lg:col-start-9 lg:mt-0 lg:grid-cols-1">
            {[
              [fmt(counts.total), "open jobs right now"],
              [String(counts.companies), "companies read on every run"],
              [fmt(counts.fresher), "that really take freshers"],
            ].map(([n, label]) => (
              <div key={label} className="grid gap-1">
                <dt className="order-2 text-[16px] text-night-muted">{label}</dt>
                <dd className="font-display text-[clamp(2.5rem,5vw,4.5rem)] leading-none font-semibold tracking-[-0.04em] tabular-nums">{n}</dd>
              </div>
            ))}
          </dl>
          <div className="col-span-full -mx-[var(--gutter)] grid gap-4 self-end pb-[8svh]">
            <Band items={SYSTEMS} />
            <Band items={COMPANIES} reverse />
          </div>
        </div>
      </div>
    </section>
  );
}

// The printed page (no script yet) is "flow"; the browser switches to the scroll scene unless the
// reader asked for less motion, and back if they change that setting.
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)");
function onMotionChange(cb: () => void) {
  const m = reducedMotion();
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}

function Band({ items, reverse = false }: { items: string[]; reverse?: boolean }) {
  const row = (hidden: boolean) => (
    <ul aria-hidden={hidden || undefined} className="band-row flex shrink-0 gap-12 pr-12">
      {items.map((s) => <li key={s} className="font-display text-[clamp(1.5rem,2.6vw,2.25rem)] font-semibold tracking-[-0.03em] whitespace-nowrap">{s}</li>)}
    </ul>
  );
  return (
    <div className={`band flex overflow-hidden ${reverse ? "band-reverse text-night-muted" : ""}`}>
      {row(false)}
      {row(true)}
    </div>
  );
}
