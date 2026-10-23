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
  /** The posting's pay range as written ("$120,000—$150,000 USD", "12-18 LPA"), when it states one. */
  salary: string | null;
}

export interface Evidence {
  kind: string;
  snippet: string;
}

export interface JobDetail extends JobSummary {
  source: string;
  department: string | null;
  employment_type: string | null;
  description_text: string;
  role_match: boolean;
  role_reason: string | null;
  evidence: { level: Evidence[]; role: Evidence[] } | null;
}

export interface JobPage {
  jobs: JobSummary[];
  page: number;
  per_page: number;
  has_more: boolean;
  total?: number; // only when asked for: counting reads every matching row
}

// Filter counts and lists come from a snapshot the pipeline writes once per run.
export interface Meta {
  total: number;
  levels: Record<Level, number>;
  internships: number;
  visa_or_relocation?: number; // in snapshots written since 2026-10-23
  within_years?: Record<"0" | "1" | "2" | "3" | "4" | "5", number>; // jobs open to someone with N years
  roles: Partial<Record<Role, number>>;
  companies: { company: string; n: number }[]; // companies with open jobs
  countries: { country: string; n: number }[];
  cities: { city: string; n: number }[];
  snapshot_at: string | null;
  last_run: { finished_at: string; companies_ok: number; jobs_new: number } | null;
}

export const PER_PAGE = 20;

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    // FastAPI puts the reason in `detail` (or `error` from our handler); fall back to the status line.
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? body?.error ?? `${res.status} ${res.statusText}`.trim());
  }
  return res.json();
}

export const fetchJob = (id: string, signal?: AbortSignal) =>
  getJson<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`, signal);

export const fetchMeta = (signal?: AbortSignal) => getJson<Meta>("/api/meta", signal);

/** One posting's deciding line, as the landing page's wall shows it. */
export interface EvidenceLine {
  id?: string;
  company: string;
  title: string;
  level: Level;
  yoe_min: number | null;
  yoe_max: number | null;
  text: string;
}

export const fetchEvidence = (limit: number, signal?: AbortSignal) =>
  getJson<{ lines: EvidenceLine[] }>(`/api/evidence?limit=${limit}`, signal);

export async function fetchJobs(filters: Record<string, string>, page: number, withTotal: boolean, signal?: AbortSignal): Promise<JobPage> {
  const params = new URLSearchParams({ ...filters, page: String(page), per_page: String(PER_PAGE) });
  if (withTotal) params.set("with_total", "true");
  return getJson<JobPage>(`/api/jobs?${params}`, signal);
}
