"use client";
// The resume editor beside the agent chat (docs/decisions.md, 2026-11-16, concept A): the resume
// saved at sign-up, edited in place; "Ask agent to improve" suggests rewording, shown line by line
// to accept or undo; "Save to profile" stores the text the agent and fit checks read; "Export PDF"
// downloads this version. Loaded only when opened, with pdf.js and pdf-lib behind it.
import { Download, FileUp, Loader2, PenLine, Undo2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { applyReview, exportResumePdf, improveResume, isChange, type Improved } from "@/lib/resumeEdit";
import { resumeText } from "@/lib/resumeText";
import { RESUME_BUCKET, RESUME_MAX_BYTES, RESUME_TEXT_MAX, resumePath, supabase } from "@/lib/supabase";
import { SidePanel } from "./SidePanel";

export interface ResumeSource { userId: string; name: string; text: string; fileName: string | null }

type Status = { kind: "idle" | "improving" | "saving" | "saved" | "reading" | "exporting" } | { kind: "error"; message: string };

export function ResumePanel({ source, onClose, onSaved, onRemaining }: {
  source: ResumeSource; onClose: () => void; onSaved: (text: string, fileName: string | null) => void; onRemaining: (n: number) => void;
}) {
  const [text, setText] = useState(source.text);
  const [file, setFile] = useState<File | null>(null);
  const [review, setReview] = useState<{ base: string; result: Improved; undone: Set<string> } | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const picker = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []); // keyboard and screen-reader users land in the panel
  const busy = ["improving", "saving", "reading", "exporting"].includes(status.kind);

  // The text as it stands: in review, each change as accepted or undone.
  const current = () => (review ? applyReview(review.base, review.result, (si, li) => !review.undone.has(`${si}:${li}`)) : text);
  const changes = review ? review.result.sections.flatMap((s, si) => s.lines.map((l, li) => ({ l, key: `${si}:${li}` }))).filter(({ l }) => isChange(l)) : [];

  const improve = async () => {
    if (!text.trim()) return setStatus({ kind: "error", message: "Add your resume first: upload a PDF or paste the text." });
    setStatus({ kind: "improving" });
    try {
      const result = await improveResume(text.slice(0, 20_000));
      onRemaining(result.remaining);
      setReview({ base: text, result, undone: new Set() });
      setStatus({ kind: "idle" });
    } catch (err) {
      const e = err as Error & { status?: number };
      setStatus({ kind: "error", message: e.status === 429 ? "You've used today's 20 agent messages."
        : e.status === 404 ? "The agent isn't switched on yet."
        : /busy|quota|usable/i.test(e.message) ? "Gemini is busy. Try again in a minute; this wasn't counted." : e.message });
    }
  };
  const finishReview = () => { setText(current()); setReview(null); };
  const toggle = (key: string) => setReview((r) => {
    if (!r) return r;
    const undone = new Set(r.undone);
    if (undone.has(key)) undone.delete(key); else undone.add(key);
    return { ...r, undone };
  });
  const all = (accept: boolean) => setReview((r) => r && { ...r, undone: accept ? new Set() : new Set(changes.map((c) => c.key)) });

  const pick = async (f: File | undefined) => {
    if (!f) return;
    if (f.type !== "application/pdf") return setStatus({ kind: "error", message: "Choose a PDF file." });
    if (f.size > RESUME_MAX_BYTES) return setStatus({ kind: "error", message: "That PDF is over 5 MB." });
    setStatus({ kind: "reading" });
    try {
      const read = await resumeText(f);
      if (!read) return setStatus({ kind: "error", message: "No text found in that PDF (is it a scan?). Paste the text instead." });
      setReview(null);
      setText(read);
      setFile(f);
      setStatus({ kind: "idle" });
    } catch {
      setStatus({ kind: "error", message: "Couldn't read that PDF. Try exporting it again." });
    }
  };

  const save = async () => {
    const value = current().trim().slice(0, RESUME_TEXT_MAX);
    setStatus({ kind: "saving" });
    const sb = supabase();
    const patch: Record<string, string | null> = { resume_text: value || null };
    if (file) {
      const up = await sb.storage.from(RESUME_BUCKET).upload(resumePath(source.userId), file, { upsert: true, contentType: "application/pdf" });
      if (up.error) return setStatus({ kind: "error", message: up.error.message });
      Object.assign(patch, { resume_path: resumePath(source.userId), resume_name: file.name.slice(0, 200) });
    }
    const res = await sb.from("students").update(patch).eq("id", source.userId);
    if (res.error) return setStatus({ kind: "error", message: res.error.message });
    if (review) finishReview();
    onSaved(value, file ? file.name : source.fileName);
    setFile(null);
    setStatus({ kind: "saved" });
  };

  const exportPdf = async () => {
    setStatus({ kind: "exporting" });
    try {
      await exportResumePdf(current(), source.name);
      setStatus({ kind: "idle" });
    } catch (e) {
      setStatus({ kind: "error", message: `Couldn't make the PDF: ${(e as Error).message}` });
    }
  };

  const field = "w-full rounded-md border border-line bg-canvas px-3 py-2 text-body outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent/40";
  const secondary = "inline-flex items-center gap-1.5 rounded-md border border-ink px-3.5 py-2 text-meta font-medium transition-transform duration-quick active:scale-[0.98] disabled:opacity-50";
  const from = file ? `From ${file.name} (not saved yet)` : source.fileName ? `From ${source.fileName}` : source.text ? "Your saved resume" : "No resume saved yet";

  return (
    <SidePanel labelledBy="resume-title" onClose={onClose}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="resume-title" ref={heading} tabIndex={-1} className="font-display text-[1.375rem] leading-tight outline-none">Your resume</h2>
          <p className="text-meta text-muted">
            {from} ·{" "}
            <button type="button" onClick={() => picker.current?.click()} disabled={busy} className="font-medium text-accent-text underline underline-offset-2">
              <FileUp aria-hidden className="mr-0.5 inline size-3.5 align-[-2px]" />Upload a new PDF
            </button>
          </p>
          <input ref={picker} type="file" accept="application/pdf" className="sr-only" tabIndex={-1} aria-label="Resume PDF"
            onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        </div>
        <button type="button" onClick={onClose} aria-label="Close resume" className="grid size-9 shrink-0 place-items-center rounded-md hover:bg-surface">
          <X aria-hidden className="size-5" />
        </button>
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin]">
        {review ? (
          <div className="grid gap-3">
            <div className="rounded-md bg-surface px-3 py-2 text-meta">
              {review.result.note && <p>{review.result.note}</p>}
              <p className="text-muted">
                {changes.length} {changes.length === 1 ? "change" : "changes"}
                {review.result.kept_original > 0 && ` · ${review.result.kept_original} kept as written (the rewrite added something your resume doesn't say)`}
                {changes.length > 0 && <> · <button type="button" onClick={() => all(true)} className="underline underline-offset-2">accept all</button> · <button type="button" onClick={() => all(false)} className="underline underline-offset-2">undo all</button></>}
              </p>
            </div>
            {review.result.sections.map((s, si) => (
              <section key={si}>
                {s.heading && <h3 className="text-caption font-medium uppercase tracking-wide text-muted">{s.heading}</h3>}
                <ul className="mt-1 grid gap-1.5">
                  {s.lines.map((l, li) => {
                    const key = `${si}:${li}`;
                    if (!isChange(l)) return <li key={key} className="text-body">{l.text}</li>;
                    const undone = review.undone.has(key);
                    return (
                      <li key={key} className="text-body">
                        {undone ? <span>{l.original}</span> : <>
                          <del className="block text-meta text-muted">{l.original}</del>
                          <ins className="block bg-accent/10 no-underline">{l.text}</ins>
                        </>}
                        <button type="button" onClick={() => toggle(key)} className="mt-0.5 inline-flex items-center gap-1 text-caption font-medium text-accent-text underline-offset-2 hover:underline">
                          {undone ? "Use the rewrite" : <><Undo2 aria-hidden className="size-3.5" />Undo</>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
            <button type="button" onClick={finishReview} className={`${secondary} justify-self-start`}>Done reviewing, keep editing</button>
          </div>
        ) : (
          <label className="block text-meta font-medium">
            <span className="sr-only">Resume text</span>
            <textarea value={text} maxLength={RESUME_TEXT_MAX} onChange={(e) => { setText(e.target.value); if (status.kind === "saved") setStatus({ kind: "idle" }); }}
              rows={14} placeholder="Paste your resume's text, or upload a PDF."
              className={`${field} resize-none font-normal leading-relaxed [field-sizing:content]`} />
          </label>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={save} disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-meta font-medium text-canvas transition-transform duration-quick active:scale-[0.98] disabled:opacity-60">
          {status.kind === "saving" && <Loader2 aria-hidden className="size-4 animate-spin" />}Save to profile
        </button>
        {!review && (
          <button type="button" onClick={improve} disabled={busy} className={secondary}>
            {status.kind === "improving" ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <PenLine aria-hidden className="size-4" />}
            {status.kind === "improving" ? "Reading your resume…" : "Ask agent to improve"}
          </button>
        )}
        <button type="button" onClick={exportPdf} disabled={busy || !current().trim()} className={secondary}>
          {status.kind === "exporting" ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Download aria-hidden className="size-4" />}Export PDF
        </button>
      </div>
      <p aria-live="polite" className="mt-2 text-caption text-muted">
        {status.kind === "error" ? <span role="alert" className="text-card-fail">{status.message}</span>
          : status.kind === "saved" ? "Saved. The agent and fit checks now read this version."
          : status.kind === "reading" ? "Reading the PDF…"
          : "Improving uses 1 of your 20 agent messages and never adds a skill or a number. Saving updates the text Aventra reads; Export PDF downloads this version."}
      </p>
    </SidePanel>
  );
}
