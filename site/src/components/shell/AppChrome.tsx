"use client";
// Sidebar, phone tab bar and the search bar. Kept light: it rides on the job list's first load.
import { Bot, BriefcaseBusiness, ChartNoAxesColumn, KanbanSquare, Search } from "lucide-react";
import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { IntentLink } from "@/components/IntentLink";
import { readSession, subscribeSession } from "@/lib/session";
import { SECTIONS, isCurrent } from "./sections";

// The palette loads the first time someone opens it.
const CommandPalette = dynamic(() => import("@/components/CommandPalette").then((m) => m.CommandPalette), { ssr: false });

const ICON = { "/": BriefcaseBusiness, "/applications": KanbanSquare, "/insights": ChartNoAxesColumn, "/agent": Bot } as const;
const ROW = 40; // one sidebar row plus its gap, in px: the marker moves by this much per section

/** The wordmark, for the page's top bar on phones (where there is no sidebar to carry it). */
export const LogoContext = createContext<React.ReactNode>(null);

export function AppChrome({ logo, children }: { logo: React.ReactNode; children: React.ReactNode }) {
  const session = useSyncExternalStore(subscribeSession, readSession, () => null);
  const path = usePathname();
  const sections = SECTIONS.filter((s) => !s.signedIn || session);
  const active = sections.findIndex((s) => isCurrent(s.href, path));

  const [palette, setPalette] = useState(false);
  const close = useCallback(() => setPalette(false), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((o) => !o); }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);

  return (
    <LogoContext value={logo}>
      <div className="lg:grid lg:grid-cols-[212px_minmax(0,1fr)]">
        <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line px-3 py-4 lg:flex">
          <IntentLink href="/" aria-label="Aventra, open jobs" className="mb-5 block px-2">{logo}</IntentLink>
          <nav aria-label="Sections" className="relative flex flex-col gap-0.5">
            {/* One marker that slides to the current section: where you are, and where you came from. */}
            {active >= 0 && (
              <span aria-hidden className="absolute inset-x-0 top-0 h-[38px] rounded-md bg-selected shadow-[inset_2px_0_var(--accent)] transition-transform duration-move ease-out-soft"
                style={{ transform: `translateY(${active * ROW}px)` }} />
            )}
            {sections.map((s, i) => {
              const Icon = ICON[s.href];
              return (
                <IntentLink key={s.href} href={s.href} aria-current={i === active ? "page" : undefined}
                  className={`press relative flex h-[38px] items-center gap-2.5 rounded-md px-2.5 text-body font-medium transition-colors duration-quick ${i === active ? "text-ink" : "text-muted hover:text-ink"}`}>
                  <Icon aria-hidden className="size-4" strokeWidth={1.75} />{s.label}
                </IntentLink>
              );
            })}
          </nav>
          {!session && (
            <p className="mt-5 px-2 text-meta text-muted">
              <IntentLink href="/login" className="font-medium text-accent-text underline underline-offset-2">Sign in</IntentLink> to track
              applications, see how you compare, and tailor your resume.
            </p>
          )}
        </aside>

        <div className="flex min-h-dvh min-w-0 flex-col pb-16 lg:pb-0">
          <div className="flex-1">{children}</div>
          {/* The search bar, within reach on every page (wide screens; phones have the tab bar). */}
          <div className="pointer-events-none sticky bottom-0 z-20 hidden bg-gradient-to-t from-canvas from-40% px-6 pb-4 pt-6 lg:block">
            <button type="button" onClick={() => setPalette(true)}
              className="press pointer-events-auto flex h-11 w-full items-center gap-2.5 rounded-lg border border-ink/70 bg-card px-3.5 text-left text-body text-muted shadow-menu transition-colors duration-quick hover:border-ink">
              <Search aria-hidden className="size-4" />
              Search jobs, jump to a page, or apply a filter
              <kbd className="ml-auto rounded-sm border border-line px-1.5 font-mono text-caption">Ctrl K</kbd>
            </button>
          </div>
        </div>

        <nav aria-label="Sections" className="fixed inset-x-0 bottom-0 z-30 flex h-16 border-t border-line bg-canvas/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden">
          {sections.map((s, i) => {
            const Icon = ICON[s.href];
            return (
              <IntentLink key={s.href} href={s.href} aria-current={i === active ? "page" : undefined}
                className={`press relative flex flex-1 flex-col items-center justify-center gap-1 text-caption font-medium transition-colors duration-quick ${i === active ? "text-ink" : "text-muted"}`}>
                <span className={`grid h-7 w-12 place-items-center rounded-full transition-colors duration-move ${i === active ? "bg-accent text-on-accent" : ""}`}>
                  <Icon aria-hidden className="size-[18px]" strokeWidth={1.75} />
                </span>
                {s.label}
              </IntentLink>
            );
          })}
          {!session && (
            <IntentLink href="/login" className="press flex flex-1 flex-col items-center justify-center gap-1 text-caption font-medium text-muted">
              <span className="grid h-7 w-12 place-items-center"><Bot aria-hidden className="size-[18px]" strokeWidth={1.75} /></span>Sign in
            </IntentLink>
          )}
        </nav>
      </div>
      {palette && <CommandPalette onClose={close} />}
    </LogoContext>
  );
}
