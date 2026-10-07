import { useEffect, useState } from "react";
import { fetchJob, type JobDetail, type JobSummary } from "./api";
import { FAMILY_LABEL, cleanSnippet, experienceLabel, kindLabel, levelLabel, locationLine, reasonText, timeAgo } from "./format";

interface Props {
  job: JobSummary;
  open: boolean;
  onToggle: () => void;
}

export function JobRow({ job, open, onToggle }: Props) {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || detail) return;
    const ctrl = new AbortController();
    fetchJob(job.id, ctrl.signal)
      .then(setDetail)
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, [open, detail, job.id]);

  const exp = experienceLabel(job);
  const panelId = `detail-${job.id}`;

  return (
    <li className={`job job--${job.level}`}>
      <div className="job__main">
        <h2 className="job__title">
          <button className="job__toggle" aria-expanded={open} aria-controls={panelId} onClick={onToggle}>
            {job.title}
          </button>
        </h2>

        <p className="job__meta">
          <span className="job__company">{job.company}</span>
          <span>{locationLine(job)}</span>
          {job.role_family && <span>{FAMILY_LABEL[job.role_family]}</span>}
          <span title={job.first_seen_at}>Seen {timeAgo(job.first_seen_at)}</span>
        </p>

        {job.highlight ? (
          <p className="job__evidence">
            <span className="job__evidence-label">{kindLabel(job.highlight)}</span>
            <span className="job__evidence-text">
              <mark>{cleanSnippet(job.highlight.text)}</mark>
            </span>
          </p>
        ) : (
          <p className="job__evidence job__evidence--none">{reasonText(job.level, job.level_reason)}</p>
        )}
      </div>

      <div className="job__badge" aria-label={`${job.level}, confidence ${Math.round(job.level_confidence * 100)}%`}>
        <span className="job__level">{levelLabel(job.level)}</span>
        <span className="job__conf">{Math.round(job.level_confidence * 100)}% sure</span>
        {exp && <span className="job__exp">{exp}</span>}
        {job.batch_years.length > 0 && <span className="job__exp">Batch {job.batch_years.join(", ")}</span>}
        <a className="job__apply" href={job.url} target="_blank" rel="noopener noreferrer">
          Apply<span className="visually-hidden"> to {job.title} at {job.company}</span>
        </a>
      </div>

      {open && (
        <div className="job__detail" id={panelId}>
          {error && <p className="notice notice--error">Couldn't load this job: {error}.</p>}
          {!detail && !error && <p className="notice">Loading details…</p>}
          {detail && (
            <>
              <section>
                <h3>Why it's labelled {job.level}</h3>
                <p className="job__reason">{reasonText(job.level, detail.level_reason)}</p>
                <ul className="evidence-list">
                  {detail.evidence.level.map((e, i) => (
                    <li key={i}>
                      <span className="job__evidence-label">{kindLabel(e)}</span>
                      <mark>{cleanSnippet(e.snippet)}</mark>
                    </li>
                  ))}
                </ul>
              </section>
              <section>
                <h3>Why it's a role for you</h3>
                <p className="job__reason">{detail.role_reason}</p>
                <ul className="evidence-list">
                  {detail.evidence.role
                    .filter((e) => e.kind !== "title")
                    .map((e, i) => (
                      <li key={i}>
                        <span className="job__evidence-label">{kindLabel(e)}</span>
                        <mark>{cleanSnippet(e.snippet)}</mark>
                      </li>
                    ))}
                </ul>
              </section>
              <section>
                <h3>Description</h3>
                <div className="job__description">{detail.description_text}</div>
              </section>
            </>
          )}
        </div>
      )}
    </li>
  );
}
