"use client";
// /applications (docs/decisions.md, 2026-11-11 layout): every job the person saved or applied
// to. A filter bar on top, then the same applications as a board or as a list. The list takes
// over by default once there are too many for a board to stay readable.
import dynamic from "next/dynamic";
import Link from "next/link";
import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AccountShell, NotSetUp } from "@/components/account/AccountShell";
import { Kanban, stageLabel, type CardInfo } from "@/components/board/Kanban";
import { CompanyMark } from "@/components/CompanyMark";
import { ViewSwitch } from "@/components/shell/PageBar";
import { nextStep } from "@/lib/board";
import { shortDate } from "@/lib/format";
import { authConfigured } from "@/lib/supabase";
import { moveJob, recentChecks, recentTailored, removeJob, trackedJobs, STAGES, type Stage, type TailoredRow, type Tracked, type Verdict } from "@/lib/tracker";
import { useProfile } from "@/lib/useProfile";

// Reopening a tailored resume (and pdf-lib) loads only when asked.
const TailorDialog = dynamic(() => import("@/components/TailorDialog").then((m) => m.TailorDialog), { ssr: false });

type View = "board" | "list";
const VIEWS = [{ v: "board", label: "Board" }, { v: "list", label: "List" }] as const;
const VIEW_KEY = "aventra.applications.view";
const LIST_FROM = 40; // more applications than this open as a list unless the person chose a view
const PER_PAGE = 20;
const DOT: Record<Stage, string> = {
  saved: "border-muted", applied: "border-accent bg-[linear-gradient(90deg,var(--accent)_50%,transparent_50%)]",
  interview: "border-accent bg-accent", offer: "border-card-pass bg-card-pass", rejected: "border-line bg-line",
};

export function Applications() {
  const load = useProfile();
  if (!authConfigured) return <AccountShell title="Applications"><NotSetUp /></AccountShell>;
  if (load.kind === "error") return <AccountShell title="Applications"><p role="alert" className="text-body text-muted">Couldn&apos;t open your applications: {load.message}</p></AccountShell>;
  if (load.kind === "loading") return <AccountShell title="Applications" wide><div aria-busy="true" aria-label="Loading your applications" className="h-72 animate-pulse rounded-lg bg-surface" /></AccountShell>;
  return <Tracker />;
}

