import type { Filters } from "@/lib/filters";

const YEARS = [0, 1, 2, 3, 4, 5];

/**
 * The first filter, written as a sentence: "I have 3 years of experience". Picking a number shows
 * jobs that ask for that many years or fewer (and jobs that state none); picking it again clears
 * it. This is the question Aventra exists to answer, so it is the page's headline.
 */
export function YearsDial({ filters, onChange }: { filters: Filters; onChange: (f: Filters) => void }) {
  const y = filters.years;
  return (
    <div className="px-4 pb-1 pt-6 lg:px-6 lg:pt-9">
      <h1 className="flex flex-wrap items-baseline gap-x-2 gap-y-1 font-display text-[1.75rem] leading-[1.12] sm:gap-x-3 sm:text-headline lg:text-hero">
        <span>I have</span>
        <span role="group" aria-label="Your years of experience" className="flex gap-0.5">
          {YEARS.map((n) => (
            <button key={n} type="button" aria-pressed={y === n} onClick={() => onChange({ ...filters, years: y === n ? null : n })}
              className={`min-w-[1.15em] rounded-md px-[0.22em] text-center transition-colors duration-quick focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${y === n ? "bg-accent text-on-accent" : "text-muted hover:bg-surface hover:text-ink"}`}>
              {n}
            </button>
          ))}
        </span>
        <span>{y === 1 ? "year" : "years"} <span className="max-sm:hidden">of experience</span></span>
      </h1>
      <p className="mt-2.5 text-body text-muted">
        {y === null ? "Pick your years to see only the jobs you can apply for."
          : y === 0 ? "Showing jobs for freshers, and jobs that don't state any years."
          : `Showing jobs that ask for ${y} ${y === 1 ? "year" : "years"} or fewer, and jobs that don't state any.`}
      </p>
    </div>
  );
}
