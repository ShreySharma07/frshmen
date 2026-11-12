"use client";
// /profile: where a sign-in link lands. useProfile swaps the link's code for a session (and sends
// a person with no profile to /profile/edit); once that is done, on to the tracker.
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AccountShell, NotSetUp } from "@/components/account/AccountShell";
import { authConfigured } from "@/lib/supabase";
import { useProfile } from "@/lib/useProfile";

export function ToApplications() {
  const load = useProfile();
  const router = useRouter();
  useEffect(() => { if (load.kind === "ready") router.replace("/applications"); }, [load.kind, router]);
  if (!authConfigured) return <AccountShell><NotSetUp /></AccountShell>;
  return (
    <AccountShell title="Applications">
      {load.kind === "error"
        ? <p role="alert" className="text-body text-muted">Couldn&apos;t sign you in: {load.message}</p>
        : <p aria-busy="true" className="text-body text-muted">Signing you in…</p>}
    </AccountShell>
  );
}
