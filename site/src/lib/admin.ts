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

// --- Contact lists (HR and YC founders; api/src/admin.py) ------------------------------------

export type ContactKind = "hr" | "founder";
export interface ContactList { kind: ContactKind; source: string; n: number; with_email: number; with_phone: number }
export interface ContactsSummary { total: number; reveals_7d: number; lists: ContactList[] }
export interface ImportReport {
  valid: number;
  added: number;
  updated: number;
  error_count: number;
  errors: { row: number; reason: string }[];
  sample: { name: string; company: string; title: string | null; email: string | null; phone: string | null }[];
}

export const contactsSummary = (): Promise<ContactsSummary> => api("/api/admin/contacts");
export const importContacts = (body: { kind: ContactKind; source: string; csv: string; dry_run: boolean }): Promise<ImportReport> =>
  api("/api/admin/contacts/import", { method: "POST", body: JSON.stringify(body) });
export const deleteContacts = (body: { email: string } | { source: string }): Promise<{ deleted: number }> =>
  api("/api/admin/contacts/delete", { method: "POST", body: JSON.stringify(body) });
