"use client";

// The signed-out landing page (docs/decisions.md 2026-10-19 and 2026-10-23), at /preview until
// every feature it describes works. Shows the 2026-10-23 counts at once, then the live ones.
// Chapters alternate graphite (.lp-dark) and white (.lp-light).
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { ArrowRight, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { fetchMeta } from "@/lib/api";
import { Wordmark } from "../Wordmark";
import { GlobeStory } from "./GlobeStory";
import { Highlighter } from "./Highlighter";
import { HowItWorks } from "./HowItWorks";
import { Intro } from "./Intro";
import { fmt, fromMeta, SNAPSHOT } from "./places";
import { setLenis } from "./scroll";
import { FinalCall, Proof, Trust } from "./Story";
import "./landing.css";

gsap.registerPlugin(ScrollTrigger);

export function Landing() {
  const [counts, setCounts] = useState(SNAPSHOT);

  useEffect(() => {
    const ctl = new AbortController();
    fetchMeta(ctl.signal).then((m) => setCounts(fromMeta(m))).catch(() => {});
    return () => ctl.abort();
  }, []);

  // Smooth scrolling on this page only (CLAUDE.md), driven by GSAP's clock so scroll scenes stay in step.
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ lerp: 0.12 });
    setLenis(lenis);
    lenis.on("scroll", ScrollTrigger.update);
    const raf = (t: number) => lenis.raf(t * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);
    return () => { gsap.ticker.remove(raf); setLenis(null); lenis.destroy(); };
  }, []);

  return (
    <div className="landing lp-dark min-h-svh">
      <Intro total={counts.total} />
      <Nav total={counts.total} />
      <main>
        <Highlighter counts={counts} />
        <Proof counts={counts} />
        <GlobeStory counts={counts} />
        <HowItWorks />
        <Trust />
        <FinalCall counts={counts} />
      </main>
      <Footer />
    </div>
  );
}

// The top bar: clear white machined glass (Shrey, 2026-10-23). The page shows through it, so its
// text follows what is underneath: light over the navy chapters, dark over the parchment ones.
function Nav({ total }: { total: number }) {
  const bar = useRef<HTMLElement>(null);
  const [overLight, setOverLight] = useState(false);

  useEffect(() => {
    let frame = 0;
    const check = () => {
      frame = 0;
      const el = bar.current;
      if (!el) return;
      // What the reader sees under the bar's middle decides: the topmost element that isn't the
      // bar and isn't mostly faded out (scroll scenes cross-fade whole panels).
      const y = el.getBoundingClientRect().bottom - 28;
      const under = document.elementsFromPoint(window.innerWidth / 2, y).find((n) => !el.contains(n) && shown(n));
      setOverLight(Boolean(under?.closest(".lp-light")));
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(check); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); };
  }, []);

  return (
    <header ref={bar} className={`${overLight ? "lp-light" : "lp-dark"} fixed inset-x-0 top-0 z-30 px-[var(--gutter)] pt-[max(0.75rem,env(safe-area-inset-top,0px))]`}>
      <nav aria-label="Main" className="machined-glass glass-white mx-auto flex h-14 items-center gap-1 rounded-full pr-2 pl-5 text-lp-ink sm:gap-2">
        <Link href="/preview" aria-label="Kario home" className="mr-auto"><Wordmark className="h-[24px] w-auto text-lp-ink" /></Link>
        <a href="#how" className="hidden rounded-full px-3 py-2 text-[15px] transition-colors duration-quick hover:bg-lp-raised/60 md:block">How it works</a>
        <Link href="/" className="hidden rounded-full px-3 py-2 text-[15px] transition-colors duration-quick hover:bg-lp-raised/60 md:block">Jobs</Link>
        <button type="button" disabled title="Sign-in comes next" aria-label="Your profile (sign-in comes next)" className="hidden size-10 place-items-center rounded-full bg-lp-raised/60 text-lp-ink sm:grid">
          <UserRound aria-hidden className="size-5" strokeWidth={1.75} />
        </button>
        <Link href="/" className="btn-primary btn-tactile btn-sm ml-1 gap-1.5">
          <span><span className="hidden sm:inline">Browse </span>{fmt(total)} jobs</span>
          <ArrowRight aria-hidden className="size-4" strokeWidth={2} />
        </Link>
      </nav>
    </header>
  );
}

/** False when the element, or anything around it, is at less than half opacity. */
function shown(el: Element) {
  for (let n: Element | null = el; n; n = n.parentElement) if (Number(getComputedStyle(n).opacity) < 0.5) return false;
  return true;
}

function Footer() {
  return (
    <footer className="lp-dark overflow-hidden bg-lp-bg px-[var(--gutter)] pt-[clamp(6rem,12vw,10rem)] text-lp-ink">
      <div className="flex flex-wrap items-end justify-between gap-6 pb-10">
        <p className="max-w-[28rem] text-[15px] text-lp-muted">Kario reads every opening to the line that decides who it&rsquo;s for, then does the legwork with you.</p>
        <ul className="flex gap-6 text-[15px]">
          <li><Link href="/" className="hover:text-lp-accent-text">Jobs</Link></li>
          <li><a href="#how" className="hover:text-lp-accent-text">How it works</a></li>
          <li><a href="https://github.com/ShreySharma07/frshmen" className="hover:text-lp-accent-text">GitHub</a></li>
        </ul>
      </div>
      <Wordmark className="-mb-[3%] block h-auto w-full text-lp-ink" />
    </footer>
  );
}
