"use client";
// What the job list will show for the profile being edited (layout A, docs/decisions.md
// 2026-11-15): on phones a line under the choices, on wide screens the first jobs beside the form.
// It asks the same API as the job list, once the picks have been still for a moment.
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchJobs, type JobSummary } from "@/lib/api";
import { categoryLabel } from "@/lib/describe";
import { bandOf, profileFilters, toApiParams, toSearch } from "@/lib/filters";
import { place, years } from "@/lib/format";
import { CompanyMark } from "@/components/CompanyMark";

type State = { kind: "loading" } | { kind: "ready"; total: number; jobs: JobSummary[] } | { kind: "error" };

export function useProfilePreview(yoe: number, roles: string[]) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const key = `${yoe}|${roles.join(",")}`;
  useEffect(() => {
    const ctl = new AbortController();
    // Waits out a quick run of taps before asking.
    const t = setTimeout(() => {
      setState({ kind: "loading" });
      fetchJobs(toApiParams(profileFilters(yoe, roles)), 1, true, ctl.signal)
        .then((r) => setState({ kind: "ready", total: r.total ?? r.jobs.length, jobs: r.jobs.slice(0, 3) }))
        .catch((e: Error) => { if (e.name !== "AbortError") setState({ kind: "error" }); });
    }, 300);
    return () => { clearTimeout(t); ctl.abort(); };
    // key stands for yoe and roles
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}

/** "### open jobs for 0–1 years in AI/ML & data science + Backend". */
export function PreviewLine({ yoe, roles, state }: { yoe: number; roles: string[]; state: State }) {
  const what = roles.length ? categoryLabel(roles.join(",")) : "every kind of work";
  const band = bandOf(yoe).replace("-", "–");
  return (
    <p aria-live="polite" className="text-meta text-muted">
      {state.kind === "ready" ? <><span className="font-mono text-ink">{state.total.toLocaleString("en-IN")}</span> open {state.total === 1 ? "job" : "jobs"}</>
        : state.kind === "error" ? "Couldn't count the jobs" : "Counting jobs…"}
      {" "}for {band} years in {what}
    </p>
  );
}

export function PreviewPanel({ yoe, roles, state }: { yoe: number; roles: string[]; state: State }) {
  return (
    <aside aria-label="Your job list" className="sticky top-[4.5rem] rounded-lg border border-card-line bg-card p-5">
      <h2 className="text-meta font-medium uppercase tracking-wide text-muted">Your job list will show</h2>
      <div className="mt-2"><PreviewLine yoe={yoe} roles={roles} state={state} /></div>
      {/* grid-cols-1 is minmax(0, 1fr): a long "company · place" line truncates instead of widening every card past the panel. */}
      <ul className={`mt-4 grid grid-cols-1 gap-2 transition-opacity duration-quick ${state.kind === "loading" ? "opacity-50" : ""}`}>
        {state.kind === "ready" && state.jobs.map((j) => {
          const y = years(j);
          return (
            <li key={j.id} className="flex items-start gap-3 rounded-md border border-line bg-canvas px-3 py-2.5">
              <CompanyMark company={j.company} />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-1 text-body font-medium">{j.title}</span>
                <span className="block truncate text-meta text-muted">{[j.company, place(j)].filter(Boolean).join(" · ")}</span>
              </span>
              <span className="shrink-0 font-mono text-meta text-muted">{y ? `${y} yrs` : "not stated"}</span>
            </li>
          );
        })}
        {state.kind === "ready" && state.jobs.length === 0 && <li className="text-body text-muted">No open jobs match yet. Try another kind of work or band.</li>}
        {state.kind === "loading" && [0, 1, 2].map((i) => <li key={i} aria-hidden className="h-[3.75rem] animate-pulse rounded-md bg-surface" />)}
      </ul>
      {state.kind === "ready" && state.total > 0 && (
        <Link href={"/jobs" + toSearch(profileFilters(yoe, roles))} className="mt-4 inline-block text-meta font-medium text-accent-text underline underline-offset-2">
          See all {state.total.toLocaleString("en-IN")}
        </Link>
      )}
      <p className="mt-3 text-caption text-muted">Updates as you change your picks. Saving takes you there.</p>
    </aside>
  );
}
