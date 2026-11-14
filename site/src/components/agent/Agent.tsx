"use client";
// /agent (docs/decisions.md, 2026-11-12 and 2026-11-14): the agent chat first (./Chat.tsx), and
// under "Today" what Aventra already does on the person's behalf: new jobs that strongly fit the
// resume, fit checks with Gemini (5 a day) and tailored resumes (2 a day), each kept to reopen.
import type { User } from "@supabase/supabase-js";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AccountShell, NotSetUp } from "@/components/account/AccountShell";
import { FitRing } from "@/components/board/FitRing";
import { Today } from "@/components/board/Today";
import { fetchJobs, type JobSummary } from "@/lib/api";
import { brief, followUpsDue, isStrongMatch } from "@/lib/board";
import { profileFilters, toApiParams, toSearch } from "@/lib/filters";
import { shortDate } from "@/lib/format";
import { skillsIn } from "@/lib/skills";
import { authConfigured, type Profile } from "@/lib/supabase";
import { fitQuota, recentChecks, recentTailored, trackedJobs, type FitCheck, type Quota, type TailoredRow, type Tracked } from "@/lib/tracker";
import { useProfile } from "@/lib/useProfile";
import { Chat } from "./Chat";

// Reopening a tailored resume (and pdf-lib) loads only when asked.
const TailorDialog = dynamic(() => import("@/components/TailorDialog").then((m) => m.TailorDialog), { ssr: false });

