"use client";
// /insights (docs/decisions.md, 2026-11-04 and 2026-11-11): the market read against one person.
// What companies ask for in the jobs that fit them and which of it their resume shows, how much
// of the market is open at their years, then their own week: applications against the goal and
// what they did when. Counting only; the market numbers come from the pipeline's last run.
import { Check, Minus } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AccountShell, NotSetUp } from "@/components/account/AccountShell";
import { fetchMeta, type Meta } from "@/lib/api";
import { profileFilters, toApiParams } from "@/lib/filters";
import { timeline, weeklyApplications, type Event } from "@/lib/insights";
import { skillsIn } from "@/lib/skills";
import { authConfigured, type Profile } from "@/lib/supabase";
import { recentChecks, recentTailored, trackedJobs, type FitCheck, type TailoredRow, type Tracked } from "@/lib/tracker";
import { useProfile } from "@/lib/useProfile";
import { WeeklyChart } from "./WeeklyChart";

const TOP = 10; // the headline counts the resume against this many most-asked skills
type Demand = { total: number; skills: { skill: string; n: number }[] };

export function Insights() {
  const load = useProfile();
  if (!authConfigured) return <AccountShell title="Insights"><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell title="Insights"><p role="alert" className="text-body text-muted">Couldn&apos;t open your insights: {load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell title="Insights" wide><div aria-busy="true" className="h-72 animate-pulse rounded-lg bg-surface" /></AccountShell>;
  return <Page profile={load.profile} />;
}

function Page({ profile }: { profile: Profile }) {
  const [data, setData] = useState<{ tracked: Tracked[]; checks: FitCheck[]; tailored: TailoredRow[] } | null>(null);
  const [demand, setDemand] = useState<Demand | "error" | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const filters = useMemo(() => profileFilters(profile.yoe, profile.target_roles), [profile.yoe, profile.target_roles]);
  useEffect(() => {
    Promise.allSettled([trackedJobs(), recentChecks(50), recentTailored(20)]).then(([t, c, r]) => setData({
      tracked: t.status === "fulfilled" ? t.value : [], checks: c.status === "fulfilled" ? c.value : [], tailored: r.status === "fulfilled" ? r.value : [],
    }));
    const p = toApiParams(filters);
    const qs = new URLSearchParams({ experience: p.experience, role: p.role, ...(p.include_unstated ? { include_unstated: "true" } : {}) });
    fetch(`/api/skill-demand?${qs}`).then((r) => (r.ok ? r.json() : Promise.reject())).then(setDemand).catch(() => setDemand("error"));
    fetchMeta().then(setMeta).catch(() => {});
  }, [filters]);
  const have = useMemo(() => skillsIn(profile.resume_text), [profile.resume_text]);
  const weeks = useMemo(() => (data ? weeklyApplications(data.tracked) : []), [data]);
  const events = useMemo(() => (data ? timeline(data.tracked, data.checks, data.tailored) : []), [data]);
  const thisWeek = weeks.at(-1)?.n ?? 0;
  const goal = profile.weekly_goal || 5;

  const top = demand && demand !== "error" ? demand.skills.slice(0, TOP) : [];
  const shown = top.filter((s) => have.has(s.skill)).length;
  const headline = demand === null ? "Reading what companies ask for…"
    : top.length === 0 ? `${thisWeek} of ${goal} applications this week.`
    : `Your resume shows ${shown} of the ${top.length} skills companies ask for most.`;

  return (
    <AccountShell title="Insights" sub="The market, read against your profile" wide>
      <h2 className="max-w-[26ch] font-display text-headline lg:text-hero" aria-live="polite">{headline}</h2>
      {top.length > 0 && (
        <p className="mt-3 max-w-[64ch] text-body text-muted">
          Counted across the {(demand as Demand).total.toLocaleString("en-IN")} open jobs that fit your years and roles. A skill counts as yours only when your saved resume names it.
          {shown < top.length && <> If you have one of the missing skills, <Link href="/profile/edit" className="text-accent-text underline underline-offset-2">add it to your resume</Link>.</>}
        </p>
      )}

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><Skills demand={demand} have={have} /></div>
        <OpenToYou meta={meta} yoe={profile.yoe} />
      </div>

      <h2 className="mt-12 font-display text-headline">
        {data ? `${thisWeek} of ${goal} applications this week.` : "Counting your week…"}
      </h2>
      <p className="mt-1 text-body text-muted">
        {data && (thisWeek >= goal ? "Goal met. " : `${goal - thisWeek} to go. `)}
        <Link href="/profile/edit" className="text-accent-text underline underline-offset-2">Change your goal</Link>
      </p>
      <div className="mt-6 grid items-start gap-6 lg:grid-cols-2">
        <Card title="Applications per week">{data ? <WeeklyChart weeks={weeks} goal={goal} /> : <Loading />}</Card>
        <Card title="Activity">{data ? <Timeline events={events} /> : <Loading />}</Card>
      </div>
    </AccountShell>
  );
}

/** How many open jobs someone with N years can apply to, N from 0 to 5, with the person's own
 *  years marked. From the pipeline's snapshot, so it covers every role, not only theirs. */
function OpenToYou({ meta, yoe }: { meta: Meta | null; yoe: number }) {
  const within = meta?.within_years;
  if (!meta) return <Card title="How much of the market is open to you"><Loading /></Card>;
  if (!within) return null;
  const mine = Math.min(Math.max(Math.round(yoe), 0), 5);
  const bars = ([0, 1, 2, 3, 4, 5] as const).map((y) => ({ y, n: within[String(y) as "0"] ?? 0 }));
  const max = Math.max(...bars.map((b) => b.n), 1);
  const open = bars[mine].n;
  return (
    <Card title="How much of the market is open to you">
      <p className="text-body">
        <span className="font-medium">{open.toLocaleString("en-IN")} of {meta.total.toLocaleString("en-IN")}</span> open jobs ask for {mine} {mine === 1 ? "year" : "years"} or fewer.
      </p>
      <div role="img" aria-label={`Open jobs by years of experience: ${bars.map((b) => `${b.y} years ${b.n}`).join(", ")}.`}
        className="mt-5 flex h-40 items-end gap-2 border-b border-ink">
        {bars.map((b) => (
          <div key={b.y} className="flex h-full flex-1 flex-col justify-end">
            <span className="mb-1 text-center font-mono text-caption text-muted">{b.n >= 1000 ? `${(b.n / 1000).toFixed(1)}k` : b.n}</span>
            {/* Each bar grows from the baseline once, so the comparison is read left to right. */}
            <div className={`grow-y rounded-t-sm ${b.y === mine ? "bg-accent" : "bg-line"}`} style={{ height: `${(b.n / max) * 100}%`, animationDelay: `${b.y * 40}ms` }} />
          </div>
        ))}
      </div>
      <div aria-hidden className="mt-1.5 flex gap-2 text-center font-mono text-caption text-muted">
        {bars.map((b) => <span key={b.y} className={`flex-1 ${b.y === mine ? "font-semibold text-ink" : ""}`}>{b.y === mine ? "You" : b.y}</span>)}
      </div>
      <p className="mt-3 text-meta text-muted">Each bar is every open job a person with that many years can apply to, in all roles. The marigold bar is you.</p>
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-card-line bg-card p-5">
      <h2 className="mb-4 font-display text-[1.375rem] leading-tight">{title}</h2>
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

function Skills({ demand, have }: { demand: Demand | "error" | null; have: Set<string> }) {
  return (
    <Card title="What companies ask for, and where you stand">
      {demand === "error" ? <p className="text-body text-muted">Couldn&apos;t count skills right now.</p>
        : demand === null ? <Loading />
        : demand.skills.length === 0 ? <p className="text-body text-muted">Skills appear here after the next job refresh.</p>
        : (
          <ol>
            {demand.skills.slice(0, 20).map(({ skill, n }, i) => {
              const pct = Math.round((n / Math.max(demand.total, 1)) * 100);
              const on = have.has(skill);
              return (
                <li key={skill} className="grid grid-cols-[1.25rem_minmax(0,9rem)_minmax(0,1fr)_2.5rem_8.5rem] items-center gap-x-3 border-t border-line py-2 text-body first:border-t-0 max-sm:grid-cols-[1.25rem_minmax(0,1fr)_2.5rem_6.5rem]">
                  <span className="font-mono text-caption text-muted">{i + 1}</span>
                  <span className="truncate font-medium">{on ? skill : <span className="rounded-sm bg-mark px-1">{skill}</span>}</span>
                  <span aria-hidden className="h-1.5 overflow-hidden rounded-full bg-line max-sm:hidden">
                    <span className="block h-full origin-left rounded-full bg-accent animate-[grow-x_500ms_var(--ease-out-soft)_both]" style={{ width: `${pct}%`, animationDelay: `${i * 25}ms` }} />
                  </span>
                  <span className="text-right font-mono text-meta">{pct}%</span>
                  <span className={`flex items-center gap-1.5 text-meta ${on ? "font-medium text-card-pass" : "text-muted"}`}>
                    {on ? <Check aria-hidden className="size-3.5" /> : <Minus aria-hidden className="size-3.5" />}{on ? "On your resume" : "Not on it"}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
    </Card>
  );
}
