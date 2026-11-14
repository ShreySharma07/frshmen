// /admin's data (api/src/admin.py). Admins only: anyone else gets 403 from the API.
import type { Band } from "./api";
import { api } from "./tracker";

export interface Run {
  finished_at: string;
  companies_ok: number;
  companies_failed: number;
  jobs_seen: number;
  jobs_new: number;
  jobs_changed: number;
  jobs_closed: number;
  error_count: number;
}

export interface Overview {
  jobs: { open: number; new_24h: number; bands: Record<Band, number>; by_source: { source: string; n: number }[]; by_category: Record<string, number> };
  pipeline: { runs: Run[]; latest_errors: Record<string, string> };
  users: { total: number; signups: { day: string; n: number }[]; usage_24h: { fit_checks: number; tailored_resumes: number } };
}

export interface ManualJob {
  id: number;
  company: string;
  title: string;
  url: string;
  location_raw: string;
  posted_at: string | null;
  added_at: string;
  closed_at: string | null;
  status: "open" | "closed";
}

export type NewJob = Pick<ManualJob, "company" | "title" | "url" | "location_raw"> & { description_text: string };

export const adminOverview = (): Promise<Overview> => api("/api/admin/overview");
export const manualJobs = (): Promise<{ jobs: ManualJob[] }> => api("/api/admin/jobs");
export const addJob = (job: NewJob): Promise<ManualJob> => api("/api/admin/jobs", { method: "POST", body: JSON.stringify(job) });
export const closeJob = (id: number): Promise<ManualJob> => api(`/api/admin/jobs/${id}/close`, { method: "POST" });
