"use client";

// The hero (critique 2026-10-23, "The Highlighter"): a wall of real deciding lines from postings.
// A highlighter runs down it on load: what takes the reader is marked, what asks for more is struck
// through. The reader says how many years they have and the wall re-reads itself. Scrolling clears
// the wall to one line, which becomes a real job card. Without WebGL or with reduced motion the
// same wall is plain text with the same marks, and nothing waits on an animation.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { fetchEvidence, type EvidenceLine } from "@/lib/api";
import { fmt, type Counts } from "./places";
import { clip, fit, rows, STARTER, YEARS } from "./wall";
import type { WallDrive } from "./WallScene";

gsap.registerPlugin(ScrollTrigger);

const WallScene = dynamic(() => import("./WallScene"), { ssr: false });

export function Highlighter({ counts }: { counts: Counts }) {
  const root = useRef<HTMLElement>(null);
  const drive = useRef<WallDrive>({ sweep: 0, collapse: 0, pointerX: 0, pointerY: 0 });
  const [years, setYears] = useState(0);
  const [lines, setLines] = useState<EvidenceLine[]>(STARTER);
  const [glReady, setGlReady] = useState(false);
  const mode = useSyncExternalStore(onMotionChange, () => (canAnimate() ? "scroll" : "flow"), () => "flow");

  useEffect(() => {
    const ctl = new AbortController();
    fetchEvidence(240, ctl.signal).then((r) => r.lines.length > 40 && setLines(r.lines)).catch(() => {});
    return () => ctl.abort();
  }, []);

  // The card is about a real line that takes the reader, with a company and a title to show.
  const hero = useMemo(() => lines.find((l) => fit(l, years) === "fits" && l.title) ?? null, [lines, years]);

  // The highlighter runs once on load, and again (faster) whenever the reader changes their years.
  const first = useRef(true);
  useEffect(() => {
    if (mode !== "scroll") { drive.current.sweep = 1; return; }
    const tween = gsap.fromTo(drive.current, { sweep: 0 }, { sweep: 1, duration: first.current ? 2.6 : 1.1, delay: first.current ? 0.5 : 0, ease: "power2.inOut" });
    first.current = false;
    return () => { tween.kill(); };
  }, [years, mode, lines]);

  useEffect(() => {
    if (mode !== "scroll" || !root.current) return;
    const ctx = gsap.context(() => {
      const q = gsap.utils.selector(root);
      const tl = gsap.timeline({ scrollTrigger: { trigger: root.current, start: "top top", end: "bottom bottom", scrub: 0.6 } });
      tl.to({}, { duration: 0.18 })
        .to(q("[data-hl-copy]"), { autoAlpha: 0, y: -40, duration: 0.16, ease: "power2.in" }, 0.18)
        .to(drive.current, { collapse: 1, duration: 0.36, ease: "power2.inOut" }, 0.22)
        .to(q("[data-hl-dom]"), { autoAlpha: 0, duration: 0.2 }, 0.22)
        .fromTo(q("[data-hl-card]"), { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.16, ease: "power2.out" }, 0.6)
        .to({}, { duration: 0.24 });
    }, root);
    const move = (e: PointerEvent) => {
      drive.current.pointerX = e.clientX / window.innerWidth - 0.5;
      drive.current.pointerY = e.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => { ctx.revert(); window.removeEventListener("pointermove", move); };
  }, [mode]);

  const within = years <= 5 ? counts.within?.[String(years)] : counts.total;
  const jobsHref = years <= 5 ? `/?yrs=${years}` : "/";
  const label = YEARS.find((y) => y.years === years)?.label ?? "";

  return (
    <section ref={root} data-mode={mode} aria-labelledby="hl-title" className="hl lp-light relative bg-lp-bg text-lp-ink">
      <div className="hl-frame relative overflow-clip">
        {/* The wall as text: the printed page, the fallback, and what shows until WebGL is up. */}
        <DomWall lines={lines} years={years} hidden={glReady && mode === "scroll"} />
        {mode === "scroll" && <div className="hl-wall absolute inset-0"><WallScene lines={lines} years={years} hero={hero} drive={drive} onReady={() => setGlReady(true)} /></div>}

        <div data-hl-copy className="hl-copy relative z-10 grid-page">
          <div className="col-span-full grid max-w-[44rem] gap-6 lg:col-span-6">
            <h1 id="hl-title" className="text-[clamp(2.75rem,6.2vw,5.75rem)] leading-[0.95] font-semibold tracking-[-0.05em] text-balance">
              Not another job board. An agent that gets you your next job.
            </h1>
            <p className="max-w-[34rem] text-[clamp(1.0625rem,1.4vw,1.25rem)] leading-relaxed">
              Kario reads every opening to the line that says who it&rsquo;s for. Tell it your years; it marks what takes you and strikes what doesn&rsquo;t.
            </p>
            <fieldset className="grid gap-3">
              <legend className="mb-3 text-[15px] text-lp-muted">Your experience</legend>
              <div role="radiogroup" aria-label="Your experience" className="flex flex-wrap gap-2">
                {YEARS.map((y) => (
                  <button
                    key={y.years}
                    type="button"
                    role="radio"
                    aria-checked={years === y.years}
                    onClick={() => setYears(y.years)}
                    className={`rounded-full border px-4 py-2 text-[15px] transition-colors duration-quick ${years === y.years ? "border-lp-ink bg-lp-ink text-lp-bg" : "border-lp-line bg-lp-raised hover:border-lp-ink"}`}
                  >
                    {y.label}
                  </button>
                ))}
              </div>
            </fieldset>
            <div>
              <Link href={jobsHref} className="btn-primary btn-tactile gap-2">
                {within != null ? `See ${fmt(within)} jobs for ${label === "Fresher" ? "freshers" : label}` : "See jobs for your years"}
                <ArrowRight aria-hidden className="size-4" strokeWidth={2} />
              </Link>
            </div>
          </div>
        </div>

        {hero && <HeroCard line={hero} years={years} href={jobsHref} />}
      </div>
    </section>
  );
}

function DomWall({ lines, years, hidden }: { lines: EvidenceLine[]; years: number; hidden: boolean }) {
  const shown = useMemo(() => rows(lines, 66), [lines]);
  return (
    <div data-hl-dom aria-hidden className={`hl-dom absolute inset-0 transition-opacity duration-layout ${hidden ? "opacity-0" : ""}`}>
      <ul className="columns-1 gap-10 px-[var(--gutter)] pt-24 font-mono text-[13px] leading-[2.15] md:columns-2 lg:columns-3">
        {shown.map((l, i) => {
          const f = fit(l, years);
          return (
            <li key={i} className={`truncate ${f === "over" ? "text-lp-muted line-through decoration-lp-del" : f === "unclear" ? "text-lp-muted" : ""}`}>
              {f === "fits" ? <mark>{clip(l.text)}</mark> : clip(l.text)}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function HeroCard({ line, years, href }: { line: EvidenceLine; years: number; href: string }) {
  const asks = line.yoe_min != null ? `asks for ${line.yoe_min}+ year${line.yoe_min === 1 ? "" : "s"}` : line.level === "fresher" ? "open to freshers" : "experience not stated";
  return (
    <div data-hl-card className="hl-card pointer-events-none absolute inset-x-0 bottom-[12svh] z-10 grid-page opacity-0">
      <div className="pointer-events-auto col-span-full rounded-2xl border border-lp-line bg-lp-surface p-2 shadow-sm lg:col-span-6 lg:col-start-4">
        <div className="rounded-xl border border-lp-window-line bg-lp-raised p-5">
          <p className="text-[14px] text-lp-muted">{line.company}</p>
          <p className="mt-0.5 text-[19px] font-medium leading-snug">{line.title}</p>
          <p className="mt-4 rounded-lg bg-lp-window-bar p-3 font-mono text-[13px] leading-relaxed">&ldquo;<mark>{line.text}</mark>&rdquo;</p>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <span className="rounded-full bg-lp-ok px-2.5 py-1 font-mono text-[12px] font-semibold text-lp-term">Takes you · {asks}</span>
            <Link href={href} className="text-[15px] font-medium text-lp-accent-text underline-offset-4 hover:underline">
              {years <= 5 ? "More like this" : "Browse all jobs"}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

// The scene needs WebGL and a reader who hasn't asked for less motion; otherwise the text wall stays.
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)");
function canAnimate() {
  if (reducedMotion().matches) return false;
  const probe = document.createElement("canvas");
  return Boolean(probe.getContext("webgl2") || probe.getContext("webgl"));
}
function onMotionChange(cb: () => void) {
  const m = reducedMotion();
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}
