// Typed client for the FastAPI backend (api/src/jobs_api.py). Same origin in production; in
// development next.config.ts forwards /api to the local API.

export type Level = "fresher" | "maybe" | "experienced";
export type Experience = "all" | "fresher" | "internship" | "0-1" | "0-2" | "0-3" | "0-5" | "unstated" | "experienced";
export type Role = "all" | "target" | "ai_ml" | "backend" | "mobile";

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
  yoe_min: number | null;
  yoe_max: number | null;
  yoe_evidence: string | null;
  batch_years: number[];
  role_family: "ai_ml" | "backend" | "generic_swe" | "mobile" | null;
  visa_sponsorship: "yes" | "no" | "unknown";
  highlight: { kind: string; text: string } | null;
}

export interface JobPage {
  jobs: JobSummary[];
  page: number;
  per_page: number;
  has_more: boolean;
  total?: number; // only when asked for: counting reads every matching row
}

export interface JobQuery {
  experience: Experience;
  role: Role;
  page: number;
  withTotal: boolean;
}

export const PER_PAGE = 20;

export async function fetchJobs(q: JobQuery, signal?: AbortSignal): Promise<JobPage> {
  const params = new URLSearchParams({ experience: q.experience, role: q.role, page: String(q.page), per_page: String(PER_PAGE) });
  if (q.withTotal) params.set("with_total", "true");
  const res = await fetch(`/api/jobs?${params}`, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    // FastAPI puts the reason in `detail` (or `error` from our handler); fall back to the status line.
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? body?.error ?? `${res.status} ${res.statusText}`.trim());
  }
  return res.json();
}
