// Typed client for the FastAPI backend. Same origin in production; Vite proxies /api in dev.

export type Level = "fresher" | "maybe" | "experienced";
export type Experience = "all" | "fresher" | "internship" | "0-1" | "0-2" | "0-3" | "0-5" | "unstated" | "experienced";
export type Posted = "any" | "24h" | "7d" | "30d";
export type Family = "ai_ml" | "backend" | "mobile";
export type Role = "all" | "target" | Family;

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
  role_match: boolean;
  role_reason: string;
  evidence: { level: Evidence[]; role: Evidence[] };
}

export interface JobPage {
  jobs: JobSummary[];
  page: number;
  per_page: number;
  has_more: boolean;
  // Only when asked for (with_total): counting reads every matching row.
  total?: number;
  pages?: number;
}

// Filter lists come from a snapshot the pipeline writes once per run (snapshot_at).
export interface Meta {
  total: number;
  levels: Record<Level, number>;
  internships: number;
  roles: Record<"target" | Family, number>;
  companies: { company: string; n: number }[];
  countries: { country: string; n: number }[];
  cities: { city: string; n: number }[];
  snapshot_at: string | null;
  last_run: { finished_at: string; companies_ok: number; companies_failed: number } | null;
  fit_check: boolean;
}

export interface Filters {
  experience: Experience;
  role: Role;
  posted: Posted;
  q: string;
  company: string;
  country: string;
  city: string;
  eligibleOnly: boolean;
  location: "" | "remote" | "hybrid" | "onsite";
}

export interface FitResult {
  fit: "strong" | "partial" | "weak";
  score: number | null;
  matched: string[];
  missing: string[];
  experience: string;
  advice: string;
  model: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { ...init, headers: { Accept: "application/json", ...init.headers } });
  if (!res.ok) {
    // FastAPI puts the reason in `detail`; fall back to the status line.
    const detail = await res.json().then((b) => (typeof b?.detail === "string" ? b.detail : ""), () => "");
    throw new Error(detail || `${res.status} ${res.statusText}`.trim());
  }
  return res.json() as Promise<T>;
}

const get = <T,>(path: string, signal?: AbortSignal) => request<T>(path, { signal });

export const PER_PAGE = 20;

export function fetchJobs(filters: Filters, page: number, withTotal: boolean, signal?: AbortSignal): Promise<JobPage> {
  const params = new URLSearchParams({ experience: filters.experience, role: filters.role, posted: filters.posted,
                                       page: String(page), per_page: String(PER_PAGE) });
  if (withTotal) params.set("with_total", "true");
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.company) params.set("company", filters.company);
  if (filters.country) params.set("country", filters.country);
  if (filters.city) params.set("city", filters.city);
  if (filters.eligibleOnly) params.set("eligible_only", "true");
  if (filters.location) params.set("location_type", filters.location);
  return get<JobPage>(`/api/jobs?${params}`, signal);
}

export const checkFit = (id: string, resume: string) =>
  request<FitResult>(`/api/jobs/${encodeURIComponent(id)}/fit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume }),
  });

export const fetchJob = (id: string, signal?: AbortSignal) =>
  get<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`, signal);

export const fetchMeta = (signal?: AbortSignal) => get<Meta>("/api/meta", signal);
