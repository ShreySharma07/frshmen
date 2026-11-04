// Insights from what the person has done (docs/decisions.md, 2026-11-04): applications per week
// against their goal, and a timeline of saves, applications, stage changes, fit checks and
// tailored resumes. Plain counting over their own rows.
import { STAGES, type FitCheck, type TailoredRow, type Tracked } from "./tracker";

const DAY = 86_400_000;

/** Monday 00:00 (local) of the week holding `t`. */
export function weekStart(t: number): number {
  const d = new Date(t);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d.getTime();
}

/** Applications sent in each of the last `weeks` weeks, oldest first (this week last). */
export function weeklyApplications(tracked: Tracked[], weeks = 8, now = Date.now()): { week: number; n: number }[] {
  const current = weekStart(now);
  const out = Array.from({ length: weeks }, (_, i) => ({ week: current - (weeks - 1 - i) * 7 * DAY, n: 0 }));
  for (const t of tracked) {
    if (!t.applied_at) continue;
    const w = weekStart(Date.parse(t.applied_at));
    const slot = out.find((o) => o.week === w);
    if (slot) slot.n++;
  }
  return out;
}

export interface Event { at: string; kind: "saved" | "applied" | "moved" | "fit" | "tailored"; title: string; detail: string }

const label = (s: string) => STAGES.find((x) => x.v === s)?.label ?? s;

export function timeline(tracked: Tracked[], checks: FitCheck[], tailored: TailoredRow[]): Event[] {
  const job = (j: Tracked["jobs"]) => `${j?.companies?.name ?? ""} · ${j?.title ?? ""}`;
  const events: Event[] = [];
  for (const t of tracked) {
    events.push({ at: t.created_at, kind: "saved", title: job(t.jobs), detail: "Saved" });
    if (t.applied_at) events.push({ at: t.applied_at, kind: "applied", title: job(t.jobs), detail: "Applied" });
    // A later stage shows when it was last moved (the tracker keeps only the latest move).
    if (!["saved", "applied"].includes(t.status)) events.push({ at: t.updated_at, kind: "moved", title: job(t.jobs), detail: `Moved to ${label(t.status)}` });
  }
  for (const c of checks) events.push({ at: c.created_at, kind: "fit", title: job(c.jobs), detail: `Fit check: ${c.result.fit}` });
  for (const r of tailored) events.push({ at: r.created_at, kind: "tailored", title: job(r.jobs), detail: "Tailored resume" });
  return events.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}
