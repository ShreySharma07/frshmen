"use client";
// The page itself is static; this component asks /api for today's jobs once the page has opened
// in the browser (the "call this number" box in the magazine).
import { useEffect, useState } from "react";
import { fetchJobs, type JobPage } from "@/lib/api";
import { place, shortDate, years } from "@/lib/format";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; page: JobPage };

export function JobList() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // Abort if the component goes away before the answer arrives, so a late reply can't
    // overwrite newer state.
    const ctrl = new AbortController();
    fetchJobs({ experience: "0-3", role: "target", page: 1, withTotal: true }, ctrl.signal)
      .then((page) => setState({ status: "ready", page }))
      .catch((e: Error) => { if (e.name !== "AbortError") setState({ status: "error", message: e.message }); });
    return () => ctrl.abort();
  }, [attempt]);

  if (state.status === "loading") return <Skeleton />;
  if (state.status === "error")
    return (
      <p className="py-6 text-body text-muted">
        Couldn&apos;t load jobs ({state.message}).{" "}
        <button className="font-medium text-accent underline" onClick={() => { setState({ status: "loading" }); setAttempt((a) => a + 1); }}>
          Retry
        </button>
      </p>
    );

  const { jobs, total } = state.page;
  return (
    <section aria-label="Jobs">
      <p className="mb-2 text-meta text-muted"><span className="font-mono text-ink">{total}</span> jobs · newest first</p>
      <ol className="space-y-0.5">
        {jobs.map((j) => {
          const y = years(j);
          return (
            <li key={j.id} className="flex items-start gap-3 rounded-lg px-4 py-3.5 transition-colors duration-quick hover:bg-surface">
              <div className="min-w-0 flex-1">
                <div className="line-clamp-2 text-body font-medium">{j.title}</div>
                <div className="mt-0.5 truncate text-meta text-muted">
                  {j.company} · {place(j)} · {shortDate(j.posted_at ?? j.first_seen_at)}
                </div>
              </div>
              <span className={`shrink-0 pt-0.5 font-mono text-caption ${y == null ? "text-muted" : "font-medium text-accent"}`}>
                {y == null ? "Not stated" : `${y} yrs`}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// Loading state: the shape of the first rows, no spinner (brief, docs/briefs/job-list.md).
function Skeleton() {
  return (
    <ol aria-busy="true" aria-label="Loading jobs" className="space-y-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <li key={i} className="px-4 py-3.5">
          <div className="h-3.5 w-3/4 animate-pulse rounded-sm bg-surface" />
          <div className="mt-2 h-3 w-1/2 animate-pulse rounded-sm bg-surface" />
        </li>
      ))}
    </ol>
  );
}
