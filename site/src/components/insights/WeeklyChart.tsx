// Applications per week (bars) against the weekly goal (a dashed line). Plain HTML and the site's
// tokens rather than an SVG, so labels keep their real size on a phone; every bar carries its
// number, so nothing hides in colour alone.
export function WeeklyChart({ weeks, goal }: { weeks: { week: number; n: number }[]; goal: number }) {
  const max = Math.max(goal, ...weeks.map((w) => w.n), 1);
  const pct = (v: number) => `${(v / max) * 100}%`;
  // Day numbers under the bars, with the month written below where it changes: short enough for
  // eight weeks side by side on a phone.
  const month = new Intl.DateTimeFormat("en-IN", { month: "short" });
  const newMonth = (i: number) => i === 0 || new Date(weeks[i].week).getMonth() !== new Date(weeks[i - 1].week).getMonth();
  const met = weeks.filter((w) => w.n >= goal).length;
  return (
    <figure>
      <div role="img" className="relative ml-6 h-40 border-b border-line"
        aria-label={`Applications per week for the last ${weeks.length} weeks: ${weeks.map((w) => w.n).join(", ")}. Goal ${goal} a week, met in ${met}.`}>
        {/* The goal line, labelled on the left. */}
        <div aria-hidden className="absolute inset-x-0 border-t border-dashed border-ink/50" style={{ bottom: pct(goal) }}>
          <span className="absolute -left-6 -top-2 w-5 text-right font-mono text-caption text-muted">{goal}</span>
        </div>
        <div aria-hidden className="absolute inset-0 flex items-end gap-[6%] px-[3%]">
          {weeks.map((w) => (
            <div key={w.week} className="relative flex h-full flex-1 flex-col justify-end">
              <span className="mb-1 text-center font-mono text-caption">{w.n}</span>
              <div className={`rounded-t-sm ${w.n >= goal ? "bg-accent" : "bg-accent/40"}`} style={{ height: pct(w.n) }} />
            </div>
          ))}
        </div>
      </div>
      <div aria-hidden className="ml-6 mt-1.5 flex gap-[6%] px-[3%]">
        {weeks.map((w, i) => (
          <span key={w.week} className="min-w-0 flex-1 whitespace-nowrap text-center text-caption text-muted">
            {i === weeks.length - 1 ? "Now" : new Date(w.week).getDate()}
            <span className="block h-4">{i < weeks.length - 1 && newMonth(i) ? month.format(w.week) : ""}</span>
          </span>
        ))}
      </div>
      <figcaption className="mt-3 text-meta text-muted">
        Bars are applications sent each week; the dashed line is your goal of {goal}. You met it in {met} of the last {weeks.length} weeks.
      </figcaption>
    </figure>
  );
}
