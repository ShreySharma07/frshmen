// The tracker (applications) and fit checks, read and written through Supabase's Data API as the
// signed-in person (lib/session.ts). RLS limits every call to their own rows
// (db/postgres/0005_tracker_fit_checks.sql).
import { freshToken, rest } from "./session";

export type Stage = "saved" | "applied" | "interview" | "offer" | "rejected";
export const STAGES: { v: Stage; label: string }[] = [
  { v: "saved", label: "Saved" }, { v: "applied", label: "Applied" }, { v: "interview", label: "Interview" },
  { v: "offer", label: "Offer" }, { v: "rejected", label: "Rejected" },
];

export interface Tracked {
  id: number;
  job_id: string;
  status: Stage;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
  jobs: { title: string; url: string; companies: { name: string } | null } | null;
}

async function ok(res: Response): Promise<Response> {
  if (res.ok) return res;
  const body = await res.json().catch(() => null);
  const err = new Error(body?.message ?? `${res.status} ${res.statusText}`) as Error & { code?: string };
  err.code = body?.code;
  throw err;
}

export async function trackedJobs(): Promise<Tracked[]> {
  const res = await rest("applications?select=id,job_id,status,applied_at,created_at,updated_at,jobs(title,url,companies(name))&order=updated_at.desc");
  return (await ok(res)).json();
}

export async function stageOf(jobId: string): Promise<Stage | null> {
  const res = await rest(`applications?select=status&job_id=eq.${encodeURIComponent(jobId)}`);
  const rows: { status: Stage }[] = await (await ok(res)).json();
  return rows[0]?.status ?? null;
}

/** Adds the job as "saved". "no-profile" when the person hasn't saved a profile yet (the row needs one). */
export async function saveJob(userId: string, jobId: string): Promise<"saved" | "no-profile"> {
  const res = await rest("applications", { method: "POST", body: JSON.stringify({ student_id: userId, job_id: jobId }) });
  if (res.ok) return "saved";
  const body = await res.json().catch(() => null);
  if (body?.code === "23505") return "saved"; // already tracked
  if (body?.code === "23503") return "no-profile";
  throw new Error(body?.message ?? `${res.status}`);
}

export async function moveJob(id: number, status: Stage) {
  await ok(await rest(`applications?id=eq.${id}`, { method: "PATCH", body: JSON.stringify({ status }) }));
}

export async function removeJob(id: number) {
  await ok(await rest(`applications?id=eq.${id}`, { method: "DELETE" }));
}

// --- Fit checks (Gemini, through our API: it counts them and keeps the verdict) ----------------

export interface Verdict {
  fit: "strong" | "partial" | "weak";
  score: number | null;
  matched: string[];
  missing: string[];
  experience: string;
  advice: string;
}
export interface FitCheck { id: number; job_id: string; result: Verdict; created_at: string; jobs: Tracked["jobs"] }
export interface Allowance { limit: number; used: number; remaining: number; frees_at: string | null }
export interface Quota extends Allowance { enabled: boolean; tailor: Allowance }

export async function recentChecks(limit = 5): Promise<FitCheck[]> {
  // Checks still waiting for Gemini hold {"pending": true}; only finished verdicts are listed.
  const res = await rest(`fit_checks?select=id,job_id,result,created_at,jobs(title,url,companies(name))&result->>fit=not.is.null&order=created_at.desc&limit=${limit}`);
  return (await ok(res)).json();
}

async function api(path: string, init: RequestInit = {}) {
  const token = await freshToken();
  if (!token) throw Object.assign(new Error("sign in again"), { status: 401 });
  const res = await fetch(path, { ...init, headers: { Authorization: `Bearer ${token}`, Accept: "application/json" } });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw Object.assign(new Error(typeof detail === "string" ? detail : detail?.message ?? `${res.status}`),
      { status: res.status, freesAt: detail?.frees_at as string | undefined });
  }
  return body;
}

export const fitQuota = (): Promise<Quota> => api("/api/fit/quota");
export const checkFit = (jobId: string): Promise<Verdict & { remaining: number }> =>
  api(`/api/jobs/${encodeURIComponent(jobId)}/fit`, { method: "POST" });

// --- Tailored resumes (2 a day; api/src/tailor.py holds each line to the saved resume) --------

export interface TailoredLine { text: string; original: string; sources: number[]; kept_original: boolean; reason: string | null }
export interface TailoredSection { heading: string; lines: TailoredLine[] }
export interface Tailored {
  name: string;
  note: string;
  sections: TailoredSection[];
  left_out: string[];
  kept_original: number;
  dropped: number;
}
export interface TailoredRow { id: number; job_id: string; result: Tailored; created_at: string; jobs: Tracked["jobs"] }

export const tailorResume = (jobId: string): Promise<Tailored & { id: number; remaining: number }> =>
  api(`/api/jobs/${encodeURIComponent(jobId)}/tailor`, { method: "POST" });

export async function recentTailored(limit = 5): Promise<TailoredRow[]> {
  const res = await rest(`tailored_resumes?select=id,job_id,result,created_at,jobs(title,url,companies(name))&result->sections=not.is.null&order=created_at.desc&limit=${limit}`);
  return (await ok(res)).json();
}
