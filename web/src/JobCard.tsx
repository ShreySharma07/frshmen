import { useEffect, useState } from "react";
import { fetchJob, type JobDetail, type JobSummary } from "./api";
import { FAMILY_LABEL, cleanSnippet, experienceLabel, kindLabel, levelLabel, locationLine, reasonText, timeAgo } from "./format";

interface Props {
  job: JobSummary;
  open: boolean;
  onToggle: () => void;
}

export function JobCard({ job, open, onToggle }: Props) {
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
    <li className={`card job--${job.level}${open ? " card--open" : ""}`}>
      <div className="card__top">
        <span className="card__level">{levelLabel(job.level)}</span>
        <span className="card__conf">{Math.round(job.level_confidence * 100)}% sure</span>
      </div>

      <h2 className="card__title">{job.title}</h2>
      <p className="card__company">
        {job.company}
        <span className="card__location"> · {locationLine(job)}</span>
      </p>

      <ul className="card__tags" aria-label="Details">
        {job.role_family && <li>{FAMILY_LABEL[job.role_family]}</li>}
        {exp && <li>{exp}</li>}
        {job.batch_years.length > 0 && <li>Batch {job.batch_years.join(", ")}</li>}
      </ul>

      {job.highlight ? (
        <p className="card__evidence">
          <span className="card__evidence-label">{kindLabel(job.highlight)}</span>
          <span className="card__evidence-text">
            <mark>{cleanSnippet(job.highlight.text)}</mark>
          </span>
        </p>
      ) : (
        <p className="card__evidence card__evidence--none">{reasonText(job.level, job.level_reason)}</p>
      )}

      <div className="card__footer">
        {/* The source's posting date when it gives one; otherwise when we first saw the job. */}
        <span className="card__seen" title={job.posted_at ?? job.first_seen_at}>
          {job.posted_at ? `Posted ${timeAgo(job.posted_at)}` : `Seen ${timeAgo(job.first_seen_at)}`}
        </span>
        <button className="card__details" aria-expanded={open} aria-controls={panelId} onClick={onToggle}>
          {open ? "Hide details" : "Details"}
        </button>
        <a className="card__apply" href={job.url} target="_blank" rel="noopener noreferrer">
          Apply<span className="visually-hidden"> to {job.title} at {job.company}</span>
        </a>
      </div>

      {open && (
        <div className="card__detail" id={panelId}>
          {error && <p className="notice notice--error">Couldn't load this job: {error}.</p>}
          {!detail && !error && <p className="notice">Loading details…</p>}
          {detail && (
            <>
              <section>
                <h3>Why it's labelled {job.level}</h3>
                <p className="detail__reason">{reasonText(job.level, detail.level_reason)}</p>
                <ul className="evidence-list">
                  {detail.evidence.level.map((e, i) => (
                    <li key={i}>
                      <span className="card__evidence-label">{kindLabel(e)}</span>
                      <mark>{cleanSnippet(e.snippet)}</mark>
                    </li>
                  ))}
                </ul>
              </section>
              <section>
                <h3>Why it's a role for you</h3>
                <p className="detail__reason">{detail.role_reason}</p>
                <ul className="evidence-list">
                  {detail.evidence.role
                    .filter((e) => e.kind !== "title")
                    .map((e, i) => (
                      <li key={i}>
                        <span className="card__evidence-label">{kindLabel(e)}</span>
                        <mark>{cleanSnippet(e.snippet)}</mark>
                      </li>
                    ))}
                </ul>
              </section>
              <section>
                <h3>Description</h3>
                <div className="detail__description">{detail.description_text}</div>
              </section>
            </>
          )}
        </div>
      )}
    </li>
  );
}
