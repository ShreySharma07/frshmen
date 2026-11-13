// The list's filters, kept in the URL (?yrs=3&role=ai_ml&q=pytorch) so a filtered list can be
// shared and the browser's Back button undoes a filter change.
import type { Band, Role } from "./api";
import { CATEGORY } from "./describe";

export type Workplace = "any" | "remote" | "hybrid" | "onsite";
export type Posted = "any" | "24h" | "7d" | "30d";

export interface Filters {
  /** The person's years of experience; null = any. The list shows its band (bandOf). */
  years: number | null;
  role: Role;
  /** A general category (CATEGORY key) for anyone's roles; "" = use `role`. */
  category: string;
  country: string; // "" = anywhere
  workplace: Workplace;
  posted: Posted;
  q: string;
}

export const DEFAULTS: Filters = { years: null, role: "target", category: "", country: "", workplace: "any", posted: "any", q: "" };

/** The "I have" choices: one per band, each standing for a typical number of years (the ruler's tick). */
export const BAND_CHOICES: { band: Band; years: number; label: string }[] = [
  { band: "0-1", years: 0, label: "0–1 years (fresher)" },
  { band: "1-3", years: 2, label: "1–3 years" },
  { band: "3-5", years: 4, label: "3–5 years" },
  { band: "5-8", years: 6, label: "5–8 years" },
  { band: "8+", years: 8, label: "8+ years" },
];

/** Bands are on the minimum years a job asks (docs/decisions.md, 2026-11-13). */
export function bandOf(years: number): Band {
  return years < 1 ? "0-1" : years < 3 ? "1-3" : years < 5 ? "3-5" : years < 8 ? "5-8" : "8+";
}

const ROLES: Role[] = ["all", "target", "ai_ml", "backend", "mobile"];
const WORKPLACES: Workplace[] = ["any", "remote", "hybrid", "onsite"];
const POSTED: Posted[] = ["any", "24h", "7d", "30d"];
const pick = <T extends string>(value: string | null, allowed: T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

export function fromSearch(search: string): Filters {
  const p = new URLSearchParams(search);
  const y = p.get("yrs");
  const years = y !== null && /^\d{1,2}$/.test(y) ? Number(y) : null;
  const cat = p.get("cat") ?? "";
  return {
    years,
    role: pick(p.get("role"), ROLES, DEFAULTS.role),
    category: cat in CATEGORY ? cat : "",
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
  if (f.category) p.set("cat", f.category);
  else if (f.role !== DEFAULTS.role) p.set("role", f.role);
  if (f.country) p.set("country", f.country);
  if (f.workplace !== "any") p.set("work", f.workplace);
  if (f.posted !== "any") p.set("posted", f.posted);
  if (f.q.trim()) p.set("q", f.q.trim());
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** API parameters. A band also lists postings that state no years ("Not stated"). A category
 *  replaces the role scope: it covers every job, not just the profile's target roles. */
export function toApiParams(f: Filters): Record<string, string> {
  const out: Record<string, string> = { role: f.category ? "all" : f.role, posted: f.posted, experience: "all" };
  if (f.category) out.category = f.category;
  if (f.years !== null) { out.band = bandOf(f.years); out.include_unstated = "true"; }
  if (f.country) out.country = f.country;
  if (f.workplace !== "any") out.location_type = f.workplace;
  if (f.q.trim()) out.q = f.q.trim();
  return out;
}

export const isDefault = (f: Filters) => toSearch(f) === "";

/** The job list a saved profile points to: the band of its years and, when
 *  exactly one role is picked, that role; otherwise all three target roles. */
export function profileFilters(yoe: number, roles: string[]): Filters {
  const role = roles.length === 1 && ROLES.includes(roles[0] as Role) ? (roles[0] as Role) : "target";
  return { ...DEFAULTS, years: Math.max(Math.round(yoe), 0), role };
}

/** Set by /profile on save; the job list shows a one-time "Profile saved" note and clears it. */
export const SAVED_KEY = "aventra:profile-saved";
