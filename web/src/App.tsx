import { useCallback, useEffect, useState } from "react";
import { fetchJobs, fetchMeta, type Family, type Filters, type JobSummary, type Experience, type Meta } from "./api";
import { JobCard } from "./JobCard";
import { timeAgo } from "./format";

// "0–N yrs" = fresher roles plus any role whose stated minimum is within N years.
const EXPERIENCE: { id: Experience; label: string }[] = [
  { id: "fresher", label: "Fresher" },
  { id: "0-1", label: "0–1 yrs" },
  { id: "0-2", label: "0–2 yrs" },
  { id: "0-3", label: "0–3 yrs" },
  { id: "0-5", label: "0–5 yrs" },
  { id: "unstated", label: "Not stated" },
  { id: "all", label: "All levels" },
];
const EXPERIENCE_IDS = EXPERIENCE.map((x) => x.id) as string[];

// Plain SWE roles that passed the Python + AI/ML check are grouped under AI / ML by the API.
const FAMILY_OPTIONS: Record<Family, string> = { ai_ml: "AI / ML", backend: "Python backend", mobile: "Android / React Native" };

// Old links used ?view=fresher|maybe|new or ?level=; they still open sensible filters.
const initialFilters = (): Pick<Filters, "experience" | "posted"> => {
  const params = new URLSearchParams(location.search);
  const view = params.get("view");
  const posted = params.get("posted") === "24h" || view === "new" ? "24h" : "any";
  const exp = params.get("experience");
  if (exp && EXPERIENCE_IDS.includes(exp)) return { experience: exp as Experience, posted };
  // Default to every level: many entry-level posts state no years, so the reader picks the range.
  if (view === "fresher" || params.get("level") === "fresher") return { experience: "fresher", posted };
  return { experience: view === "maybe" || view === "new" ? "0-2" : "all", posted };
};

export function App() {
  const [filters, setFilters] = useState<Filters>({ ...initialFilters(), q: "", company: "", country: "", city: "", family: "", includeIneligible: false, location: "" });
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
    url.searchParams.delete("view");
    url.searchParams.delete("level");
    url.searchParams.set("experience", filters.experience);
    url.searchParams.set("posted", filters.posted);
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

    const filtered = Boolean(filters.q || filters.company || filters.country || filters.city || filters.family || filters.location || filters.posted !== "any");

  return (
    <div className="page">
      <header className="masthead">
        <h1>Jobs</h1>
        {meta?.last_run && (
          <p className="masthead__status">
            Updated {timeAgo(meta.last_run.finished_at)} from {meta.last_run.companies_ok} company boards
            {meta.last_run.companies_failed > 0 && `, ${meta.last_run.companies_failed} unreachable`}.
          </p>
        )}
      </header>

      <form className="panel" role="search" onSubmit={(e) => e.preventDefault()}>
        <label className="search">
          <span className="visually-hidden">Search titles and companies</span>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search titles and companies, e.g. LLM, Sarvam" />
        </label>
        <div className="filters">
          <label className="field">
            <span>Experience</span>
            <select
              value={filters.experience}
              onChange={(e) => {
                setOpenId(null);
                setFilters((f) => ({ ...f, experience: e.target.value as Experience }));
              }}
            >
              {EXPERIENCE.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.label}
                  {meta && x.id === "fresher" ? ` (${meta.counts.fresher})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Role</span>
            <select
              value={filters.family}
              onChange={(e) => setFilters((f) => ({ ...f, family: e.target.value as Filters["family"] }))}
            >
              <option value="">All roles</option>
              {(Object.keys(FAMILY_OPTIONS) as Family[]).map((id) => (
                <option key={id} value={id}>
                  {FAMILY_OPTIONS[id]}
                  {meta ? ` (${meta.families[id] ?? 0})` : ""}
                </option>
              ))}
            </select>
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
            <span>Country</span>
            <select
              value={filters.country}
              // A city belongs to one country, so changing country clears it.
              onChange={(e) => setFilters((f) => ({ ...f, country: e.target.value, city: "" }))}
            >
              <option value="">Any country</option>
              {meta?.countries.map((c) => (
                <option key={c.country} value={c.country}>
                  {c.country} ({c.n})
                </option>
              ))}
            </select>
          </label>
          {filters.country === "India" && meta && meta.cities.length > 0 && (
            <label className="field">
              <span>City</span>
              <select value={filters.city} onChange={(e) => setFilters((f) => ({ ...f, city: e.target.value }))}>
                <option value="">Any city</option>
                {meta.cities.map((c) => (
                  <option key={c.city} value={c.city}>
                    {c.city} ({c.n})
                  </option>
                ))}
              </select>
            </label>
          )}
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
          <label className="field">
            <span>Posted</span>
            <select
              value={filters.posted}
              onChange={(e) => setFilters((f) => ({ ...f, posted: e.target.value as Filters["posted"] }))}
            >
              <option value="any">Any time</option>
              <option value="24h">New in the last 24 hours{meta ? ` (${meta.counts.new})` : ""}</option>
            </select>
          </label>
          <label className="field field--check">
            <input
              type="checkbox"
              checked={filters.includeIneligible}
              onChange={(e) => setFilters((f) => ({ ...f, includeIneligible: e.target.checked }))}
            />
            <span>Include roles outside my locations</span>
          </label>
        </div>
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
          <p className="notice">{filtered ? "No roles match these filters. Clear the search, or pick another company, country or city." : filters.experience === "fresher"
              ? "No fresher roles match right now. Try 0–1 or 0–2 yrs."
              : "No roles match this experience range right now."}</p>
        )}
        <ol className="cards" aria-busy={loading}>
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} open={openId === job.id} onToggle={() => setOpenId(openId === job.id ? null : job.id)} />
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
