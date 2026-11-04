"use client";
// The profile dashboard (docs/decisions.md, 2026-11-04): jobs for you and fit checks on top,
// then the tracker, then resume vs. the market; details live on /profile/edit. Everything here
// is counting over real data except the fit verdicts, which come from Gemini (5 a day).
import type { User } from "@supabase/supabase-js";
import { Check, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchJobs } from "@/lib/api";
import { fromSearch, profileFilters, toApiParams, toSearch, type Filters } from "@/lib/filters";
import { sessionChanged } from "@/lib/session";
import { skillsIn } from "@/lib/skills";
import { authConfigured, PROFILE_COLUMNS, supabase, type Profile } from "@/lib/supabase";
import {
  fitQuota, moveJob, recentChecks, recentTailored, removeJob, STAGES, trackedJobs,
  type FitCheck, type Quota, type Stage, type Tracked, type TailoredRow,
} from "@/lib/tracker";
import { AccountShell, NotSetUp } from "./AccountShell";

// Reopening a tailored resume (and pdf-lib) loads only when asked.
const TailorDialog = dynamic(() => import("@/components/TailorDialog").then((m) => m.TailorDialog), { ssr: false });

const ROLE_LABEL: Record<string, string> = { ai_ml: "AI/ML", backend: "Backend", mobile: "Mobile" };
const fmt = (n: number) => n.toLocaleString("en-IN");

type Load = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; user: User; profile: Profile };

