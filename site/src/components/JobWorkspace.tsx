"use client";
// The job screen: header with search, filter chips, then the list on the left and the selected
// job on the right (a full-screen sheet on phones). The page around it is static; this asks /api
// for jobs once it opens in the browser.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { fetchJob, fetchJobs, fetchMeta, type JobDetail, type JobSummary } from "@/lib/api";
import { DEFAULTS, toApiParams, toSearch, type Filters } from "@/lib/filters";
import { useUrlFilters } from "@/lib/useUrlFilters";
import { FilterBar } from "./FilterBar";
import { JobDetailView } from "./JobDetailView";
import { JobRow } from "./JobRow";
import { SearchBox } from "./SearchBox";

const NEW_SINCE_DAYS = 3; // until visits are remembered (with sign-in), "New" = first seen in the last 3 days

type ListState = { status: "loading" } | { status: "error"; message: string } | { status: "ready" };

export function JobWorkspace() {
  const [filters, navigate] = useUrlFilters();
  const [countries, setCountries] = useState<string[]>([]);

  // Country choices for the Where chip, from the pipeline's per-run snapshot (one cheap request).
  useEffect(() => {
    const ctrl = new AbortController();
    fetchMeta(ctrl.signal).then((m) => setCountries(m.countries.slice(0, 12).map((c) => c.country))).catch(() => {});
    return () => ctrl.abort();
  }, []);
  const onSearch = useCallback((q: string) => { if (filters) navigate({ ...filters, q }, "replace"); }, [filters, navigate]);

  return (
    <>
      <header className="sticky top-0 z-30 h-14 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1280px] items-center gap-4 px-4 lg:px-6">
          {/* eslint-disable-next-line @next/next/no-img-element -- static SVG; next/image needs a loader in export mode */}
          <img src="/kario-wordmark.svg" alt="kario" className="h-[22px] w-auto shrink-0 dark:invert" />
          <div className="ml-auto flex w-full justify-end">
            {filters && <SearchBox value={filters.q} onSearch={onSearch} />}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1280px] pb-4 lg:px-2">
        {filters ? (
          <>
            <FilterBar filters={filters} countries={countries} onChange={(f) => navigate(f)} />
            {/* A new key per filter set starts the results fresh: page 1, first job selected. */}
            <Results key={toSearch(filters)} filters={filters} onClear={() => navigate(DEFAULTS)} />
          </>
        ) : <Skeleton />}
      </main>
    </>
  );
}

