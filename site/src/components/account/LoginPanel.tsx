"use client";
// Sign-in: Google, or a one-time link by email (docs/decisions.md, 2026-10-30). Both land on
// /profile, where supabase-js swaps the link's code for a session.
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authConfigured, supabase } from "@/lib/supabase";
import { AccountShell, NotSetUp } from "./AccountShell";

type State = { kind: "idle" } | { kind: "busy"; via: "google" | "email" } | { kind: "sent"; email: string } | { kind: "error"; message: string };

const landing = () => `${location.origin}/profile`;

export function LoginPanel() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  // Already signed in: nothing to do here.
  useEffect(() => {
    if (!authConfigured) return;
    supabase().auth.getSession().then(({ data }) => { if (data.session) router.replace("/profile"); });
  }, [router]);

  if (!authConfigured) return <AccountShell><NotSetUp /></AccountShell>;

  async function google() {
    setState({ kind: "busy", via: "google" });
    const { error } = await supabase().auth.signInWithOAuth({ provider: "google", options: { redirectTo: landing() } });
    // On success the browser is already leaving for Google.
    if (error) setState({ kind: "error", message: error.message });
  }

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    const address = email.trim();
    setState({ kind: "busy", via: "email" });
    const { error } = await supabase().auth.signInWithOtp({ email: address, options: { emailRedirectTo: landing() } });
    setState(error ? { kind: "error", message: error.message } : { kind: "sent", email: address });
  }

  const busy = state.kind === "busy";
  return (
    <AccountShell>
      <h1 className="text-title font-medium">Sign in</h1>
      <p className="mt-2 text-body text-muted">Your profile keeps your years, roles and resume in one place, so Kario can check each job against you.</p>

      <button type="button" onClick={google} disabled={busy}
        className="mt-8 flex h-11 w-full items-center justify-center rounded-md border border-line bg-canvas text-base font-medium shadow-raised transition-colors duration-quick hover:bg-surface disabled:opacity-60">
        {state.kind === "busy" && state.via === "google" ? "Opening Google…" : "Continue with Google"}
      </button>

      <div className="my-6 flex items-center gap-3 text-meta text-muted" aria-hidden>
        <span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" />
      </div>

      {state.kind === "sent" ? (
        <div role="status" className="rounded-lg border border-line bg-surface p-4 text-body">
          <p className="font-medium">Check your inbox.</p>
          <p className="mt-1 text-muted">We sent a sign-in link to <span className="text-ink">{state.email}</span>. It works once, for one hour.</p>
          <button type="button" onClick={() => setState({ kind: "idle" })} className="mt-3 text-meta font-medium text-accent underline">Use a different email</button>
        </div>
      ) : (
        <form onSubmit={sendLink} className="space-y-3">
          <label className="block">
            <span className="text-meta text-muted">Email</span>
            <input type="email" required autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="mt-1 h-11 w-full rounded-md border border-line bg-canvas px-3 text-base outline-none transition-colors duration-quick placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/30" />
          </label>
          <button type="submit" disabled={busy}
            className="h-11 w-full rounded-md bg-accent text-base font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover disabled:opacity-60">
            {state.kind === "busy" && state.via === "email" ? "Sending…" : "Email me a sign-in link"}
          </button>
        </form>
      )}

      {state.kind === "error" && <p role="alert" className="mt-4 text-body text-muted">Couldn&apos;t sign in: {state.message}</p>}
    </AccountShell>
  );
}
