"use client";

// Four steps on a parchment chapter, as a pinned horizontal track (critique 2026-10-23): scrolling
// down moves the steps sideways, and each card acts out its step as it arrives: the scan finds the
// deciding line, the fit ticks in, the email types itself and sends, the resume line is rewritten
// and the form fills. The step pills show where you are and jump to any step. With reduced motion
// the steps stack vertically with every card in its finished state.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApplyFragment, FitFragment, JobFragment, PeopleFragment } from "./Fragments";
import { scrollToY } from "./scroll";

gsap.registerPlugin(ScrollTrigger, SplitText);

const STEPS = [
  {
    pill: "Verify YOE",
    title: "You find a job you like.",
    body: "Every posting is labelled by the years it really asks for, with the line that decided it. No more opening twenty listings to find the two that take you.",
    Fragment: JobFragment,
    act: actJob,
  },
  {
    pill: "Check Fit",
    title: "The agent checks your fit.",
    body: "Your resume against the posting: what matches, what's missing, and the one line that would make your case stronger.",
    Fragment: FitFragment,
    act: actFit,
  },
  {
    pill: "Warm Referral",
    title: "It finds people to ask for a referral.",
    body: "Your own connections at the company first, from your LinkedIn export, then engineers on the team's public pages. Once someone accepts, you write the message; Kario sends email from your Gmail after you approve it, and hands you the LinkedIn note to send yourself.",
    Fragment: PeopleFragment,
    act: actPeople,
  },
  {
    pill: "Tailor & Apply",
    title: "It prepares the application, referral or not.",
    body: "A resume reworded for this posting, never padded, and the form's answers filled in. You read it and press submit.",
    Fragment: ApplyFragment,
    act: actApply,
  },
];

