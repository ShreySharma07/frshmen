"use client";

// The signed-out landing page (docs/decisions.md 2026-10-19 and 2026-10-23), at /preview until
// every feature it describes works. Shows the 2026-10-23 counts at once, then the live ones.
// Chapters alternate graphite (.lp-dark) and white (.lp-light).
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { ArrowRight, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchMeta } from "@/lib/api";
import { Wordmark } from "../Wordmark";
import { GlobeStory } from "./GlobeStory";
import { HowItWorks } from "./HowItWorks";
import { fmt, fromMeta, SNAPSHOT } from "./places";
import { setLenis } from "./scroll";
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
      <Nav fresher={counts.fresher} />
      <main>
        <GlobeStory counts={counts} />
        <HowItWorks />
      </main>
      <Footer />
    </div>
  );
}

// The top bar: frosted white machined glass (Shrey, 2026-10-23). The page shows through it,
// blurred; its text is dark so it reads the same over the carbon and the limestone chapters.
function Nav({ fresher }: { fresher: number }) {
  return (
    <header className="lp-light fixed inset-x-0 top-0 z-30 px-[var(--gutter)] pt-[max(0.75rem,env(safe-area-inset-top,0px))]">
      <nav aria-label="Main" className="machined-glass glass-white mx-auto flex h-14 items-center gap-1 rounded-full pr-2 pl-5 text-lp-ink sm:gap-2">
        <Link href="/preview" aria-label="Kario home" className="mr-auto"><Wordmark className="h-[24px] w-auto text-lp-ink" /></Link>
        <a href="#how" className="hidden rounded-full px-3 py-2 text-[15px] transition-colors duration-quick hover:bg-lp-raised/60 md:block">How it works</a>
        <Link href="/" className="hidden rounded-full px-3 py-2 text-[15px] transition-colors duration-quick hover:bg-lp-raised/60 md:block">Jobs</Link>
        <button type="button" disabled title="Sign-in comes next" aria-label="Your profile (sign-in comes next)" className="hidden size-10 place-items-center rounded-full bg-lp-raised/60 text-lp-ink sm:grid">
          <UserRound aria-hidden className="size-5" strokeWidth={1.75} />
        </button>
        <Link href="/?yrs=0" className="btn-primary btn-tactile btn-sm ml-1 gap-1.5">
          <span><span className="hidden sm:inline">Browse </span>{fmt(fresher)} fresher jobs</span>
          <ArrowRight aria-hidden className="size-4" strokeWidth={2} />
        </Link>
      </nav>
    </header>
  );
}

function Footer() {
  return (
    <footer className="lp-dark overflow-hidden bg-lp-bg px-[var(--gutter)] pt-[clamp(6rem,12vw,10rem)] text-lp-ink">
      <div className="flex flex-wrap items-end justify-between gap-6 pb-10">
        <p className="max-w-[28rem] text-[15px] text-lp-muted">No LinkedIn, Indeed or Glassdoor scraping. Nothing goes out in your name until you approve it.</p>
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
