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

export const QUIET_DAYS = 30; // applied this long ago with no move: off the board, kept in the list
export const STALE_SAVE_DAYS = 14;

export interface Step { text: string; due: boolean; quiet: boolean }

/** What an application needs next, from its stage and dates alone. `due` means it needs the
 *  person this week; `quiet` means it has gone long enough without news to leave the board. */
export function nextStep(t: Tracked, now = Date.now()): Step {
  const step = (text: string, due = false, quiet = false): Step => ({ text, due, quiet });
  if (t.status === "interview") return step("Interviewing: prepare", true);
  if (t.status === "offer") return step("Offer: reply", true);
  if (t.status === "rejected") return step("Closed");
  if (t.status === "applied") {
    const d = daysAgo(t.applied_at ?? t.updated_at, now);
    if (d >= QUIET_DAYS) return step(`No reply in ${d} days`, false, true);
    if (d >= FOLLOW_UP_DAYS) return step(`Follow up: applied ${d} days ago`, true);
    return step(d === 0 ? "Applied today" : `Applied ${d} ${d === 1 ? "day" : "days"} ago`);
  }
  const d = daysAgo(t.created_at, now);
  return d >= STALE_SAVE_DAYS ? step(`Saved ${d} days ago: apply or drop`, true) : step("Not applied yet");
}
