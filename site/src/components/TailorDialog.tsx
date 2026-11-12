"use client";
// The tailored resume, in a window over the job list (docs/decisions.md, 2026-11-04). Opened from
// a fit verdict, or from the dashboard to reopen one already made. Shows what changed line by
// line, lets the person edit any line, and downloads a one-page PDF. Loaded only when opened.
import { Download, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { resumePdf } from "@/lib/resumePdf";
import { tailorResume, type Tailored, type TailoredSection } from "@/lib/tracker";
import { wordDiff } from "@/lib/wordDiff";

type Phase = { kind: "working" } | { kind: "error"; message: string } | { kind: "ready" };
type Line = TailoredSection["lines"][number] & { edited?: boolean };
type Section = { heading: string; lines: Line[] };

export function TailorDialog({ jobId, title, company, initial, onClose, onMade }: {
  jobId: string; title: string; company: string;
  initial?: Tailored | null; // reopening a saved one: no new Gemini run
  onClose: () => void;
  onMade?: (remaining: number) => void;
}) {
  const [phase, setPhase] = useState<Phase>(initial ? { kind: "ready" } : { kind: "working" });
  const [result, setResult] = useState<Tailored | null>(initial ?? null);
  const [sections, setSections] = useState<Section[]>(initial?.sections ?? []);
  const [leftOut, setLeftOut] = useState<string[]>(initial?.left_out ?? []);
  const panel = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  // One Gemini run per opening (React's dev double-effect included).
  useEffect(() => {
    if (initial || started.current) return;
    started.current = true;
    tailorResume(jobId).then((r) => {
      setResult(r); setSections(r.sections); setLeftOut(r.left_out); setPhase({ kind: "ready" }); onMade?.(r.remaining);
    }).catch((e: Error & { status?: number; freesAt?: string }) => {
      setPhase({ kind: "error", message: e.status === 429
        ? `Both tailored resumes for today are used. The next one frees up at ${e.freesAt ? new Date(e.freesAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "a later time"}.`
        : e.status === 409 ? "Add your resume to your profile first." : `Couldn't tailor right now (${e.message}).` });
    });
  }, [jobId, initial, onMade]);

  // A modal: Escape closes, focus moves in and comes back, Tab stays inside, the page doesn't scroll.
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !panel.current) return;
      const focusable = panel.current.querySelectorAll<HTMLElement>("button, a, textarea, input");
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    };
    addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { removeEventListener("keydown", onKey); document.body.style.overflow = overflow; before?.focus(); };
  }, [onClose]);

  const edit = (s: number, l: number, text: string) =>
    setSections((xs) => xs.map((sec, i) => i !== s ? sec : { ...sec, lines: sec.lines.map((ln, j) => j !== l ? ln : { ...ln, text, edited: true }) }));
  const addBack = (line: string) => {
    setLeftOut((xs) => xs.filter((x) => x !== line));
    setSections((xs) => xs.length
      ? [...xs.slice(0, -1), { ...xs[xs.length - 1], lines: [...xs[xs.length - 1].lines, { text: line, original: line, sources: [], kept_original: true, reason: null }] }]
      : [{ heading: "", lines: [{ text: line, original: line, sources: [], kept_original: true, reason: null }] }]);
  };
  async function download() {
    if (!result) return;
    const blob = await resumePdf(result.name, sections.map((s) => ({ ...s, lines: s.lines.filter((l) => l.text.trim()) })));
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: `${result.name || "resume"} - ${company}.pdf`.replace(/[\\/:*?"<>|]/g, "") });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const kept = sections.flatMap((s) => s.lines).filter((l) => l.reason).length;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 sm:items-center sm:p-6 motion-safe:animate-[fade-in_200ms_var(--ease-out-soft)]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="tailor-title"
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-lg bg-canvas shadow-menu outline-none sm:rounded-lg">
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0 flex-1">
            <h2 id="tailor-title" className="text-base font-medium">Your resume, tailored</h2>
            <p className="truncate text-meta text-muted">For {title} · {company}</p>
          </div>
          {phase.kind === "ready" && (
            <button type="button" onClick={download}
              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md bg-accent px-3.5 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
              <Download aria-hidden className="size-4" />Download PDF
            </button>
          )}
          <button type="button" onClick={onClose} aria-label="Close"
            className="grid size-9 shrink-0 place-items-center rounded-md text-muted transition-colors duration-quick hover:bg-surface hover:text-ink">
            <X aria-hidden className="size-4" />
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-5 text-body">
          {phase.kind === "working" && (
            <div aria-busy="true" className="space-y-3">
              <p className="text-muted">Gemini is rewording your resume for this job. Every line is then checked against what your resume says.</p>
              {Array.from({ length: 5 }, (_, i) => <div key={i} className="h-10 animate-pulse rounded-md bg-surface" />)}
            </div>
          )}
          {phase.kind === "error" && <p role="alert" className="text-muted">{phase.message}</p>}
          {phase.kind === "ready" && result && (
            <>
              {result.note && <p>{result.note}</p>}
              {kept > 0 && (
                <p className="mt-2 rounded-md border border-line bg-surface px-3 py-2 text-meta">
                  {kept} {kept === 1 ? "line was" : "lines were"} kept as you wrote {kept === 1 ? "it" : "them"}: the rewrite added something your resume doesn&apos;t say.
                </p>
              )}
              <div className="mt-5 space-y-6">
                {sections.map((sec, s) => (
                  <section key={s}>
                    {sec.heading && <h3 className="mb-2 text-meta font-medium uppercase tracking-wide text-muted">{sec.heading}</h3>}
                    <ul className="space-y-3">
                      {sec.lines.map((ln, l) => (
                        <li key={l}>
                          <label className="sr-only" htmlFor={`line-${s}-${l}`}>Line {l + 1} of {sec.heading || "the header"}</label>
                          <textarea id={`line-${s}-${l}`} value={ln.text} onChange={(e) => edit(s, l, e.target.value)} rows={Math.max(1, Math.ceil(ln.text.length / 45))}
                            className="w-full resize-none [field-sizing:content] rounded-md border border-line bg-canvas px-3 py-2 text-body outline-none transition-colors duration-quick focus:border-accent focus:ring-2 focus:ring-accent/30" />
                          <LineNote line={ln} />
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
              {leftOut.length > 0 && (
                <div className="mt-7 border-t border-line pt-5">
                  <h3 className="text-meta font-medium text-muted">Left out for this job</h3>
                  <ul className="mt-2 space-y-1.5">
                    {leftOut.map((line) => (
                      <li key={line} className="flex items-start gap-3 text-meta">
                        <span className="min-w-0 flex-1 text-muted">{line}</span>
                        <button type="button" onClick={() => addBack(line)} className="shrink-0 font-medium text-accent-text underline underline-offset-2">Add back</button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="mt-6 text-caption text-muted">Reworded by Gemini from your saved resume. Lines you edit are yours and aren&apos;t checked; read the PDF before you send it.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function LineNote({ line }: { line: Line }) {
  if (line.edited) return <p className="mt-1 text-caption text-muted">Edited by you.</p>;
  if (line.reason) return <p className="mt-1 text-caption text-muted">Kept as you wrote it: {line.reason}.</p>;
  if (!line.original || line.original === line.text) return <p className="mt-1 text-caption text-muted">Unchanged.</p>;
  return (
    <p className="mt-1 text-caption text-muted">
      <span className="sr-only">Changed from: {line.original}. </span>
      <span aria-hidden>
        {wordDiff(line.original, line.text).map((p, i) =>
          p.kind === "same" ? <span key={i}>{p.text}</span>
          // A gap after a removed word, so it doesn't run into the word that replaced it.
          : p.kind === "del" ? <del key={i} className="mr-1 text-muted/80 decoration-1">{p.text}</del>
          : <ins key={i} className="font-medium text-ink no-underline">{p.text}</ins>)}
      </span>
    </p>
  );
}
