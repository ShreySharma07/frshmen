// The signed-in person, read straight from what supabase-js stored, so pages like the job list
// can show the profile button and call the API without loading supabase-js (~45 KB). Refreshing
// an expired token, and signing out, load it on demand.
const URL_ = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
// supabase-js's default storage key: sb-<project ref>-auth-token.
const STORAGE_KEY = (() => { try { return `sb-${new URL(URL_).hostname.split(".")[0]}-auth-token`; } catch { return ""; } })();
const EVENT = "aventra:session";

export interface Session {
  userId: string;
  email: string;
  name: string;
  accessToken: string;
  expiresAt: number; // seconds since the epoch
}

let cached: { raw: string | null; session: Session | null } = { raw: null, session: null };

export function readSession(): Session | null {
  if (!STORAGE_KEY) return null;
  let raw: string | null = null;
  try { raw = localStorage.getItem(STORAGE_KEY); } catch { return null; }
  // Same object while the stored text is the same, so useSyncExternalStore doesn't loop.
  if (raw === cached.raw) return cached.session;
  let session: Session | null = null;
  try {
    const s = raw ? JSON.parse(raw) : null;
    if (s?.access_token && s.user?.id) {
      const meta = s.user.user_metadata ?? {};
      session = { userId: s.user.id, email: s.user.email ?? "", name: String(meta.full_name ?? meta.name ?? ""),
        accessToken: s.access_token, expiresAt: Number(s.expires_at ?? 0) };
    }
  } catch { /* unreadable: treat as signed out */ }
  cached = { raw, session };
  return session;
}

export function subscribeSession(onChange: () => void) {
  // "storage" covers other tabs; EVENT covers sign-in and sign-out in this one.
  addEventListener("storage", onChange);
  addEventListener(EVENT, onChange);
  return () => { removeEventListener("storage", onChange); removeEventListener(EVENT, onChange); };
}

export const sessionChanged = () => dispatchEvent(new Event(EVENT));

/** A token the API and Supabase will accept: the stored one, or a refreshed one when it's about to expire. */
export async function freshToken(): Promise<string | null> {
  const s = readSession();
  if (!s) return null;
  if (s.expiresAt * 1000 > Date.now() + 60_000) return s.accessToken;
  const { supabase } = await import("./supabase");
  const { data } = await supabase().auth.getSession(); // refreshes and stores the new token
  sessionChanged();
  return data.session?.access_token ?? null;
}

export async function signOut() {
  const { supabase } = await import("./supabase");
  await supabase().auth.signOut();
  sessionChanged();
}

/** Supabase's Data API (PostgREST) as the signed-in person; RLS decides what they reach. */
export async function rest(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await freshToken();
  if (!token) throw new Error("sign in again");
  return fetch(`${URL_}/rest/v1/${path}`, {
    ...init,
    headers: { apikey: KEY, Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
}
