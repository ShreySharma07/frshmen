// Typed client for the FastAPI backend. Same origin in production; Vite proxies /api in dev.

export type Level = "fresher" | "maybe" | "experienced";
export type View = "fresher" | "maybe" | "new";

export interface Highlight {
  kind: string;
  text: string;
}

export interface JobSummary {
  id: string;
  company: string;
  title: string;
  url: string;
  location_raw: string | null;
  location_type: "remote" | "hybrid" | "onsite" | null;
  countries: string[];
  cities: string[];
  posted_at: string | null;
  first_seen_at: string;
  level: Level;
  level_confidence: number;
  level_reason: string;
  yoe_min: number | null;
  yoe_max: number | null;
  batch_years: number[];
  role_family: "ai_ml" | "backend" | "generic_swe" | "mobile" | null;
  visa_sponsorship: "yes" | "no" | "unknown";
  eligible: boolean;
  highlight: Highlight | null;
}

export interface Evidence {
  kind: string;
  snippet: string;
}

export interface JobDetail extends JobSummary {
  description_text: string;
  role_reason: string;
  evidence: { level: Evidence[]; role: Evidence[] };
}

export interface JobPage {
  jobs: JobSummary[];
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface Meta {
  counts: Record<Level | "new", number>;
  companies: { company: string; n: number }[];
  countries: { country: string; n: number }[];
  cities: { city: string; n: number }[];
  families: Record<Family, number>;
  last_run: { finished_at: string; companies_ok: number; companies_failed: number } | null;
}

export type Family = "ai_ml" | "backend" | "mobile";

export interface Filters {
  view: View;
  q: string;
  company: string;
  country: string;
  city: string;
  family: "" | Family;
  includeIneligible: boolean;
  location: "" | "remote" | "hybrid" | "onsite";
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`.trim());
  }
  return res.json() as Promise<T>;
}

export function fetchJobs(filters: Filters, offset: number, signal?: AbortSignal): Promise<JobPage> {
  const params = new URLSearchParams({ view: filters.view, limit: "40", offset: String(offset) });
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.company) params.set("company", filters.company);
  if (filters.country) params.set("country", filters.country);
  if (filters.city) params.set("city", filters.city);
  if (filters.family) params.set("family", filters.family);
  if (filters.includeIneligible) params.set("include_ineligible", "true");
  if (filters.location) params.set("location_type", filters.location);
  return get<JobPage>(`/api/jobs?${params}`, signal);
}

export const fetchJob = (id: string, signal?: AbortSignal) =>
  get<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`, signal);

export const fetchMeta = (signal?: AbortSignal) => get<Meta>("/api/meta", signal);
