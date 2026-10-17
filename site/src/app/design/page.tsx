// Token sheet: every colour, size, radius and motion value on one page, to check both themes.
// A Server Component, so it ships no JavaScript of its own.
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Design tokens · Kario", robots: { index: false } };

const COLOURS = [
  ["canvas", "Page background"], ["surface", "Hover, subtle fills"], ["line", "Dividers, borders"],
  ["ink", "Main text"], ["muted", "Secondary text"], ["faint", "Icons and dividers only"],
  ["accent", "The brand colour"], ["selected", "Selected row"], ["card", "Fit card"],
  ["card-accent", "Years in the fit card"], ["code", "Keyword pills"],
] as const;

const TYPE = [
  ["text-display", "3+ years", "font-mono font-semibold"], ["text-title", "ML Engineer (Data), Foundational Models", "font-medium"],
  ["text-base", "Default text", ""], ["text-body", "Machine Learning Engineer, Search Quality", "font-medium"],
  ["text-meta", "Sarvam AI · Bengaluru · 21 May", "text-muted"], ["text-caption", "3–5 yrs", "font-mono text-accent"],
] as const;

export default function Tokens() {
  return (
    <main className="mx-auto max-w-3xl space-y-12 px-4 py-10">
      <h1 className="text-title font-medium">Design tokens</h1>

      <section>
        <h2 className="mb-3 text-meta font-medium text-muted">Colour</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {COLOURS.map(([name, use]) => (
            <div key={name} className="flex items-center gap-3">
              <span className="size-10 shrink-0 rounded-md border border-line" style={{ background: `var(--${name})` }} />
              <span><span className="block font-mono text-meta">{name}</span><span className="text-meta text-muted">{use}</span></span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-meta font-medium text-muted">Type</h2>
        <div className="space-y-3">
          {TYPE.map(([cls, sample, extra]) => (
            <div key={cls} className="flex items-baseline gap-4">
              <span className="w-28 shrink-0 font-mono text-caption text-muted">{cls}</span>
              <span className={`${cls} ${extra}`}>{sample}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-meta font-medium text-muted">Radius and elevation</h2>
        <div className="flex flex-wrap gap-4">
          <span className="rounded-sm border border-line bg-code px-1.5 font-mono text-caption">sm · pill</span>
          <span className="rounded-md border border-line px-3 py-1.5 text-meta shadow-raised">md · chip, button</span>
          <span className="rounded-lg border border-line px-4 py-3 text-meta shadow-menu">lg · card, menu</span>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-meta font-medium text-muted">Components from tokens</h2>
        <div className="grid gap-5 rounded-lg bg-card p-5 text-card-text sm:grid-cols-2">
          <div>
            <div className="font-mono text-display font-semibold text-card-accent">3+ <span className="text-base">years</span></div>
            <p className="mt-3 border-l-2 border-card-accent/40 pl-3 text-meta italic text-card-muted">
              3+ years of experience building large-scale data systems.
            </p>
          </div>
          <ul className="space-y-1.5 text-body sm:border-l sm:border-card-line sm:pl-5">
            <li>✓ AI/ML role</li><li className="text-card-muted">— Visa not mentioned</li>
          </ul>
        </div>
        <div className="mt-4 flex gap-2">
          <button className="rounded-md bg-accent px-4 py-2.5 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">Apply on Sarvam AI</button>
          <button className="rounded-md border border-line px-3 py-2.5 text-meta font-medium transition-colors duration-quick hover:bg-surface">Save</button>
        </div>
        <div className="mt-4 rounded-md bg-selected px-4 py-3 text-body font-medium">Selected row <span className="float-right font-mono text-caption text-accent">3+ yrs</span></div>
      </section>
    </main>
  );
}
