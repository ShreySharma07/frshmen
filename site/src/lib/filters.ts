// The list's filters, kept in the URL (?yrs=3&role=ai_ml&q=pytorch) so a filtered list can be
// shared and the browser's Back button undoes a filter change.
import type { Role } from "./api";

export type Workplace = "any" | "remote" | "hybrid" | "onsite";
export type Posted = "any" | "24h" | "7d" | "30d";

export interface Filters {
  /** Show jobs that ask for at most this many years; null = any. 5 means "≤ 5". */
  years: number | null;
  role: Role;
  country: string; // "" = anywhere
  workplace: Workplace;
  posted: Posted;
  q: string;
}

export const DEFAULTS: Filters = { years: null, role: "target", country: "", workplace: "any", posted: "any", q: "" };

const ROLES: Role[] = ["all", "target", "ai_ml", "backend", "mobile"];
const WORKPLACES: Workplace[] = ["any", "remote", "hybrid", "onsite"];
const POSTED: Posted[] = ["any", "24h", "7d", "30d"];
const pick = <T extends string>(value: string | null, allowed: T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

export function fromSearch(search: string): Filters {
  const p = new URLSearchParams(search);
  const y = p.get("yrs");
  const years = y !== null && /^[0-5]$/.test(y) ? Number(y) : null;
  return {
    years,
    role: pick(p.get("role"), ROLES, DEFAULTS.role),
    country: (p.get("country") ?? "").slice(0, 60),
    workplace: pick(p.get("work"), WORKPLACES, "any"),
    posted: pick(p.get("posted"), POSTED, "any"),
    q: (p.get("q") ?? "").slice(0, 100),
  };
}

/** Only non-default values, so a plain visit keeps a clean URL. */
export function toSearch(f: Filters): string {
  const p = new URLSearchParams();
  if (f.years !== null) p.set("yrs", String(f.years));
  if (f.role !== DEFAULTS.role) p.set("role", f.role);
  if (f.country) p.set("country", f.country);
  if (f.workplace !== "any") p.set("work", f.workplace);
  if (f.posted !== "any") p.set("posted", f.posted);
  if (f.q.trim()) p.set("q", f.q.trim());
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** API parameters. "≤ N years" also lists postings that state no years ("Not stated"). */
export function toApiParams(f: Filters): Record<string, string> {
  const out: Record<string, string> = { role: f.role, posted: f.posted };
  if (f.years === null) out.experience = "all";
  else { out.experience = `0-${f.years}`; out.include_unstated = "true"; }
  if (f.country) out.country = f.country;
  if (f.workplace !== "any") out.location_type = f.workplace;
  if (f.q.trim()) out.q = f.q.trim();
  return out;
}

export const isDefault = (f: Filters) => toSearch(f) === "";
