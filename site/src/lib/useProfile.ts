"use client";
// The signed-in person and their profile, for the board and Insights. Also where sign-in lands:
// getSession swaps a sign-in link's ?code= for a session. No session -> /login; no profile yet ->
// /profile/edit, since there's nothing to show without one.
import type { User } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { sessionChanged } from "./session";
import { authConfigured, PROFILE_COLUMNS, supabase, type Profile } from "./supabase";

export type ProfileLoad = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; user: User; profile: Profile };

export function useProfile(): ProfileLoad {
  const router = useRouter();
  const [load, setLoad] = useState<ProfileLoad>({ kind: "loading" });
  useEffect(() => {
    if (!authConfigured) return;
    const sb = supabase();
    let cancelled = false;
    sb.auth.getSession().then(async ({ data, error }) => {
      if (cancelled) return;
      if (error) return setLoad({ kind: "error", message: `${error.message}. The link may have expired; sign in again.` });
      const user = data.session?.user;
      if (!user) return router.replace("/login");
      sessionChanged(); // the header reads the session supabase-js just stored
      if (location.search.includes("code=")) history.replaceState(null, "", location.pathname);
      const row = await sb.from("students").select(PROFILE_COLUMNS).eq("id", user.id).maybeSingle<Profile>();
      if (cancelled) return;
      if (row.error) return setLoad({ kind: "error", message: row.error.message });
      if (!row.data) return router.replace("/profile/edit");
      setLoad({ kind: "ready", user, profile: { ...row.data, yoe: Number(row.data.yoe) } });
    });
    return () => { cancelled = true; };
  }, [router]);
  return load;
}
