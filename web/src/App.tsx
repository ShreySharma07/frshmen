import { useEffect, useRef, useState } from "react";
import { fetchJobs, fetchMeta, type Experience, type Filters, type JobSummary, type Meta, type Posted, type Role } from "./api";
import { JobCard } from "./JobCard";
import { Pager } from "./Pager";
import { timeAgo } from "./format";

// "0–N yrs" = fresher roles plus any role whose stated minimum is within N years.
const EXPERIENCE: { id: Experience; label: string }[] = [
  { id: "all", label: "All levels" },
  { id: "fresher", label: "Fresher / entry level" },
  { id: "internship", label: "Internships" },
  { id: "0-1", label: "0–1 yrs" },
  { id: "0-2", label: "0–2 yrs" },
  { id: "0-3", label: "0–3 yrs" },
  { id: "0-5", label: "0–5 yrs" },
  { id: "unstated", label: "Years not stated" },
  { id: "experienced", label: "Experienced" },
];

// Plain SWE roles that passed the Python + AI/ML check are grouped under AI / ML by the API.
const ROLES: { id: Role; label: string }[] = [
  { id: "all", label: "All roles" },
  { id: "target", label: "My target roles" },
  { id: "ai_ml", label: "AI / ML" },
  { id: "backend", label: "Python backend" },
  { id: "mobile", label: "Android / React Native" },
];

const POSTED: { id: Posted; label: string }[] = [
  { id: "any", label: "Any time" },
  { id: "24h", label: "New in the last 24 hours" },
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
];

const DEFAULTS: Filters = {
  experience: "all", role: "all", posted: "any", q: "", company: "", country: "", city: "", eligibleOnly: false, location: "",
};

const pick = <T extends string>(value: string | null, options: { id: T }[], fallback: T): T =>
  options.some((o) => o.id === value) ? (value as T) : fallback;

// Filters and page live in the URL, so a filtered view can be bookmarked or shared.
// Old links (?view=fresher, ?experience=0-2) still open the matching view.
function fromUrl(): { filters: Filters; page: number } {
  const p = new URLSearchParams(location.search);
  const legacy = p.get("view") === "fresher" ? "fresher" : p.get("view") === "new" ? "all" : null;
  return {
    filters: {
      ...DEFAULTS,
      experience: pick(p.get("experience") ?? legacy, EXPERIENCE, "all"),
      role: pick(p.get("role"), ROLES, "all"),
      posted: p.get("view") === "new" ? "24h" : pick(p.get("posted"), POSTED, "any"),
      q: p.get("q") ?? "",
      company: p.get("company") ?? "",
      country: p.get("country") ?? "",
      city: p.get("city") ?? "",
      eligibleOnly: p.get("mine") === "1",
      location: (["remote", "hybrid", "onsite"].includes(p.get("mode") ?? "") ? p.get("mode") : "") as Filters["location"],
    },
    page: Math.max(1, Number(p.get("page")) || 1),
  };
}

function toUrl(filters: Filters, page: number) {
  const p = new URLSearchParams();
  const set = (k: string, v: string, skip: string) => v !== skip && p.set(k, v);
  set("experience", filters.experience, "all");
  set("role", filters.role, "all");
  set("posted", filters.posted, "any");
  set("q", filters.q, "");
  set("company", filters.company, "");
  set("country", filters.country, "");
  set("city", filters.city, "");
  set("mode", filters.location, "");
  if (filters.eligibleOnly) p.set("mine", "1");
  if (page > 1) p.set("page", String(page));
  const qs = p.toString();
  history.replaceState(null, "", `${location.pathname}${qs ? `?${qs}` : ""}`);
}

