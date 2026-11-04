"use client";
// The profile (docs/decisions.md, 2026-10-30): name, years, graduation year, target roles and a
// resume. Reads and writes go straight to Supabase as the signed-in person; RLS limits them to
// their own row and their own <id>/resume.pdf (db/postgres/0004_profiles.sql).
import type { User } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { profileFilters, SAVED_KEY, toSearch } from "@/lib/filters";
import { resumeText } from "@/lib/resumeText";
import {
  authConfigured, PROFILE_COLUMNS, RESUME_BUCKET, RESUME_MAX_BYTES, RESUME_TEXT_MAX, resumePath, supabase,
  type Profile, type ProfileRole,
} from "@/lib/supabase";
import { AccountShell, NotSetUp } from "./AccountShell";

const YEARS = [{ v: 0, label: "0" }, { v: 1, label: "1" }, { v: 2, label: "2" }, { v: 3, label: "3+" }];
const ROLES: { v: ProfileRole; label: string }[] = [{ v: "ai_ml", label: "AI/ML" }, { v: "backend", label: "Backend" }, { v: "mobile", label: "Mobile" }];
const GRAD_YEARS = Array.from({ length: 13 }, (_, i) => 2018 + i);

type Load = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; user: User; exists: boolean };
type Save = { kind: "idle" } | { kind: "reading" } | { kind: "saving" } | { kind: "error"; message: string };

const blank = (user: User): Profile => ({
  // Google sign-ins carry the person's name; email sign-ins start empty.
  name: String(user.user_metadata?.full_name ?? user.user_metadata?.name ?? ""),
  yoe: 0, grad_year: null, target_roles: [], resume_path: null, resume_name: null, resume_text: null,
});

