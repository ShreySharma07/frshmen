// Supabase Auth and the profile's data (docs/decisions.md, 2026-10-30). The browser talks to
// Supabase directly; RLS in db/postgres/0004_profiles.sql decides what it may touch.
// Imported only by /login and /profile, so the job list's bundle never carries supabase-js.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Role } from "./api";

// Both are public by design (the publishable key only reaches what RLS allows). Set at build
// time from the repo's Actions variables in .github/workflows/deploy.yml.
const URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
export const authConfigured = Boolean(URL && KEY);

let client: SupabaseClient | null = null;
export function supabase(): SupabaseClient {
  // PKCE: the sign-in link carries a one-time code, swapped for a session on the page it lands on.
  client ??= createClient(URL, KEY, { auth: { flowType: "pkce", persistSession: true, detectSessionInUrl: true } });
  return client;
}

/** The one resume path the storage policies allow for this person. */
export const resumePath = (uid: string) => `${uid}/resume.pdf`;
export const RESUME_BUCKET = "resumes";
export const RESUME_MAX_BYTES = 5 * 1024 * 1024; // the bucket's limit
export const RESUME_TEXT_MAX = 60_000; // students.resume_text's limit

export type ProfileRole = Exclude<Role, "all" | "target">;

/** A row of `students`, as this person may read and write it. */
export interface Profile {
  name: string;
  yoe: number;
  grad_year: number | null;
  target_roles: ProfileRole[];
  resume_path: string | null;
  resume_name: string | null;
  resume_text: string | null;
}

export const PROFILE_COLUMNS = "name, yoe, grad_year, target_roles, resume_path, resume_name, resume_text";
