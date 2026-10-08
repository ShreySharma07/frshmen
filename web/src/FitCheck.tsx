import { useState } from "react";
import { checkFit, type FitResult } from "./api";

// The resume stays in this browser; it's sent only with a check. Storage can be blocked
// (private windows), so every access is guarded and the box simply starts empty.
const RESUME_KEY = "frshmen.resume";
const load = () => {
  try { return localStorage.getItem(RESUME_KEY) ?? ""; } catch { return ""; }
};
const save = (text: string) => {
  try { localStorage.setItem(RESUME_KEY, text); } catch { /* not persisted; still usable */ }
};

const FIT_LABEL: Record<FitResult["fit"], string> = { strong: "Strong fit", partial: "Partial fit", weak: "Weak fit" };

export function FitCheck({ jobId }: { jobId: string }) {
  const [resume, setResume] = useState(load);
  const [editing, setEditing] = useState(() => load().length < 50);
  const [result, setResult] = useState<FitResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = () => {
    save(resume);
    setEditing(false);
    setBusy(true);
    setError(null);
    checkFit(jobId, resume)
      .then(setResult)
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false));
  };

  return (
    <section className="fit">
      <h3>Check my fit</h3>
      {editing ? (
        <label className="fit__resume">
          <span>Paste your resume as text. It's saved in this browser only and sent to Gemini with each check.</span>
          <textarea rows={8} value={resume} onChange={(e) => setResume(e.target.value)} />
        </label>
      ) : (
        <p className="fit__note">
          Using the resume saved in this browser. <button type="button" className="link" onClick={() => setEditing(true)}>Edit</button>
        </p>
      )}
      <button type="button" className="button" disabled={busy || resume.trim().length < 50} onClick={run}>
        {busy ? "Checking…" : result ? "Check again" : "Check my fit with Gemini"}
      </button>
      {error && <p className="notice notice--error">Couldn't check: {error}.</p>}
      {result && (
        <div className={`fit__result fit--${result.fit}`}>
          <p className="fit__verdict">
            <strong>{FIT_LABEL[result.fit]}</strong>
            {result.score !== null && <span> · {result.score}/100</span>}
          </p>
          {result.experience && <p>{result.experience}</p>}
          {result.matched.length > 0 && <p><span className="card__evidence-label">You have</span> {result.matched.join(", ")}</p>}
          {result.missing.length > 0 && <p><span className="card__evidence-label">Missing</span> {result.missing.join(", ")}</p>}
          {result.advice && <p className="fit__advice">{result.advice}</p>}
          <p className="fit__model">Gemini ({result.model}). AI judgement: check the posting yourself.</p>
        </div>
      )}
    </section>
  );
}