function Tracker() {
  const [items, setItems] = useState<Tracked[] | "error" | null>(null);
  const [verdicts, setVerdicts] = useState<Record<string, Verdict["fit"]>>({});
  const [resumes, setResumes] = useState<Record<string, TailoredRow>>({});
  const [open, setOpen] = useState<TailoredRow | null>(null);
  const [chosen, setChosen] = useState<View | null>(null);
  const [f, setF] = useState({ due: false, stage: "" as Stage | "", company: "", tailored: false, q: "" });
  const [page, setPage] = useState(1);

  const reload = useCallback(() => { trackedJobs().then(setItems).catch(() => setItems("error")); }, []);
  useEffect(() => {
    reload();
    // The latest Gemini verdict and the latest tailored resume per job, when there are any.
    recentChecks(50).then((cs) => setVerdicts(Object.fromEntries([...cs].reverse().map((c) => [c.job_id, c.result.fit])))).catch(() => {});
    recentTailored(50).then((rs) => setResumes(Object.fromEntries([...rs].reverse().map((r) => [r.job_id, r])))).catch(() => {});
    // Read once from localStorage, which only exists in the browser, so it can't be initial state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { const v = localStorage.getItem(VIEW_KEY); if (v === "board" || v === "list") setChosen(v); } catch {}
  }, [reload]);

  const all = useMemo(() => (Array.isArray(items) ? items : []), [items]);
  const steps = useMemo(() => new Map(all.map((t) => [t.id, nextStep(t)])), [all]);
  const due = all.filter((t) => steps.get(t.id)!.due).length;
  const companies = useMemo(() => [...new Set(all.map((t) => t.jobs?.companies?.name ?? "").filter(Boolean))].sort(), [all]);
  const shown = useMemo(() => {
    const q = f.q.trim().toLowerCase();
    return all.filter((t) =>
      (!f.due || steps.get(t.id)!.due) && (!f.stage || t.status === f.stage) && (!f.company || t.jobs?.companies?.name === f.company)
      && (!f.tailored || t.job_id in resumes)
      && (!q || `${t.jobs?.title} ${t.jobs?.companies?.name}`.toLowerCase().includes(q)));
  }, [all, f, steps, resumes]);
  const view: View = chosen ?? (all.length > LIST_FROM ? "list" : "board");
  const filtered = f.due || f.stage || f.company || f.tailored || f.q.trim();
  const set = (patch: Partial<typeof f>) => { setF((x) => ({ ...x, ...patch })); setPage(1); };

  async function move(t: Tracked, status: Stage) {
    setItems(all.map((x) => (x.id === t.id ? { ...x, status, updated_at: new Date().toISOString(), applied_at: x.applied_at ?? (status !== "saved" ? new Date().toISOString() : null) } : x)));
    try { await moveJob(t.id, status); } catch { reload(); }
  }
  async function remove(t: Tracked) {
    setItems(all.filter((x) => x.id !== t.id));
    try { await removeJob(t.id); } catch { reload(); }
  }
  const info = (t: Tracked): CardInfo => ({
    step: steps.get(t.id) ?? nextStep(t), fit: verdicts[t.job_id],
    onResume: resumes[t.job_id] ? () => setOpen(resumes[t.job_id]) : undefined,
  });

  const sub = items === null ? "Loading…" : items === "error" ? "" : `${all.length} tracked${due ? `, ${due} ${due === 1 ? "needs" : "need"} you this week` : ""}`;
  return (
    <>
      <AccountShell title="Applications" sub={sub} wide
        actions={<ViewSwitch label="View" options={VIEWS} value={view} onChange={(v) => { setChosen(v); try { localStorage.setItem(VIEW_KEY, v); } catch {} }} />}>
        {items === "error" ? <p role="alert" className="text-body text-muted">Couldn&apos;t load your applications. <button type="button" className="font-medium text-accent-text underline" onClick={reload}>Retry</button></p>
          : items === null ? <div aria-busy="true" className="h-72 animate-pulse rounded-lg bg-surface" />
          : all.length === 0 ? (
            <p className="text-body text-muted">
              Nothing tracked yet. Open a job and press Save, and it starts here. <Link href="/" className="font-medium text-accent-text underline underline-offset-2">See open jobs</Link>
            </p>
          ) : (
            <>
              <div className="-mx-4 -mt-8 mb-6 flex items-center gap-2 overflow-x-auto border-b border-line px-4 py-2.5 [scrollbar-width:none] lg:-mx-6 lg:-mt-10 lg:px-6">
                <Toggle on={f.due} onClick={() => set({ due: !f.due })}>Needs me <span key={due} className="tick font-mono">{due}</span></Toggle>
                <Pick label="Stage" value={f.stage} onChange={(v) => set({ stage: v as Stage | "" })}>
                  <option value="">All stages</option>
                  {STAGES.map((s) => <option key={s.v} value={s.v}>{stageLabel(s.v)}</option>)}
                </Pick>
                <Pick label="Company" value={f.company} onChange={(v) => set({ company: v })}>
                  <option value="">Any company</option>
                  {companies.map((c) => <option key={c} value={c}>{c}</option>)}
                </Pick>
                <Toggle on={f.tailored} onClick={() => set({ tailored: !f.tailored })}>With a tailored resume</Toggle>
                {filtered && <button type="button" onClick={() => set({ due: false, stage: "", company: "", tailored: false, q: "" })} className="shrink-0 px-1 text-meta font-medium text-accent-text hover:underline">Clear</button>}
                <label className="ml-auto flex h-8 w-56 shrink-0 items-center gap-2 rounded-md border border-line bg-card px-2.5 text-meta text-muted focus-within:border-ink/50">
                  <Search aria-hidden className="size-3.5" />
                  <input type="search" value={f.q} onChange={(e) => set({ q: e.target.value })} placeholder={`Search ${all.length} applications`} aria-label="Search your applications"
                    className="w-full bg-transparent text-ink outline-none placeholder:text-muted" />
                </label>
              </div>
              {shown.length === 0 ? <p className="text-body text-muted">No application matches these filters.</p>
                // A new key per view: switching cross-fades, so it reads as the same data re-drawn.
                : view === "board" ? <div key="board" className="list-in"><Kanban items={shown} info={info} onMove={move} onRemove={remove} /></div>
                : <div key="list" className="list-in"><List items={shown} info={info} page={page} onPage={setPage} onMove={move} /></div>}
            </>
          )}
      </AccountShell>
      {open && <TailorDialog jobId={open.job_id} title={open.jobs?.title ?? ""} company={open.jobs?.companies?.name ?? ""} initial={open.result} onClose={() => setOpen(null)} />}
    </>
  );
}

const chip = "press inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border px-2.5 text-meta font-medium duration-quick";

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" aria-pressed={on} onClick={onClick} className={`${chip} ${on ? "border-accent bg-accent text-on-accent" : "border-line hover:bg-surface"}`}>{children}</button>;
}

