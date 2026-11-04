"use client";
// /insights (docs/decisions.md, 2026-11-04): this week against your goal, applications per week,
// what you did and when, and every skill your matching jobs ask for. Counting only.
import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AccountShell, NotSetUp } from "@/components/account/AccountShell";
import { profileFilters, toApiParams } from "@/lib/filters";
import { timeline, weeklyApplications, type Event } from "@/lib/insights";
import { skillsIn } from "@/lib/skills";
import { authConfigured, type Profile } from "@/lib/supabase";
import { recentChecks, recentTailored, trackedJobs, type FitCheck, type TailoredRow, type Tracked } from "@/lib/tracker";
import { useProfile } from "@/lib/useProfile";
import { WeeklyChart } from "./WeeklyChart";

export function Insights() {
  const load = useProfile();
  if (!authConfigured) return <AccountShell><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell><p role="alert" className="text-body text-muted">Couldn&apos;t open your insights: {load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell wide><div aria-busy="true" className="h-72 animate-pulse rounded-lg bg-surface" /></AccountShell>;
  return <Page profile={load.profile} />;
}

function Page({ profile }: { profile: Profile }) {
  const [data, setData] = useState<{ tracked: Tracked[]; checks: FitCheck[]; tailored: TailoredRow[] } | null>(null);
  useEffect(() => {
    Promise.allSettled([trackedJobs(), recentChecks(50), recentTailored(20)]).then(([t, c, r]) => setData({
      tracked: t.status === "fulfilled" ? t.value : [], checks: c.status === "fulfilled" ? c.value : [], tailored: r.status === "fulfilled" ? r.value : [],
    }));
  }, []);
  const weeks = useMemo(() => (data ? weeklyApplications(data.tracked) : []), [data]);
  const events = useMemo(() => (data ? timeline(data.tracked, data.checks, data.tailored) : []), [data]);
  const thisWeek = weeks.at(-1)?.n ?? 0;
  const goal = profile.weekly_goal || 5;

  return (
    <AccountShell wide>
      <p className="text-meta text-muted">Insights</p>
      <h1 className="mt-1 text-title font-medium">
        {data ? `${thisWeek} of ${goal} applications this week.` : "Counting your week…"}
      </h1>
      <p className="mt-1 text-body text-muted">
        {data && (thisWeek >= goal ? "Goal met. " : `${goal - thisWeek} to go. `)}
        <Link href="/profile/edit" className="text-accent underline underline-offset-2">Change your goal</Link>
      </p>

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Applications per week">{data ? <WeeklyChart weeks={weeks} goal={goal} /> : <Loading />}</Card>
          <Card title="Activity">{data ? <Timeline events={events} /> : <Loading />}</Card>
        </div>
        <Skills profile={profile} />
      </div>
    </AccountShell>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line p-5">
      <h2 className="mb-4 text-meta font-medium uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

const Loading = () => <p className="text-body text-muted">Loading…</p>;

const DOT: Record<Event["kind"], string> = {
  saved: "bg-line", applied: "bg-accent", moved: "bg-ink", fit: "bg-accent/50", tailored: "bg-accent/50",
};

function Timeline({ events }: { events: Event[] }) {
  if (!events.length) return <p className="text-body text-muted">Nothing yet. Save a job from the list and it starts here.</p>;
  const day = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short" });
  const groups: [string, Event[]][] = [];
  for (const e of events.slice(0, 40)) {
    const key = day.format(new Date(e.at));
    const last = groups.at(-1);
    if (last?.[0] === key) last[1].push(e); else groups.push([key, [e]]);
  }
  return (
    <ol className="space-y-5">
      {groups.map(([date, list]) => (
        <li key={date}>
          <h3 className="text-meta font-medium text-muted">{date}</h3>
          <ul className="mt-2 space-y-2 border-l border-line pl-4">
            {list.map((e, i) => (
              <li key={i} className="relative text-body">
                <span aria-hidden className={`absolute -left-[21px] top-1.5 size-2.5 rounded-full ring-2 ring-canvas ${DOT[e.kind]}`} />
                <span className="font-medium">{e.detail}</span> <span className="text-muted">· {e.title}</span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}

function Skills({ profile }: { profile: Profile }) {
  const [demand, setDemand] = useState<{ total: number; skills: { skill: string; n: number }[] } | "error" | null>(null);
  const filters = useMemo(() => profileFilters(profile.yoe, profile.target_roles), [profile.yoe, profile.target_roles]);
  useEffect(() => {
    const p = toApiParams(filters);
    const qs = new URLSearchParams({ experience: p.experience, role: p.role, ...(p.include_unstated ? { include_unstated: "true" } : {}) });
    fetch(`/api/skill-demand?${qs}`).then((r) => (r.ok ? r.json() : Promise.reject())).then(setDemand).catch(() => setDemand("error"));
  }, [filters]);
  const have = useMemo(() => skillsIn(profile.resume_text), [profile.resume_text]);
  return (
    <Card title="Skills your matches ask for">
      {demand === "error" ? <p className="text-body text-muted">Couldn&apos;t count skills right now.</p>
        : demand === null ? <Loading />
        : demand.skills.length === 0 ? <p className="text-body text-muted">Skills appear here after the next job refresh.</p>
        : (
          <>
            <p className="mb-3 text-meta text-muted">Share of your {demand.total.toLocaleString("en-IN")} matching jobs whose posting names each skill.</p>
            <ul className="space-y-2">
              {demand.skills.slice(0, 20).map(({ skill, n }) => {
                const pct = Math.round((n / Math.max(demand.total, 1)) * 100);
                const on = have.has(skill);
                return (
                  <li key={skill} className="grid grid-cols-[1fr_2.5rem] items-center gap-x-3 text-body">
                    <span className="flex items-center gap-1.5 truncate">
                      {on ? <Check aria-label="On your resume" className="size-3.5 shrink-0 text-accent" /> : <span aria-label="Not on your resume" className="size-3.5 shrink-0" />}
                      <span className={on ? "font-medium" : ""}>{skill}</span>
                    </span>
                    <span className="text-right font-mono text-meta">{pct}%</span>
                    <span aria-hidden className="col-span-2 h-1 rounded-full bg-surface"><span className="block h-full rounded-full bg-accent" style={{ width: `${pct}%` }} /></span>
                  </li>
                );
              })}
            </ul>
          </>
        )}
    </Card>
  );
}