export function Dashboard() {
  const router = useRouter();
  const [load, setLoad] = useState<Load>({ kind: "loading" });

  useEffect(() => {
    if (!authConfigured) return;
    const sb = supabase();
    let cancelled = false;
    // getSession also swaps a sign-in link's ?code= for a session: this is where sign-in lands.
    sb.auth.getSession().then(async ({ data, error }) => {
      if (cancelled) return;
      if (error) return setLoad({ kind: "error", message: `${error.message}. The link may have expired; sign in again.` });
      const user = data.session?.user;
      if (!user) return router.replace("/login");
      sessionChanged();
      if (location.search.includes("code=")) history.replaceState(null, "", "/profile");
      const row = await sb.from("students").select(PROFILE_COLUMNS).eq("id", user.id).maybeSingle<Profile>();
      if (cancelled) return;
      if (row.error) return setLoad({ kind: "error", message: row.error.message });
      // First visit: nothing to show until there's a profile.
      if (!row.data) return router.replace("/profile/edit");
      setLoad({ kind: "ready", user, profile: { ...row.data, yoe: Number(row.data.yoe) } });
    });
    return () => { cancelled = true; };
  }, [router]);

  if (!authConfigured) return <AccountShell><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell><p role="alert" className="text-body text-muted">Couldn&apos;t open your profile: {load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell wide><Skeleton /></AccountShell>;

  const { profile } = load;
  const filters = profileFilters(profile.yoe, profile.target_roles);
  const first = profile.name.trim().split(/\s+/)[0];
  const summary = [
    profile.yoe >= 3 ? "3+ yrs" : `${profile.yoe} ${profile.yoe === 1 ? "yr" : "yrs"}`,
    profile.target_roles.length ? profile.target_roles.map((r) => ROLE_LABEL[r] ?? r).join(", ") : "All target roles",
    profile.grad_year ? `Class of ${profile.grad_year}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <AccountShell wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-title font-medium">Hi {first}</h1>
          <p className="mt-1 text-body text-muted">{summary}</p>
        </div>
        <Link href="/profile/edit" className="text-meta font-medium text-accent underline underline-offset-2">Edit your details</Link>
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <JobsForYou filters={filters} />
        <FitChecks />
      </div>
      <div className="mt-4"><Tracker /></div>
      <div className="mt-4"><ResumeVsMarket filters={filters} resume={profile.resume_text} /></div>
    </AccountShell>
  );
}

function Card({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line p-5">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-meta font-medium uppercase tracking-wide text-muted">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function JobsForYou({ filters }: { filters: Filters }) {
  const [counts, setCounts] = useState<{ total: number; week: number } | "error" | null>(null);
  const key = toSearch(filters); // a string, so the counts load once per set of filters
  useEffect(() => {
    const ctrl = new AbortController();
    const params = toApiParams(fromSearch(key));
    Promise.all([fetchJobs(params, 1, true, ctrl.signal), fetchJobs({ ...params, posted: "7d" }, 1, true, ctrl.signal)])
      .then(([all, week]) => setCounts({ total: all.total ?? 0, week: week.total ?? 0 }))
      .catch((e) => { if (e.name !== "AbortError") setCounts("error"); });
    return () => ctrl.abort();
  }, [key]);
  return (
    <Card title="Jobs for you">
      {counts === "error" ? <p className="text-body text-muted">Couldn&apos;t count jobs right now.</p> : (
        <>
          <p className="font-mono text-display font-semibold">{counts ? fmt(counts.total) : "…"}</p>
          <p className="mt-1 text-body text-muted">
            open jobs fit your years and roles{counts ? <>, <span className="text-ink">{fmt(counts.week)}</span> posted this week</> : null}.
          </p>
        </>
      )}
      <Link href={"/" + toSearch(filters)}
        className="mt-5 inline-flex h-10 items-center rounded-md bg-accent px-4 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
        See your jobs
      </Link>
    </Card>
  );
}

const FIT_TONE: Record<string, string> = { strong: "bg-accent text-on-accent", partial: "bg-surface text-ink border border-line", weak: "text-muted border border-line" };

function FitChecks() {
  const [quota, setQuota] = useState<Quota | "off" | null>(null);
  const [checks, setChecks] = useState<FitCheck[] | null>(null);
  const [tailored, setTailored] = useState<TailoredRow[]>([]);
  const [open, setOpen] = useState<TailoredRow | null>(null);
  useEffect(() => {
    fitQuota().then(setQuota).catch(() => setQuota("off"));
    recentChecks().then(setChecks).catch(() => setChecks([]));
    recentTailored().then(setTailored).catch(() => {});
  }, []);
  const off = quota === "off" || (quota !== null && !quota.enabled);
  return (
    <Card title="Fit checks" aside={quota && quota !== "off" && quota.enabled
      ? <span className="font-mono text-meta"><span className="text-ink">{quota.remaining}</span> <span className="text-muted">of {quota.limit} left today</span></span> : null}>
      {off ? <p className="text-body text-muted">Fit checks aren&apos;t switched on yet.</p>
        : checks === null ? <p className="text-body text-muted">Loading…</p>
        : checks.length === 0 ? (
          <p className="text-body text-muted">No checks yet. Open a job and press <span className="text-ink">Check my fit</span>: Gemini compares it with your resume.</p>
        ) : (
          <ul className="space-y-2.5">
            {checks.map((c) => (
              <li key={c.id} className="flex items-center gap-3 text-body">
                <span className={`w-16 shrink-0 rounded-sm px-1.5 py-0.5 text-center text-caption font-medium capitalize ${FIT_TONE[c.result.fit]}`}>{c.result.fit}</span>
                <a href={c.jobs?.url} target="_blank" rel="noopener" className="min-w-0 truncate hover:underline">
                  <span className="font-medium">{c.jobs?.companies?.name}</span> · {c.jobs?.title}
                </a>
              </li>
            ))}
          </ul>
        )}
      {tailored.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <h3 className="flex items-baseline justify-between text-meta text-muted">
            Tailored resumes
            {quota && quota !== "off" && <span className="font-mono"><span className="text-ink">{quota.tailor.remaining}</span> of {quota.tailor.limit} left today</span>}
          </h3>
          <ul className="mt-2 space-y-1.5">
            {tailored.map((t) => (
              <li key={t.id} className="flex items-center gap-3 text-body">
                <span className="min-w-0 flex-1 truncate"><span className="font-medium">{t.jobs?.companies?.name}</span> · {t.jobs?.title}</span>
                <button type="button" onClick={() => setOpen(t)} className="shrink-0 text-meta font-medium text-accent underline underline-offset-2">Open</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {open && <TailorDialog jobId={open.job_id} title={open.jobs?.title ?? ""} company={open.jobs?.companies?.name ?? ""} initial={open.result} onClose={() => setOpen(null)} />}
    </Card>
  );
}

function Tracker() {
  const [items, setItems] = useState<Tracked[] | "error" | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  useEffect(() => { trackedJobs().then(setItems).catch(() => setItems("error")); }, []);
  if (items === "error") return <Card title="Tracker"><p className="text-body text-muted">Couldn&apos;t load your tracker.</p></Card>;

  async function move(t: Tracked, status: Stage) {
    setBusy(t.id);
    try { await moveJob(t.id, status); setItems((xs) => Array.isArray(xs) ? xs.map((x) => (x.id === t.id ? { ...x, status } : x)) : xs); }
    finally { setBusy(null); }
  }
  async function remove(t: Tracked) {
    setBusy(t.id);
    try { await removeJob(t.id); setItems((xs) => Array.isArray(xs) ? xs.filter((x) => x.id !== t.id) : xs); }
    finally { setBusy(null); }
  }
  const count = (s: Stage) => (Array.isArray(items) ? items.filter((x) => x.status === s).length : 0);
  return (
    <Card title="Tracker">
      <div className="mb-4 flex flex-wrap gap-2">
        {STAGES.map((s) => (
          <span key={s.v} className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1 text-meta">
            {s.label} <span className="font-mono text-ink">{count(s.v)}</span>
          </span>
        ))}
      </div>
      {items === null ? <p className="text-body text-muted">Loading…</p>
        : items.length === 0 ? <p className="text-body text-muted">Nothing saved yet. Press <span className="text-ink">Save</span> on any job to keep it here.</p>
        : (
          <ul className="divide-y divide-line">
            {items.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3 py-2.5 text-body">
                <a href={t.jobs?.url} target="_blank" rel="noopener" className="min-w-0 flex-1 truncate hover:underline">
                  <span className="font-medium">{t.jobs?.companies?.name}</span> · {t.jobs?.title}
                </a>
                <label className="sr-only" htmlFor={`stage-${t.id}`}>Stage</label>
                <select id={`stage-${t.id}`} value={t.status} disabled={busy === t.id} onChange={(e) => move(t, e.target.value as Stage)}
                  className="h-8 rounded-md border border-line bg-canvas px-2 text-meta outline-none focus:border-accent focus:ring-2 focus:ring-accent/30">
                  {STAGES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
                </select>
                <button type="button" aria-label={`Remove ${t.jobs?.title ?? "job"}`} disabled={busy === t.id} onClick={() => remove(t)}
                  className="grid size-8 place-items-center rounded-md text-muted transition-colors duration-quick hover:bg-surface hover:text-ink">
                  <X aria-hidden className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
    </Card>
  );
}

function ResumeVsMarket({ filters, resume }: { filters: Filters; resume: string | null }) {
  const [demand, setDemand] = useState<{ total: number; skills: { skill: string; n: number }[] } | "error" | null>(null);
  const key = toSearch(filters);
  useEffect(() => {
    const p = toApiParams(fromSearch(key));
    const qs = new URLSearchParams({ experience: p.experience, role: p.role, ...(p.include_unstated ? { include_unstated: "true" } : {}) });
    fetch(`/api/skill-demand?${qs}`).then((r) => (r.ok ? r.json() : Promise.reject())).then(setDemand).catch(() => setDemand("error"));
  }, [key]);
  const have = skillsIn(resume);
  const top = demand && demand !== "error" ? demand.skills.slice(0, 10) : [];
  return (
    <Card title="Resume vs. the market" aside={demand && demand !== "error" ? <span className="text-meta text-muted">your {fmt(demand.total)} matching jobs</span> : null}>
      {demand === "error" ? <p className="text-body text-muted">Couldn&apos;t count skills right now.</p>
        : demand === null ? <p className="text-body text-muted">Loading…</p>
        : top.length === 0 ? <p className="text-body text-muted">Skills appear here after the next job refresh.</p>
        : (
          <ul className="space-y-2">
            {top.map(({ skill, n }) => {
              const pct = Math.round((n / Math.max(demand.total, 1)) * 100);
              const on = have.has(skill);
              return (
                <li key={skill} className="grid grid-cols-[7.5rem_1fr_3rem_8.5rem] items-center gap-3 text-body max-sm:grid-cols-[6.5rem_1fr_2.75rem] max-sm:gap-2">
                  <span className="truncate font-medium">{skill}</span>
                  <span aria-hidden className="h-1.5 rounded-full bg-surface"><span className="block h-full rounded-full bg-accent" style={{ width: `${pct}%` }} /></span>
                  <span className="text-right font-mono text-meta">{pct}%</span>
                  <span className={`text-meta max-sm:col-span-3 max-sm:-mt-1 ${on ? "text-ink" : "text-muted"}`}>{on ? <span className="inline-flex items-center gap-1"><Check aria-hidden className="size-3.5" />on your resume</span> : "not on your resume"}</span>
                </li>
              );
            })}
          </ul>
        )}
      <p className="mt-4 text-meta text-muted">Share of your matching jobs whose posting names the skill. Ticks come from your saved resume text.</p>
    </Card>
  );
}

function Skeleton() {
  return (
    <div aria-busy="true" aria-label="Loading your profile" className="space-y-4">
      <div className="h-7 w-40 animate-pulse rounded-sm bg-surface" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-44 animate-pulse rounded-lg bg-surface" /><div className="h-44 animate-pulse rounded-lg bg-surface" />
      </div>
      <div className="h-56 animate-pulse rounded-lg bg-surface" />
    </div>
  );
}
