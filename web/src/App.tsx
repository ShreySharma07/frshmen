import { useCallback, useEffect, useState } from "react";
import { fetchJobs, fetchMeta, type Filters, type JobSummary, type Meta, type View } from "./api";
import { JobRow } from "./JobRow";
import { timeAgo } from "./format";

const VIEWS: { id: View; label: string; empty: string }[] = [
  {
    id: "fresher",
    label: "Fresher",
    empty: "No fresher roles match right now. Maybe has roles that state no experience requirement.",
  },
  {
    id: "maybe",
    label: "Maybe",
    empty: "Nothing here. Maybe holds roles with no stated experience or a 1–2 year ask.",
  },
  {
    id: "new",
    label: "New today",
    empty: "No new fresher or maybe roles in the last 24 hours.",
  },
];

const initialView = (): View => {
  const v = new URLSearchParams(location.search).get("view");
  return v === "maybe" || v === "new" ? v : "fresher";
};

export function App() {
  const [filters, setFilters] = useState<Filters>({ view: initialView(), q: "", company: "", location: "" });
  const [query, setQuery] = useState("");
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchMeta(ctrl.signal).then(setMeta).catch(() => setMeta(null));
    return () => ctrl.abort();
  }, []);

  // Search waits for a pause in typing so each keystroke doesn't spend D1 reads.
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => (f.q === query ? f : { ...f, q: query })), 300);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    fetchJobs(filters, 0, ctrl.signal)
      .then((page) => {
        setJobs(page.jobs);
        setHasMore(page.has_more);
      })
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message))
      .finally(() => !ctrl.signal.aborted && setLoading(false));
    const url = new URL(location.href);
    url.searchParams.set("view", filters.view);
    history.replaceState(null, "", url);
    return () => ctrl.abort();
  }, [filters]);

  const loadMore = useCallback(() => {
    setLoading(true);
    fetchJobs(filters, jobs.length)
      .then((page) => {
        setJobs((prev) => [...prev, ...page.jobs]);
        setHasMore(page.has_more);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters, jobs.length]);

  const view = VIEWS.find((v) => v.id === filters.view)!;
  const filtered = Boolean(filters.q || filters.company || filters.location);

  return (
    <div className="page">
      <header className="masthead">
        <h1>frshmen</h1>
        <p className="masthead__line">
          Fresher-level AI/ML and Python backend roles. Each one shows the sentence that decided it.
        </p>
        {meta?.last_run && (
          <p className="masthead__status">
            Updated {timeAgo(meta.last_run.finished_at)} from {meta.last_run.companies_ok} company boards
            {meta.last_run.companies_failed > 0 && `, ${meta.last_run.companies_failed} unreachable`}.
          </p>
        )}
      </header>

      <nav className="tabs" aria-label="Job views">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            className="tab"
            aria-current={filters.view === v.id ? "page" : undefined}
            onClick={() => {
              setOpenId(null);
              setFilters((f) => ({ ...f, view: v.id }));
            }}
          >
            {v.label}
            {meta && <span className="tab__count">{meta.counts[v.id]}</span>}
          </button>
        ))}
      </nav>

      <form className="filters" role="search" onSubmit={(e) => e.preventDefault()}>
        <label className="field field--grow">
          <span>Search titles and companies</span>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. LLM, Sarvam" />
        </label>
        <label className="field">
          <span>Company</span>
          <select value={filters.company} onChange={(e) => setFilters((f) => ({ ...f, company: e.target.value }))}>
            <option value="">All companies</option>
            {meta?.companies.map((c) => (
              <option key={c.company} value={c.company}>
                {c.company} ({c.n})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Work mode</span>
          <select
            value={filters.location}
            onChange={(e) => setFilters((f) => ({ ...f, location: e.target.value as Filters["location"] }))}
          >
            <option value="">Any</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">Onsite</option>
          </select>
        </label>
      </form>

      <main>
        {error && (
          <div className="notice notice--error" role="alert">
            <p>Couldn't load jobs: {error}.</p>
            <button className="button" onClick={() => setFilters((f) => ({ ...f }))}>
              Try again
            </button>
          </div>
        )}
        {!error && !loading && jobs.length === 0 && (
          <p className="notice">{filtered ? "No roles match these filters. Clear the search or pick another company." : view.empty}</p>
        )}
        <ol className="jobs" aria-busy={loading}>
          {jobs.map((job) => (
            <JobRow key={job.id} job={job} open={openId === job.id} onToggle={() => setOpenId(openId === job.id ? null : job.id)} />
          ))}
        </ol>
        {loading && <p className="notice">Loading roles…</p>}
        {hasMore && !loading && (
          <button className="button button--more" onClick={loadMore}>
            Show more roles
          </button>
        )}
      </main>
    </div>
  );
}
