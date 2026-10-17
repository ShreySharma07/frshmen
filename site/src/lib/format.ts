import type { JobSummary } from "./api";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "3+", "3–6", "0", or null when the posting states no years. */
export function years(j: JobSummary): string | null {
  if (j.yoe_min == null) return j.level === "fresher" ? "0" : null;
  if (j.yoe_max != null && j.yoe_max !== j.yoe_min) return `${j.yoe_min}–${j.yoe_max}`;
  return j.yoe_min === 0 ? "0" : `${j.yoe_min}+`;
}

/** "25 Sep"; adds the year when it isn't the current one. */
export function shortDate(iso: string | null, now = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  const s = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  return d.getUTCFullYear() === now.getUTCFullYear() ? s : `${s} ${d.getUTCFullYear()}`;
}

/** "Bengaluru · Onsite", "Remote", or the raw location. */
export function place(j: JobSummary): string {
  const where = j.cities[0] ?? j.location_raw ?? j.countries[0] ?? "";
  const mode = j.location_type ? j.location_type[0].toUpperCase() + j.location_type.slice(1) : "";
  return [where, mode].filter(Boolean).join(" · ");
}
