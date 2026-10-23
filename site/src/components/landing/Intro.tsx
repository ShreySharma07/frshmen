"use client";

// The opening count (critique 2026-10-23, the micro layer): a paper screen counts the openings
// Kario has read while a highlighter runs under the number, then wipes up to the hero. Once per
// visit, about 1.6 s, and never with reduced motion or without script: an inline script hides it
// before the first paint in those cases, so nobody watches a loader for a page that's ready.
import { gsap } from "gsap";
import { useEffect, useRef } from "react";
import { Wordmark } from "../Wordmark";
import { finishIntro } from "./intro";
import { fmt } from "./places";

const SEEN = "kario:intro";
// Runs while the page parses, before paint (sessionStorage can throw in private modes).
const SKIP = `try{if(sessionStorage.getItem("${SEEN}")||matchMedia("(prefers-reduced-motion: reduce)").matches)document.documentElement.classList.add("intro-skip")}catch(e){document.documentElement.classList.add("intro-skip")}`;

export function Intro({ total }: { total: number }) {
  const root = useRef<HTMLDivElement>(null);
  const num = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el || document.documentElement.classList.contains("intro-skip")) { finishIntro(); return; }
    document.documentElement.classList.add("intro-on"); // holds the page still while it runs
    const count = { n: 0 };
    const tl = gsap.timeline({
      onComplete: () => {
        el.style.display = "none";
        document.documentElement.classList.remove("intro-on");
        try { sessionStorage.setItem(SEEN, "1"); } catch {}
        finishIntro();
      },
    });
    tl.to(count, { n: total, duration: 1.1, ease: "power2.out", onUpdate: () => { if (num.current) num.current.textContent = fmt(Math.round(count.n)); } })
      .fromTo(el.querySelector("[data-intro-mark]"), { scaleX: 0 }, { scaleX: 1, duration: 1.1, ease: "power2.out" }, 0)
      .to(el, { clipPath: "inset(0 0 100% 0)", duration: 0.55, ease: "expo.inOut" }, "+=0.15");
    return () => { tl.kill(); document.documentElement.classList.remove("intro-on"); finishIntro(); };
    // Counts once, with the number known at load; the live count arriving later doesn't restart it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: SKIP }} />
      <noscript><style>{".intro{display:none}"}</style></noscript>
      <div ref={root} aria-hidden className="intro lp-light fixed inset-0 z-50 grid bg-lp-bg text-lp-ink" style={{ clipPath: "inset(0 0 0% 0)" }}>
        <div className="px-[var(--gutter)] pt-[max(0.75rem,env(safe-area-inset-top,0px))]">
          <div className="flex h-14 items-center pl-5"><Wordmark className="h-[24px] w-auto" /></div>
        </div>
        <div className="grid-page self-end pb-[12svh]">
          <div className="col-span-full grid gap-4">
            <span className="relative w-fit font-mono text-[clamp(4.5rem,15vw,13rem)] leading-[0.85] tracking-[-0.045em] tabular-nums">
              <i data-intro-mark className="absolute inset-x-[-0.06em] bottom-[0.04em] h-[0.3em] origin-left bg-lp-mark" />
              <span ref={num} className="relative">0</span>
            </span>
            <span className="text-[clamp(1.0625rem,1.6vw,1.375rem)] text-lp-muted">openings read, line by line.</span>
          </div>
        </div>
      </div>
    </>
  );
}
