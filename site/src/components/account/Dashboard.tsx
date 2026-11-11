"use client";
// The board (docs/decisions.md, 2026-11-04): a one-line brief with one action, the tracker as a
// kanban, and a Today rail (strong matches, follow-ups, fit checks left, the skill gap). All of it
// is counting over real data except the fit verdicts, which come from Gemini (5 a day). The weekly
// chart, the timeline and every skill are on /insights; details on /profile/edit.
import type { User } from "@supabase/supabase-js";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FitRing } from "@/components/board/FitRing";
import { Kanban } from "@/components/board/Kanban";
import { SkillGap } from "@/components/board/SkillGap";
import { Today } from "@/components/board/Today";
import { fetchJobs, type JobSummary } from "@/lib/api";
import { brief, followUpsDue, isStrongMatch, missingSkills } from "@/lib/board";
import { profileFilters, toApiParams, toSearch } from "@/lib/filters";
import { skillsIn } from "@/lib/skills";
import { authConfigured, type Profile } from "@/lib/supabase";
import { useProfile } from "@/lib/useProfile";
import {
  fitQuota, moveJob, recentChecks, recentTailored, removeJob, trackedJobs,
  type FitCheck, type Quota, type Stage, type Tracked, type TailoredRow, type Verdict,
} from "@/lib/tracker";
import { AccountShell, NotSetUp } from "./AccountShell";

// Reopening a tailored resume (and pdf-lib) loads only when asked.
const TailorDialog = dynamic(() => import("@/components/TailorDialog").then((m) => m.TailorDialog), { ssr: false });