export function HowItWorks() {
  const root = useRef<HTMLElement>(null);
  const pin = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  // The sideways track needs a wide screen (a phone's cards are taller than the screen);
  // narrow screens and reduced motion get the stacked steps.
  const mode = useSyncExternalStore(onMotionChange, () => (reducedMotion().matches || !wide().matches ? "flow" : "scroll"), () => "flow");
  const animate = useSyncExternalStore(onMotionChange, () => !reducedMotion().matches, () => false);

  // Stacked steps still play their acts as each card scrolls into view, unless motion is reduced.
  useEffect(() => {
    if (mode !== "flow" || !animate || !root.current) return;
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>("[data-panel-step]").forEach((panel, i) => {
        const tl = gsap.timeline({ scrollTrigger: { trigger: panel, start: "top 75%", end: "center 45%", scrub: 0.5 } });
        STEPS[i].act(tl, gsap.utils.selector(panel));
      });
      const panels = gsap.utils.toArray<HTMLElement>("[data-panel-step]");
      panels.forEach((panel, i) => ScrollTrigger.create({ trigger: panel, start: "top 50%", end: "bottom 50%", onToggle: (st) => st.isActive && setActive(i) }));
    }, root);
    return () => ctx.revert();
  }, [mode, animate]);

  useEffect(() => {
    if (mode !== "scroll" || !pin.current || !track.current) return;
    const ctx = gsap.context(() => {
      const panels = gsap.utils.toArray<HTMLElement>("[data-panel-step]");
      const slide = gsap.to(track.current, {
        x: () => -(track.current!.scrollWidth - window.innerWidth),
        ease: "none",
        scrollTrigger: {
          trigger: pin.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 0.6,
          invalidateOnRefresh: true,
          onUpdate: (self) => setActive(Math.min(STEPS.length - 1, Math.round(self.progress * (STEPS.length - 1)))),
        },
      });
      // Each card plays its step while its panel slides into place.
      panels.forEach((panel, i) => {
        const tl = gsap.timeline({
          scrollTrigger: { trigger: panel, containerAnimation: slide, start: i === 0 ? "left left" : "left 85%", end: i === 0 ? "left -30%" : "left 15%", scrub: 0.5 },
        });
        STEPS[i].act(tl, gsap.utils.selector(panel));
      });
    }, root);
    return () => ctx.revert();
  }, [mode]);

  const go = (i: number) => {
    setActive(i);
    const el = pin.current;
    if (mode !== "scroll" || !el) {
      document.querySelector(`[data-panel-step="${i}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const top = el.getBoundingClientRect().top + window.scrollY;
    scrollToY(top + (i / (STEPS.length - 1)) * (el.offsetHeight - window.innerHeight) + 2);
  };

  return (
    <section ref={root} id="how" data-mode={mode} aria-labelledby="how-title" className="how scroll-mt-20 lp-light bg-lp-bg text-lp-ink">
      <div className="grid-page pt-[clamp(6rem,12vw,10rem)]">
        <h2 id="how-title" className="col-span-full font-display text-[clamp(3rem,6.6vw,6rem)] leading-[0.92] tracking-[-0.02em]">How it works</h2>
        <p className="col-span-full mt-4 max-w-[38rem] text-[16px] text-lp-muted">One real Palantir posting, start to finish. The job and every quote from it are real; the resume and the people are a sample profile.</p>
      </div>

      <div ref={pin} className="how-pin">
        <div className="how-stage">
          <nav aria-label="Steps" className="how-pills px-[var(--gutter)] pt-3 pb-2">
            <ol className="flex items-center overflow-x-auto py-1 [scrollbar-width:none]">
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

          <div ref={track} className="how-track">
            {STEPS.map(({ title, body, Fragment }, i) => (
              <article key={title} data-panel-step={i} aria-label={`Step ${i + 1}: ${title}`} className="how-panel grid-page">
                <div className="col-span-full grid content-center gap-4 lg:col-span-5">
                  <h3 className="font-display text-[clamp(2.25rem,3.6vw,3.5rem)] leading-[1] tracking-[-0.015em] text-balance">{title}</h3>
                  <p className="max-w-[32rem] text-[17px] leading-relaxed">{body}</p>
                </div>
                <div className="col-span-full min-w-0 content-center lg:col-span-6 lg:col-start-7 lg:grid">
                  <Fragment />
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

type Q = (selector: string) => Element[];

// Step 1: the scan runs down the inspector, stops on the deciding line, the line lights and the
// verdict stamps in.
function actJob(tl: gsap.core.Timeline, q: Q) {
  tl.fromTo(q("[data-scan]"), { autoAlpha: 0, y: 0 }, { autoAlpha: 1, duration: 0.05 })
    .to(q("[data-scan]"), { y: 22, duration: 0.25, ease: "power1.inOut" })
    .fromTo(q("[data-mark]"), { backgroundSize: "0% 100%" }, { backgroundSize: "100% 100%", duration: 0.25, ease: "power2.out" })
    .to(q("[data-scan]"), { autoAlpha: 0, duration: 0.1 })
    .fromTo(q("[data-verdict]"), { autoAlpha: 0, y: 8 }, { autoAlpha: 1, y: 0, duration: 0.15 }, "<")
    .fromTo(q("[data-stamp]"), { autoAlpha: 0, scale: 1.6, rotate: -8 }, { autoAlpha: 1, scale: 1, rotate: 0, duration: 0.2, ease: "back.out(2)" });
}

// Step 2: the rows come in one by one, the meter fills with each match.
function actFit(tl: gsap.core.Timeline, q: Q) {
  tl.fromTo(q("[data-row]"), { autoAlpha: 0, x: 24 }, { autoAlpha: 1, x: 0, stagger: 0.18, duration: 0.2, ease: "power2.out" })
    .fromTo(q("[data-seg]"), { scaleX: 0, transformOrigin: "left center" }, { scaleX: 1, stagger: 0.18, duration: 0.15 }, 0.1);
}

// Step 3: the people found, then the email types itself and the button flips to sent.
function actPeople(tl: gsap.core.Timeline, q: Q) {
  const words = SplitText.create(q("[data-type]"), { type: "words" }).words;
  tl.fromTo(q("[data-row]"), { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, stagger: 0.12, duration: 0.15 })
    .fromTo(words, { autoAlpha: 0 }, { autoAlpha: 1, stagger: 0.012, duration: 0.01, ease: "none" })
    .to(q("[data-send]"), { autoAlpha: 0, y: -6, duration: 0.08 })
    .fromTo(q("[data-sent]"), { autoAlpha: 0, y: 6 }, { autoAlpha: 1, y: 0, duration: 0.08 }, "<");
}

// Step 4: the old line is struck out, the new one is written in, and the form fills.
function actApply(tl: gsap.core.Timeline, q: Q) {
  const count = q("[data-count]")[0];
  const n = { v: 0 };
  tl.fromTo(q("[data-del]"), { opacity: 1 }, { opacity: 0.55, duration: 0.15 })
    .fromTo(q("[data-add]"), { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.35, ease: "power1.inOut" })
    .fromTo(q(".diff-mark"), { opacity: 0.25, scale: 0.92 }, { opacity: 1, scale: 1, stagger: 0.05, duration: 0.1 })
    .to(n, { v: 6, duration: 0.3, ease: "none", onUpdate: () => { if (count) count.textContent = String(Math.round(n.v)); } });
}

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)");
const wide = () => matchMedia("(min-width: 64rem)");
function onMotionChange(cb: () => void) {
  const queries = [reducedMotion(), wide()];
  queries.forEach((m) => m.addEventListener("change", cb));
  return () => queries.forEach((m) => m.removeEventListener("change", cb));
}