export function App() {
  const initial = useRef(fromUrl()).current;
  const [filters, setFilters] = useState<Filters>(initial.filters);
  const [page, setPage] = useState(initial.page);
  const [query, setQuery] = useState(initial.filters.q);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState<{ key: string; n: number; pages: number } | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const top = useRef<HTMLElement>(null);

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

  const change = (patch: Partial<Filters>) => {
    setOpenId(null);
    setPage(1);
    setFilters((f) => ({ ...f, ...patch }));
  };

  // The total is counted once per set of filters, not on every page turn: counting reads every match.
  const filterKey = JSON.stringify(filters);
  useEffect(() => {
    const ctrl = new AbortController();
    const needTotal = total?.key !== filterKey;
    setLoading(true);
    setError(null);
    fetchJobs(filters, page, needTotal, ctrl.signal)
      .then((res) => {
        setJobs(res.jobs);
        setHasMore(res.has_more);
        if (res.total !== undefined) setTotal({ key: filterKey, n: res.total, pages: res.pages ?? 1 });
      })
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message))
      .finally(() => !ctrl.signal.aborted && setLoading(false));
    toUrl(filters, page);
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey, page, retry]);

  const goTo = (n: number) => {
    setOpenId(null);
    setPage(n);
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const filtered = filterKey !== JSON.stringify({ ...DEFAULTS, q: filters.q }) || Boolean(filters.q);
  const shownTotal = total?.key === filterKey ? total : null;
  const levelCount = (id: Experience) =>
    !meta ? "" : id === "fresher" ? ` (${meta.levels.fresher})` : id === "experienced" ? ` (${meta.levels.experienced})`
      : id === "internship" ? ` (${meta.internships})` : id === "all" ? ` (${meta.total})` : "";

  return (
    <div className="page">
      <header className="masthead" ref={top}>
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
            <select value={filters.experience} onChange={(e) => change({ experience: e.target.value as Experience })}>
              {EXPERIENCE.map((x) => (
                <option key={x.id} value={x.id}>{x.label}{levelCount(x.id)}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Role</span>
            <select value={filters.role} onChange={(e) => change({ role: e.target.value as Role })}>
              {ROLES.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                  {meta && r.id !== "all" ? ` (${meta.roles[r.id] ?? 0})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Company</span>
            <select value={filters.company} onChange={(e) => change({ company: e.target.value })}>
              <option value="">All companies</option>
              {meta?.companies.map((c) => (
                <option key={c.company} value={c.company}>{c.company} ({c.n})</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Country</span>
            {/* A city belongs to one country, so changing country clears it. */}
            <select value={filters.country} onChange={(e) => change({ country: e.target.value, city: "" })}>
              <option value="">Any country</option>
              {meta?.countries.map((c) => (
                <option key={c.country} value={c.country}>{c.country} ({c.n})</option>
              ))}
            </select>
          </label>
          {filters.country === "India" && meta && meta.cities.length > 0 && (
            <label className="field">
              <span>City</span>
              <select value={filters.city} onChange={(e) => change({ city: e.target.value })}>
                <option value="">Any city</option>
                {meta.cities.map((c) => (
                  <option key={c.city} value={c.city}>{c.city} ({c.n})</option>
                ))}
              </select>
            </label>
          )}
          <label className="field">
            <span>Work mode</span>
            <select value={filters.location} onChange={(e) => change({ location: e.target.value as Filters["location"] })}>
              <option value="">Any</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
          </label>
          <label className="field">
            <span>Posted</span>
            <select value={filters.posted} onChange={(e) => change({ posted: e.target.value as Posted })}>
              {POSTED.map((x) => (
                <option key={x.id} value={x.id}>{x.label}</option>
              ))}
            </select>
          </label>
          <label className="field field--check">
            <input type="checkbox" checked={filters.eligibleOnly} onChange={(e) => change({ eligibleOnly: e.target.checked })} />
            <span>Only where I can work (India, remote, or visa sponsored)</span>
          </label>
          {filtered && (
            <button type="button" className="button button--quiet" onClick={() => { setQuery(""); change(DEFAULTS); }}>
              Clear filters
            </button>
          )}
        </div>
      </form>

      <main>
        <p className="results" aria-live="polite">
          {shownTotal ? `${shownTotal.n.toLocaleString()} ${shownTotal.n === 1 ? "job" : "jobs"}` : " "}
          {shownTotal && shownTotal.pages > 1 && ` · page ${page} of ${shownTotal.pages}`}
        </p>
        {error && (
          <div className="notice notice--error" role="alert">
            <p>Couldn't load jobs: {error}.</p>
            <button className="button" onClick={() => setRetry((n) => n + 1)}>Try again</button>
          </div>
        )}
        {!error && !loading && jobs.length === 0 && (
          <p className="notice">{filtered ? "No jobs match these filters. Clear some of them to see more." : "No open jobs right now."}</p>
        )}
        <ol className="cards" aria-busy={loading}>
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} open={openId === job.id} fitCheck={Boolean(meta?.fit_check)}
                     onToggle={() => setOpenId(openId === job.id ? null : job.id)} />
          ))}
        </ol>
        {loading && <p className="notice">Loading jobs…</p>}
        <Pager page={page} pages={shownTotal?.pages ?? (hasMore ? page + 1 : page)} hasMore={hasMore} onPage={goTo} />
      </main>
    </div>
  );
}
