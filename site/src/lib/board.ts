// The board's rules (docs/decisions.md, 2026-11-04), kept apart from the components so they read
// as rules: what makes a strong match, when a follow-up is due, what the brief says.
import type { JobSummary } from "./api";
import type { Tracked } from "./tracker";

const DAY = 86_400_000;
export const FOLLOW_UP_DAYS = 7;

/** New, fits the profile (the caller's filters), and the resume has at least half of the skills the
 *  posting names. A posting that names none can't be judged, so it isn't "strong". */
export function isStrongMatch(job: JobSummary, have: Set<string>): boolean {
  const asked = job.skills ?? [];
  if (!asked.length) return false;
  return asked.filter((s) => have.has(s)).length >= Math.ceil(asked.length / 2);
}

/** Jobs sitting in Applied for FOLLOW_UP_DAYS or more. */
export function followUpsDue(tracked: Tracked[], now = Date.now()): Tracked[] {
  return tracked.filter((t) => t.status === "applied" && t.applied_at && now - Date.parse(t.applied_at) >= FOLLOW_UP_DAYS * DAY);
}

export function daysAgo(iso: string, now = Date.now()): number {
  return Math.max(0, Math.floor((now - Date.parse(iso)) / DAY));
}

/** The one-sentence brief at the top of the board. */
export function brief(strong: number, followUps: number): string {
  const parts = [
    strong ? `${strong} new strong ${strong === 1 ? "match" : "matches"}` : "No new strong matches today",
    followUps ? `${followUps} follow-up${followUps === 1 ? "" : "s"} due` : null,
  ].filter(Boolean);
  return parts.join(", ") + ".";
}

/** The skills most asked for in your matching jobs that your resume doesn't name. */
export function missingSkills(demand: { skill: string; n: number }[], have: Set<string>, count = 5) {
  return demand.filter((d) => !have.has(d.skill)).slice(0, count);
}
