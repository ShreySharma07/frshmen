"use client";

// After the Highlighter, one scroll scene: the globe turns to India while arcs from hubs abroad land
// on it, then dives in, and the city lights fly into the table beside it; then the dark gives way to
// a paper field for the arrivals board. Without script, or with reduced motion, the panels simply
// stack (mode "flow") with the globe facing India, so nothing hides behind an animation that didn't
// run. Without WebGL, or with Save-Data on, a still picture of the globe stands in.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Board } from "./Board";
import type { GlobeView } from "./GlobeScene";
import { fmt, type Counts } from "./places";

gsap.registerPlugin(ScrollTrigger);

const GlobeScene = dynamic(() => import("./GlobeScene"), { ssr: false });

// Indian cities sit close together on the globe, so only places far apart get a label.
const LABELLED = new Set(["blr", "us", "uk", "jp", "sg"]);
export function GlobeStory({ counts }: { counts: Counts }) {
  const root = useRef<HTMLElement>(null);
  const view = useRef<GlobeView>({ focus: 0, arcs: 0, dive: 0, morph: 0, drag: 0 });
  const mode = useSyncExternalStore(onMotionChange, () => (reducedMotion().matches ? "flow" : "scroll"), () => "flow");
  const still = useSyncExternalStore(noChange, stillWanted, () => false);
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState(false);

  // Draw only while the scene is on screen.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const seen = new IntersectionObserver(([e]) => setActive(e.isIntersecting));
    seen.observe(el);
    return () => seen.disconnect();
  }, []);

  // Stacked screens show the globe as it ends its turn: facing India, arcs drawn.
  useEffect(() => {
    if (mode === "flow") Object.assign(view.current, { focus: 1, arcs: 1, dive: 0, morph: 0 });
  }, [mode]);

  // Drag to turn it (the scroll still brings it back to India).
  const drag = useRef<{ x: number; from: number } | null>(null);
  const onDown = (e: React.PointerEvent<HTMLDivElement>) => {
    drag.current = { x: e.clientX, from: view.current.drag };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    if (drag.current) view.current.drag = drag.current.from - (e.clientX - drag.current.x) * 0.35;
  };
  const onUp = () => { drag.current = null; };

  useEffect(() => {
    if (mode !== "scroll" || !root.current) return;
    // Start from the top of the story, not from the stacked-screens pose set while hydrating.
    Object.assign(view.current, { focus: 0, arcs: 0, dive: 0, morph: 0 });
    const ctx = gsap.context(() => {
      const q = gsap.utils.selector(root);
      const mm = gsap.matchMedia();
      mm.add({ wide: "(min-width: 64rem)", narrow: "(max-width: 63.99rem)" }, (c) => {
        const wide = c.conditions?.wide;
        const tl = gsap.timeline({
          defaults: { ease: "power2.inOut" },
          scrollTrigger: { trigger: root.current, start: "top top", end: "bottom bottom", scrub: 0.6 },
        });
        // Turn to India as the arcs land, dive in, then the city lights become the table's bullets
        // while its rows arrive. Hand-offs never overlap, so text is never half-faded under another.
        tl.set(q("[data-panel=sources]"), { autoAlpha: 0 }, 0)
          .to(view.current, { focus: 1, duration: 0.26 }, 0.04)
          .to(view.current, { arcs: 1, duration: 0.24, ease: "none" }, 0.06)
          .to(q("[data-globe]"), wide ? { scale: 1.08, duration: 0.26 } : { scale: 1, duration: 0.26 }, 0.04)
          .to(q(".reticle"), { autoAlpha: 0, duration: 0.04 }, 0.3)
          .to(view.current, { dive: 1, duration: 0.16 }, 0.32)
          // The lights land on bare background first; then each row fades in over its light, its own
          // dot exactly where the light came to rest (the canvas is under the rows, so this is the hand-off).
          .to(view.current, { morph: 1, duration: 0.1 }, 0.4)
          .fromTo(q("[data-place-row]"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.05, stagger: 0.008, ease: "power1.out" }, 0.5)
          .to(q("[data-globe-layer], [data-panel=places]"), { autoAlpha: 0, duration: 0.06, ease: "power2.in" }, 0.6)
          .fromTo(q("[data-field]"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.06, ease: "none" }, 0.64)
          .fromTo(q("[data-panel=sources]"), { autoAlpha: 0, y: 48 }, { autoAlpha: 1, y: 0, duration: 0.1, ease: "power2.out" }, 0.7)
          .to({}, { duration: 0.16 });
        return () => { Object.assign(view.current, { focus: 0, arcs: 0, dive: 0, morph: 0 }); };
      });
    }, root);
    return () => ctx.revert();
  }, [mode]);

  const india = counts.cities.slice(0, 4);
  const slot = new Set(india.map((p) => p.id));
  const abroad = counts.abroad.slice(0, 4);
  const labelled = [...counts.cities, ...counts.abroad].filter((p) => LABELLED.has(p.id));

  return (
    <section ref={root} data-mode={mode} aria-label="Kario" className="story relative">
      <div className="story-frame relative">
        <div data-field aria-hidden className="lp-light absolute inset-0 bg-lp-bg" />
        <div data-globe className="globe-box pointer-events-none absolute">
          <div
            data-globe-anchor
            role={still ? undefined : "img"}
            aria-label={still ? undefined : "The earth as dots, with lights where Kario has open jobs and arcs from hubs abroad to India. Drag to turn it."}
            onPointerDown={still ? undefined : onDown}
            onPointerMove={still ? undefined : onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
            className={`relative aspect-square ${still ? "" : "pointer-events-auto cursor-grab touch-pan-y active:cursor-grabbing"}`}
          >
            {/* Viewfinder ticks at the globe's corners. */}
            <div className="reticle hidden lg:block" aria-hidden><i /><i /><i /><i /></div>
            {still && (
              // Captured from the live globe, facing India with its arcs drawn (2026-10-23 counts).
              // eslint-disable-next-line @next/next/no-img-element -- static export, no image optimiser
              <img src="/landing/globe.webp" alt="The earth as dots, with lights on Indian cities and hubs abroad that have open jobs" className="size-full" />
            )}
          </div>
        </div>
        {!still && (
          <div data-globe-layer aria-hidden className={`globe-layer pointer-events-none absolute inset-x-0 top-0 h-[100svh] transition-opacity duration-landing ease-out-expo ${ready ? "" : "opacity-0"}`}>
            <GlobeScene cities={counts.cities} abroad={counts.abroad} view={view} root={root} still={mode === "flow"} active={active} onReady={() => setReady(true)} />
            {labelled.map((p) => (
              <span key={p.id} data-globe-label={p.id} className="globe-label machined-glass tabular-nums">
                {p.name} <b>{fmt(p.n)}</b>
              </span>
            ))}
          </div>
        )}

        <div data-panel="places" className="panel">
          <div className="col-span-full grid gap-7 lg:col-span-5 lg:col-start-8">
            <h2 className="font-display text-[clamp(3rem,6vw,5.5rem)] leading-[0.92] tracking-[-0.02em] text-balance">Find jobs all around the globe.</h2>
            <p className="max-w-[30rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed">
              India&rsquo;s tech hubs first, then the cities abroad that are hiring. Roles outside India are tagged when they sponsor a visa or help you relocate.
            </p>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-3 text-[16px] tabular-nums sm:max-w-[30rem]">
              {[...india, ...abroad.slice(0, 2)].map((p) => (
                <div key={p.id} data-place-row className="flex items-baseline justify-between gap-3 rounded-md bg-lp-surface px-3 py-2">
                  <dt className="flex items-center gap-2.5 text-lp-muted">
                    {/* A city's light lands here at the end of the dive; on stacked screens it's plain CSS. */}
                    {slot.has(p.id) && <i data-city-slot={p.id} aria-hidden className="city-slot size-2 shrink-0 rounded-full bg-lp-accent" />}
                    {p.name}
                  </dt>
                  <dd className="font-medium">{fmt(p.n)}</dd>
                </div>
              ))}
              {counts.visa != null && (
                <div data-place-row className="col-span-2 flex items-baseline justify-between gap-3 rounded-md bg-lp-raised px-3 py-2.5">
                  <dt>Visa or relocation tagged</dt>
                  <dd className="font-semibold text-lp-accent-text">{fmt(counts.visa)}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>

        <div data-panel="sources" className="panel lp-light text-lp-ink">
          <div className="col-span-full grid gap-10 lg:col-span-5">
            <h2 className="max-w-[16ch] font-display text-[clamp(2.75rem,4.8vw,4.75rem)] leading-[0.92] tracking-[-0.02em] text-balance">
              Every opening, straight from the companies hiring.
            </h2>
            <p className="max-w-[36rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed">
              Kario reads each company&rsquo;s own hiring page, so a role shows up here the day it opens, with the line that says who it&rsquo;s for.
            </p>
          </div>
          <div className="col-span-full mt-10 grid gap-3 self-center lg:col-span-7 lg:col-start-6 lg:mt-0">
            <Board />
            <p className="px-1 font-mono text-[12px] leading-relaxed text-lp-muted">
              Read from Greenhouse, Lever, Ashby, Workday, Workable, SmartRecruiters, Oracle Recruiting, Eightfold, Keka, Zoho Recruit, Amazon Jobs and company sites.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// The printed page (no script yet) is "flow"; the browser switches to the scroll scene unless the
// reader asked for less motion, and back if they change that setting.
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)");
const noChange = () => () => {};
let stillCache: boolean | undefined;
function stillWanted() {
  if (stillCache === undefined) {
    const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
    const probe = document.createElement("canvas");
    stillCache = Boolean(saveData) || !(probe.getContext("webgl2") || probe.getContext("webgl"));
  }
  return stillCache;
}
function onMotionChange(cb: () => void) {
  const m = reducedMotion();
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}