export function ProfileForm() {
  const router = useRouter();
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [form, setForm] = useState<Profile | null>(null);
  const [file, setFile] = useState<File | null>(null); // a new PDF, not uploaded yet
  const [save, setSave] = useState<Save>({ kind: "idle" });
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!authConfigured) return;
    const sb = supabase();
    let cancelled = false;
    // getSession waits for supabase-js to swap a sign-in link's ?code= for a session.
    sb.auth.getSession().then(async ({ data, error }) => {
      if (cancelled) return;
      if (error) return setLoad({ kind: "error", message: `${error.message}. The link may have expired; sign in again.` });
      const user = data.session?.user;
      if (!user) return router.replace("/login");
      if (location.search.includes("code=")) history.replaceState(null, "", "/profile");
      const row = await sb.from("students").select(PROFILE_COLUMNS).eq("id", user.id).maybeSingle<Profile>();
      if (cancelled) return;
      if (row.error) return setLoad({ kind: "error", message: row.error.message });
      setForm(row.data ? { ...row.data, yoe: Math.min(Number(row.data.yoe), 3) } : blank(user));
      setLoad({ kind: "ready", user, exists: Boolean(row.data) });
    });
    const { data: sub } = sb.auth.onAuthStateChange((event) => { if (event === "SIGNED_OUT") router.replace("/login"); });
    return () => { cancelled = true; sub.subscription.unsubscribe(); };
  }, [router]);

  if (!authConfigured) return <AccountShell><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell><p role="alert" className="text-body text-muted">Couldn&apos;t open your profile: {load.message}</p></AccountShell>;
  if (load.kind === "loading" || !form) return <AccountShell><FormSkeleton /></AccountShell>;

  const { user, exists } = load;
  const set = (patch: Partial<Profile>) => { setForm({ ...form, ...patch }); if (save.kind === "error") setSave({ kind: "idle" }); };
  const toggleRole = (r: ProfileRole) =>
    set({ target_roles: form.target_roles.includes(r) ? form.target_roles.filter((x) => x !== r) : [...form.target_roles, r] });

  async function pick(f: File | undefined) {
    if (!f) return;
    if (f.type !== "application/pdf") return setSave({ kind: "error", message: "Choose a PDF file." });
    if (f.size > RESUME_MAX_BYTES) return setSave({ kind: "error", message: "That PDF is over 5 MB." });
    setSave({ kind: "reading" });
    try {
      const text = await resumeText(f);
      setFile(f);
      setForm((prev) => prev && { ...prev, resume_name: f.name.slice(0, 200), resume_text: text });
      setSave(text ? { kind: "idle" } : { kind: "error", message: "No text found in that PDF (is it a scan?). Paste your resume's text below instead." });
    } catch {
      setSave({ kind: "error", message: "Couldn't read that PDF. Try exporting it again." });
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSave({ kind: "saving" });
    const sb = supabase();
    const path = resumePath(user.id);
    if (file) {
      const up = await sb.storage.from(RESUME_BUCKET).upload(path, file, { upsert: true, contentType: "application/pdf" });
      if (up.error) return setSave({ kind: "error", message: up.error.message });
    }
    const values = {
      name: form.name.trim(), yoe: form.yoe, grad_year: form.grad_year, target_roles: form.target_roles,
      resume_path: file ? path : form.resume_path, resume_name: form.resume_name,
      resume_text: form.resume_text?.trim() ? form.resume_text.slice(0, RESUME_TEXT_MAX) : null,
    };
    // Insert once, then update: an upsert would also try to write `id`, which only INSERT may set.
    const res = exists
      ? await sb.from("students").update(values).eq("id", user.id)
      : await sb.from("students").insert({ id: user.id, ...values });
    if (res.error) return setSave({ kind: "error", message: res.error.message });
    // Saved: on to the jobs this profile fits (docs/decisions.md, 2026-11-04).
    try { sessionStorage.setItem(SAVED_KEY, "1"); } catch {}
    router.push("/" + toSearch(profileFilters(values.yoe, values.target_roles)));
  }

  async function openResume() {
    if (!form?.resume_path) return;
    // A link that works for one minute; the bucket itself is private.
    const { data, error } = await supabase().storage.from(RESUME_BUCKET).createSignedUrl(form.resume_path, 60);
    if (error) return setSave({ kind: "error", message: error.message });
    window.open(data.signedUrl, "_blank", "noopener");
  }

  async function deleteEverything() {
    if (!confirm("Delete your profile and resume from Aventra? This can't be undone.")) return;
    const sb = supabase();
    setSave({ kind: "saving" });
    const files = await sb.storage.from(RESUME_BUCKET).remove([resumePath(user.id)]);
    const row = await sb.from("students").delete().eq("id", user.id);
    if (files.error || row.error) return setSave({ kind: "error", message: (files.error ?? row.error)!.message });
    await sb.auth.signOut();
    router.replace("/");
  }

  const busy = save.kind === "saving" || save.kind === "reading";
  const signOut = (
    <button type="button" onClick={() => supabase().auth.signOut()}
      className="h-8 rounded-md px-2.5 text-meta font-medium text-muted transition-colors duration-quick hover:bg-surface hover:text-ink">Sign out</button>
  );

  return (
    <AccountShell actions={signOut}>
      <h1 className="text-title font-medium">Your profile</h1>
      <p className="mt-2 text-body text-muted">Signed in as <span className="text-ink">{user.email}</span>. Only you can see this.</p>

      <form onSubmit={submit} className="mt-8 space-y-7">
        <Field label="Name" htmlFor="name">
          <input id="name" required maxLength={120} autoComplete="name" value={form.name} onChange={(e) => set({ name: e.target.value })}
            className="h-11 w-full rounded-md border border-line bg-canvas px-3 text-base outline-none transition-colors duration-quick focus:border-accent focus:ring-2 focus:ring-accent/30" />
        </Field>

        <fieldset>
          <legend className="text-meta text-muted">Years of work experience</legend>
          <div className="mt-1.5 grid grid-cols-4 gap-1 rounded-md border border-line p-1">
            {YEARS.map(({ v, label }) => (
              <label key={v} className={`flex h-9 cursor-pointer items-center justify-center rounded-sm font-mono text-body transition-colors duration-quick has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent/40 ${form.yoe === v ? "bg-accent text-on-accent" : "hover:bg-surface"}`}>
                <input type="radio" name="yoe" value={v} checked={form.yoe === v} onChange={() => set({ yoe: v })} className="sr-only" />
                {label}
              </label>
            ))}
          </div>
          <p className="mt-1.5 text-meta text-muted">Internships don&apos;t count. Pick 0 if you&apos;re graduating or just graduated.</p>
        </fieldset>

        <Field label="Graduation year" htmlFor="grad">
          <select id="grad" value={form.grad_year ?? ""} onChange={(e) => set({ grad_year: e.target.value ? Number(e.target.value) : null })}
            className="h-11 w-full rounded-md border border-line bg-canvas px-3 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/30">
            <option value="">Choose a year</option>
            {GRAD_YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </Field>

        <fieldset>
          <legend className="text-meta text-muted">Roles you want</legend>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {ROLES.map(({ v, label }) => {
              const on = form.target_roles.includes(v);
              return (
                <label key={v} className={`inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border px-3 text-body transition-colors duration-quick has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent/40 ${on ? "border-ink/25 bg-canvas font-medium shadow-raised" : "border-line hover:bg-surface"}`}>
                  <input type="checkbox" checked={on} onChange={() => toggleRole(v)} className="size-3.5 accent-[var(--accent)]" />
                  {label}
                </label>
              );
            })}
          </div>
        </fieldset>

        <div>
          <p className="text-meta text-muted">Resume</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-3 rounded-md border border-dashed border-line p-3">
            <button type="button" onClick={() => fileInput.current?.click()} disabled={busy}
              className="h-9 rounded-md border border-line bg-canvas px-3 text-meta font-medium shadow-raised transition-colors duration-quick hover:bg-surface disabled:opacity-60">
              {form.resume_name ? "Replace PDF" : "Upload PDF"}
            </button>
            <input ref={fileInput} type="file" accept="application/pdf" className="sr-only" tabIndex={-1} aria-label="Resume PDF"
              onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
            {form.resume_name ? (
              <span className="min-w-0 truncate font-mono text-meta">
                {form.resume_name}
                {file ? <span className="text-muted"> · not saved yet</span>
                  : form.resume_path && <> · <button type="button" onClick={openResume} className="font-sans font-medium text-accent underline">open</button></>}
              </span>
            ) : <span className="text-meta text-muted">PDF, up to 5 MB.</span>}
          </div>
        </div>

        <Field label="What Aventra reads from your resume" htmlFor="resume-text"
          hint={save.kind === "reading" ? "Reading your PDF…" : "Fix anything the PDF garbled. Aventra checks jobs against this text, never adds to it."}>
          <textarea id="resume-text" rows={10} maxLength={RESUME_TEXT_MAX} value={form.resume_text ?? ""} onChange={(e) => set({ resume_text: e.target.value })}
            aria-busy={save.kind === "reading"} placeholder="Upload a PDF, or paste your resume's text here."
            className="w-full rounded-md border border-line bg-canvas px-3 py-2.5 font-mono text-meta leading-5 outline-none transition-colors duration-quick placeholder:font-sans placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/30" />
        </Field>

        <div className="flex items-center gap-4 border-t border-line pt-6">
          <button type="submit" disabled={busy}
            className="h-11 rounded-md bg-accent px-6 text-base font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover disabled:opacity-60">
            {save.kind === "saving" ? "Saving…" : "Save profile"}
          </button>
          <p aria-live="polite" className="text-body text-muted">
            {save.kind === "error" && <span role="alert">{save.message}</span>}
          </p>
        </div>
      </form>

      {exists && (
        <button type="button" onClick={deleteEverything} disabled={busy}
          className="mt-12 text-meta text-muted underline underline-offset-2 hover:text-ink disabled:opacity-60">
          Delete my profile and resume
        </button>
      )}
    </AccountShell>
  );
}

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="text-meta text-muted">{label}</label>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1.5 text-meta text-muted">{hint}</p>}
    </div>
  );
}

function FormSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading your profile" className="space-y-6">
      <div className="h-7 w-1/3 animate-pulse rounded-sm bg-surface" />
      {Array.from({ length: 4 }, (_, i) => <div key={i} className="h-11 animate-pulse rounded-md bg-surface" />)}
      <div className="h-40 animate-pulse rounded-md bg-surface" />
    </div>
  );
}
