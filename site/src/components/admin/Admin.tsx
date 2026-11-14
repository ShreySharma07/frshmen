"use client";
// /admin (docs/decisions.md 2026-11-13; concept A in docs/wireframes/admin/): every number on one
// page for whoever runs Aventra, then a form to add a job by hand. Unlinked; the API answers only
// accounts in the admins table, so anyone else sees "admins only".
import { ArrowUpRight, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AccountShell, NotSetUp } from "@/components/account/AccountShell";
import { addJob, adminOverview, closeJob, manualJobs, type ManualJob, type NewJob, type Overview } from "@/lib/admin";
import { CATEGORY, ATS } from "@/lib/describe";
import { BAND_CHOICES } from "@/lib/filters";
import { shortDate } from "@/lib/format";
import { authConfigured } from "@/lib/supabase";
import { useProfile } from "@/lib/useProfile";
import { Contacts } from "./Contacts";

const n = (x: number) => x.toLocaleString("en-IN");
const ANALYTICS = "https://dash.cloudflare.com/?to=/:account/web-analytics";

export function Admin() {
  const load = useProfile();
  if (!authConfigured) return <AccountShell title="Admin"><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell title="Admin"><p role="alert" className="text-body text-muted">{load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell title="Admin" wide><div aria-busy="true" className="h-72 animate-pulse rounded-lg bg-surface" /></AccountShell>;
  return <Page />;
}

function Page() {
  const [data, setData] = useState<Overview | { error: string; status?: number } | null>(null);
  useEffect(() => {
    adminOverview().then(setData).catch((e: Error & { status?: number }) => setData({ error: e.message, status: e.status }));
  }, []);

  if (data && "error" in data) {
    return (
      <AccountShell title="Admin">
        <p role="alert" className="text-body text-muted">
          {data.status === 403 ? "This page is for Aventra's admins only." : `Couldn't load the numbers: ${data.error}`}
        </p>
      </AccountShell>
    );
  }
  return (
    <AccountShell title="Admin" sub="Jobs, pipeline and people, live" wide>
      {!data ? <div aria-busy="true" className="h-72 animate-pulse rounded-lg bg-surface" /> : <Numbers o={data} />}
      <AddJob />
      <Contacts Card={Card} />
    </AccountShell>
  );
}

function Card({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-card-line bg-card p-5 ${className}`}>
      <h2 className="mb-3 text-meta font-medium uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

function Stat({ title, value, note, href }: { title: string; value: string; note: React.ReactNode; href?: string }) {
  return (
    <Card title={title}>
      <p className="font-display text-headline leading-none tabular-nums">
        {href ? <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">{value}<ArrowUpRight aria-hidden className="size-5" /></a> : value}
      </p>
      <p className="mt-2 text-meta text-muted">{note}</p>
    </Card>
  );
}

function ago(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  return mins < 60 ? `${mins} min ago` : mins < 48 * 60 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} days ago`;
}

function Numbers({ o }: { o: Overview }) {
  const last = o.pipeline.runs[0];
  const today = o.users.signups.at(-1)?.n ?? 0;
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat title="Open jobs" value={n(o.jobs.open)} note={`+${n(o.jobs.new_24h)} new in 24 h`} />
        <Stat title="Users" value={n(o.users.total)} note={`+${n(today)} today`} />
        <Stat title="Visits" value="Cloudflare" href={ANALYTICS} note="Web Analytics: visits, pages, countries" />
        <Stat title="Last pipeline run" value={last ? ago(last.finished_at) : "None yet"}
          note={last ? `${n(last.companies_ok)} boards ok · ${n(last.companies_failed)} failed` : "Runs every 3 hours"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Sign-ups, last 14 days" className="lg:col-span-2"><Signups days={o.users.signups} /></Card>
        <Card title="AI use, last 24 h">
          <p className="text-body"><span className="font-mono">{n(o.users.usage_24h.fit_checks)}</span> fit checks <span className="text-muted">(5 per person a day)</span></p>
          <p className="mt-2 text-body"><span className="font-mono">{n(o.users.usage_24h.tailored_resumes)}</span> tailored résumés <span className="text-muted">(2 per person)</span></p>
        </Card>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-3">
        <Card title="Open jobs by" className="lg:col-span-2"><Breakdown o={o} /></Card>
        <Card title="Pipeline, last 10 runs"><Runs o={o} /></Card>
      </div>
    </div>
  );
}

function Signups({ days }: { days: Overview["users"]["signups"] }) {
  const max = Math.max(1, ...days.map((d) => d.n));
  return (
    <>
      <div role="img" aria-label={days.map((d) => `${d.day}: ${d.n}`).join(", ")} className="flex h-32 items-end gap-1.5 border-b border-ink">
        {days.map((d, i) => (
          <div key={d.day} className="flex h-full flex-1 flex-col justify-end">
            {d.n > 0 && <span className="mb-1 text-center font-mono text-caption text-muted">{d.n}</span>}
            <div className="grow-y rounded-t-sm bg-accent" style={{ height: `${(d.n / max) * 100}%`, animationDelay: `${i * 25}ms` }} />
          </div>
        ))}
      </div>
      <div aria-hidden className="mt-1 flex justify-between font-mono text-caption text-muted">
        <span>{shortDate(days[0]?.day ?? null)}</span><span>today</span>
      </div>
    </>
  );
}

type By = "category" | "band" | "source";

function Breakdown({ o }: { o: Overview }) {
  const [by, setBy] = useState<By>("category");
  const rows: [string, number][] = by === "category"
    ? Object.entries(o.jobs.by_category).map(([k, v]) => [CATEGORY[k] ?? k, v])
    : by === "band" ? BAND_CHOICES.map((c) => [c.label, o.jobs.bands[c.band] ?? 0])
    : o.jobs.by_source.map((s) => [ATS[s.source] ?? s.source, s.n]);
  const max = Math.max(1, ...rows.map(([, v]) => v));
  return (
    <>
      <div role="group" aria-label="Group by" className="mb-3 flex gap-1.5">
        {(["category", "band", "source"] as By[]).map((b) => (
          <button key={b} type="button" aria-pressed={by === b} onClick={() => setBy(b)}
            className={`rounded-full border px-3 py-1 text-meta transition-colors duration-quick ${by === b ? "border-ink bg-ink text-canvas" : "border-line hover:border-ink"}`}>
            {b === "band" ? "Experience" : b[0].toUpperCase() + b.slice(1)}
          </button>
        ))}
      </div>
      <ul className="grid gap-1.5">
        {rows.map(([label, v]) => (
          <li key={label} className="grid grid-cols-[minmax(0,12rem)_4.5rem_minmax(0,1fr)] items-center gap-3 text-body">
            <span className="truncate">{label}</span>
            <span className="text-right font-mono text-meta">{n(v)}</span>
            <span aria-hidden className="h-1.5 overflow-hidden rounded-full bg-line">
              <span className="block h-full rounded-full bg-accent" style={{ width: `${(v / max) * 100}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

function Runs({ o }: { o: Overview }) {
  const errors = Object.entries(o.pipeline.latest_errors);
  if (!o.pipeline.runs.length) return <p className="text-body text-muted">No runs yet.</p>;
  return (
    <>
      <table className="w-full text-meta">
        <thead><tr className="text-left text-muted"><th className="py-1 font-medium">When</th><th className="font-medium">New</th><th className="font-medium">Closed</th><th className="font-medium">Failed</th></tr></thead>
        <tbody className="font-mono">
          {o.pipeline.runs.map((r) => (
            <tr key={r.finished_at} className="border-t border-line">
              <td className="py-1 font-sans">{ago(r.finished_at)}</td><td>{n(r.jobs_new)}</td><td>{n(r.jobs_closed)}</td>
              <td className={r.companies_failed ? "text-card-fail" : ""}>{n(r.companies_failed)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {errors.length > 0 && (
        <details className="group mt-3">
          <summary className="flex cursor-pointer list-none items-center gap-1 text-meta font-medium">
            <ChevronRight aria-hidden className="size-4 transition-transform duration-quick group-open:rotate-90" />
            Latest run&apos;s errors ({errors.length})
          </summary>
          <ul className="mt-2 grid gap-1 text-meta">
            {errors.map(([company, msg]) => <li key={company}><span className="font-medium">{company}</span> <span className="text-muted">{msg}</span></li>)}
          </ul>
        </details>
      )}
    </>
  );
}

const EMPTY: NewJob = { company: "", title: "", url: "", location_raw: "", description_text: "" };

function AddJob() {
  const [form, setForm] = useState<NewJob>(EMPTY);
  const [jobs, setJobs] = useState<ManualJob[] | null>(null);
  const [state, setState] = useState<{ kind: "idle" | "saving" } | { kind: "error" | "done"; text: string }>({ kind: "idle" });
  const refresh = useCallback(() => { manualJobs().then((r) => setJobs(r.jobs)).catch(() => setJobs([])); }, []);
  useEffect(refresh, [refresh]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState({ kind: "saving" });
    try {
      const job = await addJob(form);
      setForm(EMPTY);
      setState({ kind: "done", text: `Added ${job.company}: ${job.title}. It's listed after the next pipeline run.` });
      refresh();
    } catch (err) {
      setState({ kind: "error", text: (err as Error).message });
    }
  };
  const close = async (id: number) => { await closeJob(id).catch(() => {}); refresh(); };
  const field = (k: keyof NewJob) => ({ value: form[k], onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value }) });
  const input = "mt-1 w-full rounded-md border border-line bg-canvas px-3 py-2 text-body outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent/40";

  return (
    <Card title="Add a job by hand" className="mt-4">
      <form onSubmit={submit} className="grid gap-4 lg:grid-cols-2">
        <div className="grid content-start gap-3">
          <label className="text-meta font-medium">Company<input required maxLength={120} className={input} {...field("company")} /></label>
          <label className="text-meta font-medium">Title<input required maxLength={200} className={input} {...field("title")} /></label>
          <label className="text-meta font-medium">Link to the posting<input required type="url" pattern="https?://.+" maxLength={2000} placeholder="https://" className={input} {...field("url")} /></label>
          <label className="text-meta font-medium">Location<input maxLength={200} placeholder="Bengaluru, India" className={input} {...field("location_raw")} /></label>
        </div>
        <div className="grid content-start gap-3">
          <label className="text-meta font-medium">Description <span className="font-normal text-muted">(paste the whole posting: the years and skills are read from it)</span>
            <textarea required maxLength={60000} rows={9} className={input} {...field("description_text")} />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={state.kind === "saving"}
              className="rounded-md bg-ink px-4 py-2 text-body font-medium text-canvas transition-transform duration-quick active:scale-[0.98] disabled:opacity-60">
              {state.kind === "saving" ? "Adding…" : "Add job"}
            </button>
            <p role="status" className={`text-meta ${state.kind === "error" ? "text-card-fail" : "text-muted"}`}>
              {state.kind === "done" || state.kind === "error" ? state.text : "Listed after the next pipeline run, labelled like every job."}
            </p>
          </div>
        </div>
      </form>
      <h3 className="mt-6 mb-2 text-meta font-medium uppercase tracking-wide text-muted">Added by hand</h3>
      {!jobs ? <p className="text-body text-muted">Loading…</p> : !jobs.length ? <p className="text-body text-muted">None yet.</p> : (
        <ul className="grid">
          {jobs.map((j) => (
            <li key={j.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 border-t border-line py-2 text-body sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_5rem_4rem_3.5rem]">
              <span className="truncate font-medium">{j.company}</span>
              <a href={j.url} target="_blank" rel="noreferrer" className="truncate hover:underline max-sm:col-span-3 max-sm:row-start-2">{j.title}</a>
              <span className="text-meta text-muted max-sm:hidden">{shortDate(j.added_at)}</span>
              <span className={`text-meta ${j.status === "open" ? "text-card-pass" : "text-muted"}`}>{j.status}</span>
              {j.status === "open"
                ? <button type="button" onClick={() => close(j.id)} className="text-meta font-medium text-accent-text underline-offset-2 hover:underline">Close</button>
                : <span />}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