function Results({ filters, onClear }: { filters: Filters; onClear: () => void }) {
  const [list, setList] = useState<ListState>({ status: "loading" });
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState(0);
  const [sheetOpen, setSheetOpen] = useState(false); // phones only: details cover the list
  const [details, setDetails] = useState<Record<string, JobDetail | "error">>({});
  // Fixed when the page opens, so a re-render can't flip a row's "New" mark.
  const [newSince] = useState(() => Date.now() - NEW_SINCE_DAYS * 86_400_000);

  // Page 1 (with the total) on open and on retry; later pages append.
  useEffect(() => {
    const ctrl = new AbortController();
    fetchJobs(toApiParams(filters), page, page === 1, ctrl.signal)
      .then((res) => {
        setJobs((prev) => (page === 1 ? res.jobs : [...prev, ...res.jobs]));
        if (res.total != null) setTotal(res.total);
        setHasMore(res.has_more);
        setList({ status: "ready" });
      })
      .catch((e: Error) => { if (e.name !== "AbortError") setList({ status: "error", message: e.message }); });
    return () => ctrl.abort();
  }, [filters, page, attempt]);

  const current = jobs[active];
  const detail = current ? details[current.id] : undefined;

  // Details for the selected job, fetched once and kept.
  useEffect(() => {
    if (!current || details[current.id]) return;
    const ctrl = new AbortController();
    fetchJob(current.id, ctrl.signal)
      .then((d) => setDetails((m) => ({ ...m, [d.id]: d })))
      .catch((e: Error) => { if (e.name !== "AbortError") setDetails((m) => ({ ...m, [current.id]: "error" })); });
    return () => ctrl.abort();
  }, [current, details]);

  // Phones: opening a job pushes a history entry, so the system back gesture closes it.
  const openSheet = useCallback(() => {
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    history.pushState({ sheet: true }, "");
    setSheetOpen(true);
  }, []);
  useEffect(() => {
    const onPop = () => setSheetOpen(false);
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, []);
  const closeSheet = () => (history.state?.sheet ? history.back() : setSheetOpen(false));

  // Keyboard: j/k or arrows move, a applies, Escape closes the sheet.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && e.target.closest("input, textarea, select, [contenteditable]")) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, jobs.length - 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
      else if (e.key === "a" && current) window.open(current.url, "_blank", "noopener");
      else if (e.key === "Escape" && sheetOpen) closeSheet();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });

  // The accent bar slides to the selected row: one element moved with transform (cheap to
  // animate), instead of a bar per row popping in and out.
  const listRef = useRef<HTMLOListElement>(null);
  const [bar, setBar] = useState<{ y: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const row = listRef.current?.children[active] as HTMLElement | undefined;
    if (!row) return;
    setBar({ y: row.offsetTop, h: row.offsetHeight });
    row.scrollIntoView({ block: "nearest" });
  }, [active, jobs]);

  if (list.status === "loading" && jobs.length === 0) return <Skeleton />;
  if (list.status === "error" && jobs.length === 0) return <ErrorLine message={list.message} onRetry={() => { setList({ status: "loading" }); setAttempt((a) => a + 1); }} />;
  if (jobs.length === 0)
    return (
      <p className="px-4 py-8 text-body text-muted lg:px-6">
        No jobs match these filters.{" "}
        <button type="button" className="font-medium text-accent underline" onClick={onClear}>Clear filters</button>
      </p>
    );

  return (
    <div className="grid grid-cols-1 items-start lg:grid-cols-[420px_1fr]">
      <section aria-label="Jobs" className="min-w-0 lg:pr-6">
        <p className="mb-2 px-4 text-meta text-muted" aria-live="polite"><span className="font-mono text-ink">{total ?? jobs.length}</span> {(total ?? jobs.length) === 1 ? "job" : "jobs"} · newest first</p>
        <div className="relative">
          {bar && (
            <span aria-hidden className="pointer-events-none absolute left-0 top-0 hidden w-[3px] rounded-r-sm bg-accent transition-transform duration-move ease-out-soft lg:block"
              style={{ transform: `translateY(${bar.y}px)`, height: bar.h }} />
          )}
          <ol ref={listRef} className="space-y-0.5">
            {jobs.map((j, i) => (
              <JobRow key={j.id} job={j} selected={i === active} isNew={Date.parse(j.first_seen_at) > newSince}
                onSelect={() => { setActive(i); openSheet(); }} />
            ))}
          </ol>
        </div>
        {hasMore && (
          <button type="button" onClick={() => setPage((p) => p + 1)} disabled={list.status === "loading"}
            className="mx-4 mt-4 rounded-md border border-line px-4 py-2 text-meta font-medium transition-colors duration-quick hover:bg-surface disabled:opacity-50">
            {list.status === "loading" ? "Loading…" : "Show 20 more"}
          </button>
        )}
        {list.status === "error" && jobs.length > 0 && <ErrorLine message={list.message} onRetry={() => { setList({ status: "loading" }); setAttempt((a) => a + 1); }} />}
        <p className="mt-4 hidden gap-3 px-4 text-caption text-muted lg:flex">
          <span><Kbd>j</Kbd> <Kbd>k</Kbd> move</span><span><Kbd>a</Kbd> apply</span>
        </p>
      </section>

      <aside aria-live="polite"
        className={`${sheetOpen ? "fixed inset-0 z-40 block overflow-y-auto bg-canvas p-5" : "hidden"} lg:sticky lg:inset-auto lg:top-[72px] lg:z-auto lg:block lg:h-[calc(100vh-88px)] lg:overflow-y-auto lg:border-l lg:border-line lg:bg-transparent lg:px-8 lg:py-1`}>
        {detail === "error" ? <p className="text-body text-muted">Couldn&apos;t load this job.</p>
          : detail ? <JobDetailView job={detail} onBack={closeSheet} />
          : current ? <DetailSkeleton /> : null}
      </aside>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded-sm border border-line bg-surface px-1.5 font-mono text-caption">{children}</kbd>;
}

function ErrorLine({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <p className="px-4 py-6 text-body text-muted">
      Couldn&apos;t load jobs ({message}).{" "}
      <button type="button" className="font-medium text-accent underline" onClick={onRetry}>Retry</button>
    </p>
  );
}

// Loading states: the shape of what's coming, no spinner (docs/briefs/job-list.md).
function Skeleton() {
  return (
    <ol aria-busy="true" aria-label="Loading jobs" className="max-w-[420px] space-y-0.5">
      {Array.from({ length: 6 }, (_, i) => (
        <li key={i} className="px-4 py-3.5">
          <div className="h-3.5 w-3/4 animate-pulse rounded-sm bg-surface" />
          <div className="mt-2 h-3 w-1/2 animate-pulse rounded-sm bg-surface" />
        </li>
      ))}
    </ol>
  );
}

function DetailSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading job" className="space-y-3">
      <div className="h-4 w-1/3 animate-pulse rounded-sm bg-surface" />
      <div className="h-7 w-2/3 animate-pulse rounded-sm bg-surface" />
      <div className="h-40 animate-pulse rounded-lg bg-surface" />
    </div>
  );
}
