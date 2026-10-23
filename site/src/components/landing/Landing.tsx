"use client";

// The signed-out landing page (docs/decisions.md 2026-10-19 and 2026-10-23), at /preview until
// every feature it describes works. Shows the 2026-10-23 counts at once, then the live ones.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchMeta } from "@/lib/api";
import { Wordmark } from "../Wordmark";
import { GlobeStory } from "./GlobeStory";
import { HowItWorks } from "./HowItWorks";
import { fromMeta, SNAPSHOT } from "./places";
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
    lenis.on("scroll", ScrollTrigger.update);
    const raf = (t: number) => lenis.raf(t * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);
    return () => { gsap.ticker.remove(raf); lenis.destroy(); };
  }, []);

  return (
    <div className="night landing min-h-svh">
      <Nav />
      <main>
        <GlobeStory counts={counts} />
        <HowItWorks />
      </main>
      <Footer />
    </div>
  );
}

// The one glass surface on the page (Shrey's call, 2026-10-23): a bar that blurs what scrolls under it.
function Nav() {
  return (
    <header className="fixed inset-x-0 top-0 z-30 px-[var(--gutter)] pt-[max(0.75rem,env(safe-area-inset-top,0px))]">
      <nav aria-label="Main" className="mx-auto flex h-14 items-center gap-2 rounded-full bg-night-surface/70 pr-2 pl-5 backdrop-blur-xl backdrop-saturate-150 sm:gap-6">
        <Link href="/preview" aria-label="Kario home" className="mr-auto"><Wordmark className="h-[22px] w-auto text-night-ink" /></Link>
        <a href="#how" className="rounded-full px-3 py-2 text-[15px] transition-colors duration-quick hover:bg-night-raised">How it works</a>
        <Link href="/" className="rounded-full px-3 py-2 text-[15px] transition-colors duration-quick hover:bg-night-raised">Jobs</Link>
        <button type="button" disabled title="Sign-in comes next" aria-label="Your profile (sign-in comes next)" className="grid size-10 place-items-center rounded-full bg-night-raised text-night-muted">
          <UserRound aria-hidden className="size-5" strokeWidth={1.75} />
        </button>
      </nav>
    </header>
  );
}

function Footer() {
  return (
    <footer className="mt-[clamp(6rem,14vw,12rem)] overflow-hidden px-[var(--gutter)]">
      <div className="flex flex-wrap items-end justify-between gap-6 pb-10">
        <p className="max-w-[28rem] text-[15px] text-night-muted">No LinkedIn, Indeed or Glassdoor scraping. Nothing goes out in your name until you approve it.</p>
        <ul className="flex gap-6 text-[15px]">
          <li><Link href="/" className="hover:text-night-accent">Jobs</Link></li>
          <li><a href="#how" className="hover:text-night-accent">How it works</a></li>
          <li><a href="https://github.com/ShreySharma07/frshmen" className="hover:text-night-accent">GitHub</a></li>
        </ul>
      </div>
      <Wordmark className="-mb-[3%] block h-auto w-full text-night-ink" />
    </footer>
  );
}