function Pick({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
      className={`${chip} cursor-pointer bg-transparent outline-none [field-sizing:content] focus:border-ink ${value ? "border-ink bg-selected" : "border-line hover:bg-surface"}`}>
      {children}
    </select>
  );
}

/** One row per application, what needs the person first, 20 a page. */
function List({ items, info, page, onPage, onMove }: {
  items: Tracked[]; info: (t: Tracked) => CardInfo; page: number; onPage: (p: number) => void; onMove: (t: Tracked, to: Stage) => void;
}) {
  const sorted = useMemo(() => [...items].sort((a, b) =>
    Number(info(b).step.due) - Number(info(a).step.due) || Number(a.status === "rejected") - Number(b.status === "rejected")
    || Date.parse(b.updated_at) - Date.parse(a.updated_at)),
  // `info` is rebuilt each render from the same data as `items`; sorting again on it would be wasted work.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [items]);
  const pages = Math.max(Math.ceil(sorted.length / PER_PAGE), 1);
  const p = Math.min(page, pages);
  const rows = sorted.slice((p - 1) * PER_PAGE, p * PER_PAGE);
  return (
    <>
      <div role="table" aria-label="Applications" className="-mx-4 lg:-mx-6">
        <div role="row" className="hidden grid-cols-[12px_28px_minmax(0,1.6fr)_120px_minmax(0,1.2fr)_130px_64px] items-center gap-3.5 border-b border-line bg-surface px-6 py-2 text-caption font-semibold text-muted md:grid">
          <span /><span /><span role="columnheader">Job</span><span role="columnheader">Stage</span><span role="columnheader">Next step</span>
          <span role="columnheader">Resume</span><span role="columnheader" className="text-right">Updated</span>
        </div>
        {rows.map((t) => {
          const { step, onResume } = info(t);
          const company = t.jobs?.companies?.name ?? "";
          return (
            <div key={t.id} role="row"
              className={`grid grid-cols-[12px_28px_minmax(0,1fr)_auto] items-center gap-x-3.5 gap-y-1 border-b border-line px-4 py-2.5 text-body transition-colors duration-quick hover:bg-surface md:grid-cols-[12px_28px_minmax(0,1.6fr)_120px_minmax(0,1.2fr)_130px_64px] md:px-6 ${t.status === "rejected" ? "text-muted" : ""}`}>
              <span aria-hidden className={`size-2.5 rounded-full border-2 ${DOT[t.status]}`} />
              <CompanyMark company={company} size="sm" />
              <div role="cell" className="min-w-0">
                <a href={t.jobs?.url} target="_blank" rel="noopener" className="block truncate font-medium hover:underline">{t.jobs?.title}</a>
                <span className="block truncate text-meta text-muted">{company}</span>
              </div>
              <div role="cell">
                <select aria-label={`Stage of ${t.jobs?.title ?? "job"}`} value={t.status} onChange={(e) => onMove(t, e.target.value as Stage)}
                  className="h-7 cursor-pointer rounded-sm border border-transparent bg-transparent text-body outline-none hover:border-line focus:border-ink">
                  {STAGES.map((s) => <option key={s.v} value={s.v}>{stageLabel(s.v)}</option>)}
                </select>
              </div>
              <div role="cell" className="col-span-2 col-start-3 truncate md:col-span-1 md:col-start-auto">
                <span className={step.due ? "rounded-sm bg-mark px-1 font-medium" : "text-muted"}>{step.text}</span>
              </div>
              <div role="cell" className="text-meta max-md:hidden">
                {onResume ? <button type="button" onClick={onResume} className="font-medium text-accent-text underline underline-offset-2">Tailored</button> : <span className="text-muted">Base resume</span>}
              </div>
              <div role="cell" className="text-right font-mono text-caption text-muted max-md:hidden">{shortDate(t.updated_at)}</div>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-2.5 pt-4 text-meta text-muted">
        <span>{(p - 1) * PER_PAGE + 1} to {Math.min(p * PER_PAGE, sorted.length)} of {sorted.length}, what needs you first</span>
        <button type="button" disabled={p <= 1} onClick={() => onPage(p - 1)} className={`${chip} ml-auto border-line hover:bg-surface disabled:opacity-40`}>Previous</button>
        <button type="button" disabled={p >= pages} onClick={() => onPage(p + 1)} className={`${chip} border-line hover:bg-surface disabled:opacity-40`}>Next {PER_PAGE}</button>
      </div>
    </>
  );
}