export function Dashboard() {
  const load = useProfile();
  if (!authConfigured) return <AccountShell><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell><p role="alert" className="text-body text-muted">Couldn&apos;t open your profile: {load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell wide><Skeleton /></AccountShell>;

  return <Board user={load.user} profile={load.profile} />;
}

interface Data {
  tracked: Tracked[] | "error";
  fresh: JobSummary[]; // posted in the last 24 hours, fitting the profile
  checks: FitCheck[];
  quota: Quota | "off" | null;
  demand: { total: number; skills: { skill: string; n: number }[] } | null;
  tailored: TailoredRow[];
}

function Board({ user, profile }: { user: User; profile: Profile }) {
  const filters = useMemo(() => profileFilters(profile.yoe, profile.target_roles), [profile.yoe, profile.target_roles]);
  const have = useMemo(() => skillsIn(profile.resume_text), [profile.resume_text]);
  const [data, setData] = useState<Data>({ tracked: [], fresh: [], checks: [], quota: null, demand: null, tailored: [] });
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState<TailoredRow | null>(null);

  const reloadTracked = useCallback(() => { trackedJobs().then((tracked) => setData((d) => ({ ...d, tracked }))).catch(() => {}); }, []);
  useEffect(() => {
    const p = toApiParams(filters);
    const qs = new URLSearchParams({ experience: p.experience, role: p.role, ...(p.include_unstated ? { include_unstated: "true" } : {}) });
    Promise.allSettled([
      trackedJobs(), fetchJobs({ ...p, posted: "24h" }, 1, false), recentChecks(10), fitQuota(),
      fetch(`/api/skill-demand?${qs}`).then((r) => (r.ok ? r.json() : null)), recentTailored(),
    ]).then(([tracked, fresh, checks, quota, demand, tailored]) => {
      setData({
        tracked: tracked.status === "fulfilled" ? tracked.value : "error",
        fresh: fresh.status === "fulfilled" ? fresh.value.jobs : [],
        checks: checks.status === "fulfilled" ? checks.value : [],
        quota: quota.status === "fulfilled" ? quota.value : "off",
        demand: demand.status === "fulfilled" ? demand.value : null,
        tailored: tailored.status === "fulfilled" ? tailored.value : [],
      });
      setLoaded(true);
    });
  }, [filters]);

  const tracked = Array.isArray(data.tracked) ? data.tracked : [];
  // The latest Gemini verdict per job: it upgrades (or settles) what the rules say.
  const verdicts = useMemo(() => {
    const out: Record<string, Verdict["fit"]> = {};
    for (const c of [...data.checks].reverse()) out[c.job_id] = c.result.fit;
    return out;
  }, [data.checks]);
  const strong = data.fresh.filter((j) => verdicts[j.id] === "strong" || (verdicts[j.id] !== "weak" && isStrongMatch(j, have)));
  const followUps = followUpsDue(tracked);
  const missing = missingSkills(data.demand?.skills ?? [], have);

  async function move(t: Tracked, status: Stage) {
    setData((d) => ({ ...d, tracked: tracked.map((x) => (x.id === t.id ? { ...x, status, applied_at: x.applied_at ?? (status !== "saved" ? new Date().toISOString() : null) } : x)) }));
    try { await moveJob(t.id, status); } catch { reloadTracked(); }
  }
  async function remove(t: Tracked) {
    setData((d) => ({ ...d, tracked: tracked.filter((x) => x.id !== t.id) }));
    try { await removeJob(t.id); } catch { reloadTracked(); }
  }

  const quota = data.quota && data.quota !== "off" && data.quota.enabled ? data.quota : null;
  return (
    <AccountShell wide>
      {/* The brief: what changed since you last looked, and the one thing to do about it. */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-meta text-muted">Today</p>
          <h1 className="mt-1 text-title font-medium" aria-live="polite">{loaded ? brief(strong.length, followUps.length) : "Reading today's jobs…"}</h1>
        </div>
        <Link href={"/" + toSearch({ ...filters, posted: "24h" })}
          className="inline-flex h-10 items-center rounded-md bg-accent px-4 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
          Review today&apos;s matches
        </Link>
      </div>

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-3">
        <section aria-label="Tracker" className="min-w-0 lg:col-span-2">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-meta font-medium uppercase tracking-wide text-muted">Tracker</h2>
            <span className="text-caption text-muted">Drag a card, or use its menu</span>
          </div>
          {data.tracked === "error" ? <p className="text-body text-muted">Couldn&apos;t load your tracker.</p>
            : <Kanban items={tracked} verdicts={verdicts} onMove={move} onRemove={remove} />}
        </section>

        <aside className="space-y-4" aria-label="Today">
          <Today userId={user.id} matches={strong} followUps={followUps} tracked={new Set(tracked.map((t) => t.job_id))} onSaved={reloadTracked} />
          <section className="rounded-lg border border-line p-4">
            <h2 className="text-meta font-medium uppercase tracking-wide text-muted">Fit checks</h2>
            {quota ? (
              <div className="mt-3 flex items-center gap-4">
                <FitRing remaining={quota.remaining} limit={quota.limit} />
                <p className="text-body">
                  <span className="font-medium">{quota.remaining} of {quota.limit}</span> left today
                  <span className="block text-meta text-muted">Tailored resumes: {quota.tailor.remaining} of {quota.tailor.limit} left</span>
                </p>
              </div>
            ) : <p className="mt-3 text-body text-muted">{data.quota === null ? "Loading…" : "Fit checks aren't switched on yet."}</p>}
            {data.tailored.length > 0 && (
              <ul className="mt-4 space-y-1.5 border-t border-line pt-3">
                {data.tailored.map((t) => (
                  <li key={t.id} className="flex items-center gap-3 text-body">
                    <span className="min-w-0 flex-1 truncate">Resume for <span className="font-medium">{t.jobs?.companies?.name}</span></span>
                    <button type="button" onClick={() => setOpen(t)} className="shrink-0 text-meta font-medium text-accent-text underline underline-offset-2">Open</button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {data.demand && <SkillGap missing={missing} total={data.demand.total} />}
        </aside>
      </div>
      {open && <TailorDialog jobId={open.job_id} title={open.jobs?.title ?? ""} company={open.jobs?.companies?.name ?? ""} initial={open.result} onClose={() => setOpen(null)} />}
    </AccountShell>
  );
}

function Skeleton() {
  return (
    <div aria-busy="true" aria-label="Loading your board" className="space-y-4">
      <div className="h-8 w-2/3 animate-pulse rounded-sm bg-surface" />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="h-72 animate-pulse rounded-lg bg-surface lg:col-span-2" /><div className="h-72 animate-pulse rounded-lg bg-surface" />
      </div>
    </div>
  );
}
