"use client";
// The board's Today feed: new strong matches with a one-click Save, then follow-ups that are due.
import { Bookmark, BookmarkCheck } from "lucide-react";
import { useState } from "react";
import { CompanyMark } from "@/components/CompanyMark";
import type { JobSummary } from "@/lib/api";
import { daysAgo } from "@/lib/board";
import { saveJob, type Tracked } from "@/lib/tracker";

export function Today({ userId, matches, followUps, tracked, onSaved }: {
  userId: string; matches: JobSummary[]; followUps: Tracked[]; tracked: Set<string>; onSaved: () => void;
}) {
  const [saved, setSaved] = useState<Set<string>>(new Set());
  async function save(id: string) {
    if ((await saveJob(userId, id)) === "saved") { setSaved((s) => new Set(s).add(id)); onSaved(); }
  }
  return (
    <section className="rounded-lg border border-line p-4">
      <h2 className="text-meta font-medium uppercase tracking-wide text-muted">Today</h2>
      {matches.length === 0 && followUps.length === 0 && (
        <p className="mt-3 text-body text-muted">Nothing new that strongly fits you today. New jobs arrive every few hours.</p>
      )}
      {matches.length > 0 && (
        <ul className="mt-3 space-y-2.5">
          {matches.slice(0, 5).map((j) => {
            const isSaved = saved.has(j.id) || tracked.has(j.id);
            return (
              <li key={j.id} className="flex items-center gap-2.5 text-body">
                <CompanyMark company={j.company} size="sm" />
                <a href={j.url} target="_blank" rel="noopener" className="min-w-0 flex-1 hover:underline">
                  <span className="block truncate font-medium">{j.title}</span>
                  <span className="block truncate text-meta text-muted">{j.company}</span>
                </a>
                <button type="button" onClick={() => save(j.id)} disabled={isSaved} aria-label={isSaved ? `${j.title} is saved` : `Save ${j.title}`}
                  className="grid size-8 shrink-0 place-items-center rounded-md border border-line text-muted transition-colors duration-quick hover:bg-surface hover:text-ink disabled:border-transparent">
                  {isSaved ? <BookmarkCheck aria-hidden className="size-4 text-accent" /> : <Bookmark aria-hidden className="size-4" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {followUps.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <h3 className="text-meta text-muted">Follow-ups due</h3>
          <ul className="mt-2 space-y-1.5">
            {followUps.map((t) => (
              <li key={t.id} className="text-body">
                <a href={t.jobs?.url} target="_blank" rel="noopener" className="hover:underline">
                  <span className="font-medium">{t.jobs?.companies?.name}</span> · {t.jobs?.title}
                </a>
                <span className="block text-meta text-muted">Applied {daysAgo(t.applied_at!)} days ago, no reply yet.</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
