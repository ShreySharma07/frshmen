"use client";
// The resume beside the agent chat (docs/decisions.md, 2026-11-16 and 2026-11-17, concept A).
// Content: the resume as fields, read from the person's PDF (resume_doc). Design: four templates,
// a preview, Download (ResumeDesign). "Ask agent to improve" rewords lines (tailor.guard keeps it to
// what the resume says) and each change goes back into its own field. "Save to profile" stores the
// structure and the text the agent and fit checks read. Loaded only when opened.
import { FileUp, Loader2, PenLine, Undo2, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { docFromText, docStats, docToText, setLine, tidy, type Path, type ResumeDoc } from "@/lib/resumeDoc";
import { improveResume, isChange } from "@/lib/resumeEdit";
import { readResume, storedResume } from "@/lib/resumeRead";
import { RESUME_BUCKET, RESUME_MAX_BYTES, RESUME_TEXT_MAX, resumePath, supabase } from "@/lib/supabase";
import { ResumeFields } from "./ResumeFields";
import { SidePanel } from "./SidePanel";

// The Design tab brings the Typst client; it loads when the tab is first opened.
const ResumeDesign = dynamic(() => import("./ResumeDesign").then((m) => m.ResumeDesign), { ssr: false });

export interface ResumeSource { userId: string; name: string; text: string; fileName: string | null; path: string | null; doc: ResumeDoc | null }

type Status = { kind: "idle" | "improving" | "saving" | "saved" | "reading" } | { kind: "error"; message: string };
interface Change { key: string; path: Path; original: string; text: string }

export function ResumePanel({ source, onClose, onSaved, onRemaining }: {
  source: ResumeSource; onClose: () => void; onSaved: (s: Pick<ResumeSource, "text" | "fileName" | "doc">) => void; onRemaining: (n: number) => void;
}) {
  const [doc, setDoc] = useState<ResumeDoc | null>(source.doc);
  const [file, setFile] = useState<File | null>(null);
  const [tab, setTab] = useState<"content" | "design">("content");
  const [review, setReview] = useState<{ note: string; changes: Change[]; undone: Set<string>; kept: number } | null>(null);
  const [status, setStatus] = useState<Status>(source.doc ? { kind: "idle" } : { kind: "reading" });
  const [dirty, setDirty] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []); // keyboard and screen-reader users land in the panel

  // People who signed up before resume_doc existed: read the PDF they stored then, once.
  useEffect(() => {
    if (source.doc) return;
    let gone = false;
    (async () => {
      const stored = source.path ? await storedResume(source.path).catch(() => null) : null;
      const read = stored ? await readResume(stored).catch(() => null) : null;
      if (gone) return;
      setDoc(read?.doc ?? docFromText(source.text));
      setDirty(Boolean(read || source.text));
      setStatus({ kind: "idle" });
    })();
    return () => { gone = true; };
  }, [source.doc, source.path, source.text]);

  const edit = (d: ResumeDoc) => { setDoc(d); setDirty(true); if (status.kind === "saved" || status.kind === "error") setStatus({ kind: "idle" }); };
  const busy = ["improving", "saving", "reading"].includes(status.kind);

  const improve = async () => {
    if (!doc) return;
    const { text, map } = docToText(tidy(doc));
    if (!text.trim()) return setStatus({ kind: "error", message: "Add your resume first: upload a PDF or fill in the fields." });
    setStatus({ kind: "improving" });
    try {
      const result = await improveResume(text.slice(0, 20_000));
      onRemaining(result.remaining);
      // A reworded line made from exactly one of ours goes back into that line's field; the order and
      // the sections stay as the person set them.
      const changes = result.sections.flatMap((s, si) => s.lines.map((l, li) => ({ l, key: `${si}:${li}` })))
        .filter(({ l }) => isChange(l) && l.sources.length === 1 && map[l.sources[0] - 1])
        .map(({ l, key }) => ({ key, path: map[l.sources[0] - 1], original: l.original, text: l.text }));
      setDoc(tidy(doc));
      setReview({ note: result.note, changes, undone: new Set(), kept: result.kept_original });
      setStatus({ kind: "idle" });
    } catch (err) {
      const e = err as Error & { status?: number };
      setStatus({ kind: "error", message: e.status === 429 ? "You've used today's 20 agent messages."
        : e.status === 404 ? "The agent isn't switched on yet."
        : /busy|quota|usable/i.test(e.message) ? "Gemini is busy. Try again in a minute; this wasn't counted." : e.message });
    }
  };
  const applied = (r = review, d = doc) => (r && d ? r.changes.filter((c) => !r.undone.has(c.key)).reduce((acc, c) => setLine(acc, c.path, c.text), d) : d);
  // What the Design tab lays out: the fields with the accepted changes in (a stable object, so the
  // preview compiles again only when something changed).
  const shown = useMemo(() => applied(review, doc), [review, doc]); // eslint-disable-line react-hooks/exhaustive-deps
  const finishReview = () => { const next = applied(); if (next) edit(next); setReview(null); };
  const toggle = (key: string) => setReview((r) => {
    if (!r) return r;
    const undone = new Set(r.undone);
    if (undone.has(key)) undone.delete(key); else undone.add(key);
    return { ...r, undone };
  });

  const pick = async (f: File | undefined) => {
    if (!f) return;
    if (f.type !== "application/pdf") return setStatus({ kind: "error", message: "Choose a PDF file." });
    if (f.size > RESUME_MAX_BYTES) return setStatus({ kind: "error", message: "That PDF is over 5 MB." });
    setStatus({ kind: "reading" });
    try {
      const { doc: read } = await readResume(f);
      if (!read.name && !read.sections.length) return setStatus({ kind: "error", message: "No text found in that PDF (is it a scan?)." });
      setReview(null);
      setFile(f);
      edit(read);
      setStatus({ kind: "idle" });
    } catch {
      setStatus({ kind: "error", message: "Couldn't read that PDF. Try exporting it again." });
    }
  };

  const save = async () => {
    const value = applied();
    if (!value) return;
    const clean = tidy(value);
    const text = docToText(clean).text.slice(0, RESUME_TEXT_MAX);
    setStatus({ kind: "saving" });
    const sb = supabase();
    const patch: Record<string, unknown> = { resume_doc: clean, resume_text: text || null };
    if (file) {
      const up = await sb.storage.from(RESUME_BUCKET).upload(resumePath(source.userId), file, { upsert: true, contentType: "application/pdf" });
      if (up.error) return setStatus({ kind: "error", message: up.error.message });
      Object.assign(patch, { resume_path: resumePath(source.userId), resume_name: file.name.slice(0, 200) });
    }
    const res = await sb.from("students").update(patch).eq("id", source.userId);
    if (res.error) return setStatus({ kind: "error", message: res.error.message });
    setReview(null);
    setDoc(clean);
    setDirty(false);
    onSaved({ text, doc: clean, fileName: file ? file.name : source.fileName });
    setFile(null);
    setStatus({ kind: "saved" });
  };

  const secondary = "inline-flex items-center gap-1.5 rounded-md border border-ink px-3.5 py-2 text-meta font-medium transition-transform duration-quick active:scale-[0.98] disabled:opacity-50";
  const from = file ? `From ${file.name} (not saved yet)` : source.fileName ? `From ${source.fileName}` : source.text ? "Your saved resume" : "No resume saved yet";
  const stats = doc ? docStats(doc) : null;
  const active = review ? review.changes.filter((c) => !review.undone.has(c.key)).length : 0;

  return (
    <SidePanel labelledBy="resume-title" onClose={onClose}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="resume-title" ref={heading} tabIndex={-1} className="font-display text-[1.375rem] leading-tight outline-none">Your resume</h2>
          <p className="text-meta text-muted">
            {from}{stats && ` · ${stats.sections} sections, ${stats.entries} entries`} ·{" "}
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

      <div role="tablist" aria-label="Resume" className="mt-3 flex gap-1.5">
        {(["content", "design"] as const).map((t) => (
          <button key={t} type="button" role="tab" id={`resume-tab-${t}`} aria-selected={tab === t} aria-controls={`resume-panel-${t}`} onClick={() => setTab(t)}
            className={`rounded-full border px-3.5 py-1 text-meta font-medium transition-colors duration-quick ${tab === t ? "border-ink bg-ink text-canvas" : "border-line hover:border-ink"}`}>
            {t === "content" ? "Content" : "Design"}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`resume-panel-${tab}`} aria-labelledby={`resume-tab-${tab}`} className="mt-4 min-h-0 flex-1 overflow-y-auto [scrollbar-width:thin]">
        {!doc ? (
          <div aria-busy="true" className="grid gap-2">{[0, 1, 2, 3].map((i) => <div key={i} className="h-10 animate-pulse rounded-md bg-surface" />)}<p className="text-meta text-muted">Reading your PDF…</p></div>
        ) : tab === "design" ? (
          <ResumeDesign doc={shown ?? doc} />
        ) : review ? (
          <div className="grid gap-3">
            <div className="rounded-md bg-surface px-3 py-2 text-meta">
              {review.note && <p>{review.note}</p>}
              <p className="text-muted">
                {review.changes.length} {review.changes.length === 1 ? "change" : "changes"}
                {review.kept > 0 && ` · ${review.kept} kept as written (the rewrite added something your resume doesn't say)`}
                {review.changes.length > 0 && <> · <button type="button" onClick={() => setReview({ ...review, undone: new Set() })} className="underline underline-offset-2">accept all</button> · <button type="button" onClick={() => setReview({ ...review, undone: new Set(review.changes.map((c) => c.key)) })} className="underline underline-offset-2">undo all</button></>}
              </p>
            </div>
            {review.changes.length === 0 && <p className="text-body text-muted">Nothing to change: your lines already read well.</p>}
            <ul className="grid gap-3">
              {review.changes.map((c) => {
                const undone = review.undone.has(c.key);
                return (
                  <li key={c.key} className="text-body">
                    {undone ? <span>{c.original}</span> : <>
                      <del className="block text-meta text-muted">{c.original}</del>
                      <ins className="block bg-accent/10 no-underline">{c.text}</ins>
                    </>}
                    <button type="button" onClick={() => toggle(c.key)} className="mt-0.5 inline-flex items-center gap-1 text-caption font-medium text-accent-text underline-offset-2 hover:underline">
                      {undone ? "Use the rewrite" : <><Undo2 aria-hidden className="size-3.5" />Undo</>}
                    </button>
                  </li>
                );
              })}
            </ul>
            <button type="button" onClick={finishReview} className={`${secondary} justify-self-start`}>Done reviewing{active ? `, keep ${active}` : ""}</button>
          </div>
        ) : (
          <ResumeFields doc={doc} set={edit} />
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={save} disabled={busy || !doc || (!dirty && !review && !file)}
          className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-meta font-medium text-canvas transition-transform duration-quick active:scale-[0.98] disabled:opacity-60">
          {status.kind === "saving" && <Loader2 aria-hidden className="size-4 animate-spin" />}Save to profile
        </button>
        {!review && tab === "content" && (
          <button type="button" onClick={improve} disabled={busy || !doc} className={secondary}>
            {status.kind === "improving" ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <PenLine aria-hidden className="size-4" />}
            {status.kind === "improving" ? "Reading your resume…" : "Ask agent to improve"}
          </button>
        )}
      </div>
      <p aria-live="polite" className="mt-2 text-caption text-muted">
        {status.kind === "error" ? <span role="alert" className="text-card-fail">{status.message}</span>
          : status.kind === "saved" ? "Saved. The agent and fit checks now read this version."
          : status.kind === "reading" ? "Reading the PDF…"
          : dirty ? "Not saved yet." : "Improving uses 1 of your 20 agent messages and never adds a skill or a number."}
      </p>
    </SidePanel>
  );
}