export function Agent() {
  const load = useProfile();
  if (!authConfigured) return <AccountShell title="Agent"><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell title="Agent"><p role="alert" className="text-body text-muted">Couldn&apos;t open this page: {load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell title="Agent" wide><div aria-busy="true" className="h-72 animate-pulse rounded-lg bg-surface" /></AccountShell>;
  return <Page user={load.user} profile={load.profile} />;
}

interface Data { tracked: Tracked[]; fresh: JobSummary[]; checks: FitCheck[]; quota: Quota | null; tailored: TailoredRow[] }

function Page({ user, profile }: { user: User; profile: Profile }) {
  const filters = useMemo(() => profileFilters(profile.yoe, profile.target_roles), [profile.yoe, profile.target_roles]);
  const have = useMemo(() => skillsIn(profile.resume_text), [profile.resume_text]);
  const [data, setData] = useState<Data | null>(null);
  const [open, setOpen] = useState<TailoredRow | null>(null);
  const [view, setView] = useState<"chat" | "today">("chat");

  const reloadTracked = useCallback(() => { trackedJobs().then((tracked) => setData((d) => (d ? { ...d, tracked } : d))).catch(() => {}); }, []);
  useEffect(() => {
    Promise.allSettled([trackedJobs(), fetchJobs({ ...toApiParams(filters), posted: "24h" }, 1, false), recentChecks(10), fitQuota(), recentTailored(20)])
      .then(([tracked, fresh, checks, quota, tailored]) => setData({
        tracked: tracked.status === "fulfilled" ? tracked.value : [],
        fresh: fresh.status === "fulfilled" ? fresh.value.jobs : [],
        checks: checks.status === "fulfilled" ? checks.value : [],
        quota: quota.status === "fulfilled" && quota.value.enabled ? quota.value : null,
        tailored: tailored.status === "fulfilled" ? tailored.value : [],
      }));
  }, [filters]);

  // The latest Gemini verdict per job upgrades (or settles) what the rules say.
  const verdicts = useMemo(() => Object.fromEntries([...(data?.checks ?? [])].reverse().map((c) => [c.job_id, c.result.fit])), [data]);
  const strong = (data?.fresh ?? []).filter((j) => verdicts[j.id] === "strong" || (verdicts[j.id] !== "weak" && isStrongMatch(j, have)));
  const followUps = followUpsDue(data?.tracked ?? []);

  return (
    <AccountShell title="Agent" sub={view === "chat" ? "Ask about jobs, companies or people" : "What Aventra has done for you"} wide>
      <div role="tablist" aria-label="Agent" className="mb-6 flex gap-1.5">
        {(["chat", "today"] as const).map((v) => (
          <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => setView(v)}
            className={`rounded-full border px-4 py-1.5 text-meta font-medium transition-colors duration-quick ${view === v ? "border-ink bg-ink text-canvas" : "border-line hover:border-ink"}`}>
            {v === "chat" ? "Chat" : "Today"}
          </button>
        ))}
      </div>
      {view === "chat" ? <Chat name={profile.name} initialRemaining={data?.quota?.agent?.remaining ?? null} /> : <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 className="max-w-[24ch] font-display text-headline lg:text-hero" aria-live="polite">{data ? brief(strong.length, followUps.length) : "Reading today's jobs…"}</h2>
        <Link href={"/" + toSearch({ ...filters, posted: "24h" })}
          className="press inline-flex h-10 items-center rounded-md bg-accent px-4 text-meta font-medium text-on-accent duration-quick hover:bg-accent-hover">
          Review today&apos;s matches
        </Link>
      </div>

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel title="Resumes tailored for a job" note="Reworded from your saved resume toward one posting, never adding a skill or a number. Two a day.">
            {!data ? <Loading /> : data.tailored.length === 0
              ? <p className="text-body text-muted">None yet. Open a job, check your fit, then tailor your resume for it.</p>
              : (
                <ul className="-mx-2">
                  {data.tailored.map((t) => (
                    <li key={t.id}>
                      <button type="button" onClick={() => setOpen(t)} className="press flex w-full items-center gap-3 rounded-md px-2 py-2.5 text-left text-body duration-quick hover:bg-surface">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{t.jobs?.title}</span>
                          <span className="block truncate text-meta text-muted">{t.jobs?.companies?.name} · {changed(t)} reworded</span>
                        </span>
                        <span className="shrink-0 font-mono text-caption text-muted">{shortDate(t.created_at)}</span>
                        <span className="shrink-0 text-meta font-medium text-accent-text underline underline-offset-2">Open</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
          </Panel>
          <Panel title="Fit checks" note="Gemini reads the posting against your resume. Five a day.">
            {!data ? <Loading /> : data.checks.length === 0
              ? <p className="text-body text-muted">None yet. Open a job and press &quot;Check my fit&quot;.</p>
              : (
                <ul className="space-y-3">
                  {data.checks.map((c) => (
                    <li key={c.id} className="text-body">
                      <span className={`mr-2 rounded-sm px-1.5 text-meta font-medium capitalize ${c.result.fit === "strong" ? "bg-accent text-on-accent" : "border border-line"}`}>{c.result.fit}</span>
                      <a href={c.jobs?.url} target="_blank" rel="noopener" className="font-medium hover:underline">{c.jobs?.title}</a>
                      <span className="text-muted"> · {c.jobs?.companies?.name}</span>
                      {c.result.advice && <span className="mt-0.5 block text-meta text-muted">{c.result.advice}</span>}
                    </li>
                  ))}
                </ul>
              )}
          </Panel>
        </div>

        <aside className="space-y-6" aria-label="Today">
          <Today userId={user.id} matches={strong} followUps={followUps} tracked={new Set((data?.tracked ?? []).map((t) => t.job_id))} onSaved={reloadTracked} />
          <Panel title="Today's allowance">
            {!data ? <Loading /> : data.quota ? (
              <div className="flex items-center gap-4">
                <FitRing remaining={data.quota.remaining} limit={data.quota.limit} />
                <p className="text-body">
                  <span className="font-medium">{data.quota.remaining} of {data.quota.limit}</span> fit checks left
                  <span className="block text-meta text-muted">Tailored resumes: {data.quota.tailor.remaining} of {data.quota.tailor.limit} left</span>
                </p>
              </div>
            ) : <p className="text-body text-muted">Fit checks aren&apos;t switched on yet.</p>}
          </Panel>
        </aside>
      </div>
      </>}
      {open && <TailorDialog jobId={open.job_id} title={open.jobs?.title ?? ""} company={open.jobs?.companies?.name ?? ""} initial={open.result} onClose={() => setOpen(null)} />}
    </AccountShell>
  );
}

/** "3 lines": how many lines of the resume the rewrite changed. */
function changed(t: TailoredRow): string {
  const n = t.result.sections.flatMap((s) => s.lines).filter((l) => !l.kept_original && l.text.trim() !== l.original.trim()).length;
  return `${n} ${n === 1 ? "line" : "lines"}`;
}

function Panel({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-card-line bg-card p-5">
      <h2 className="font-display text-[1.375rem] leading-tight">{title}</h2>
      {note && <p className="mt-1 text-meta text-muted">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

const Loading = () => <p className="text-body text-muted">Loading…</p>;
