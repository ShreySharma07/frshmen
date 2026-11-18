"use client";
// The Design tab (docs/decisions.md, 2026-11-17, concept A): the four templates, a preview of page 1,
// and Download. The first time, the layout engine (11 MB) downloads with a progress bar; after that
// the browser's cache has it and a change shows in well under a second.
import { Download, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { exportPlainPdf } from "@/lib/resumeEdit";
import { compileResume, drawFirstPage, savePdf, typstSupported } from "@/lib/resumeExport";
import type { ResumeDoc } from "@/lib/resumeDoc";
import { TEMPLATES, type TemplateId } from "@/lib/resumeTemplates";

type State = { kind: "loading"; progress: number | null } | { kind: "ready"; pdf: Uint8Array; pages: number } | { kind: "error"; message: string };

const TEMPLATE_KEY = "aventra:resume-template";
const savedTemplate = (): TemplateId => {
  try { const t = localStorage.getItem(TEMPLATE_KEY); if (TEMPLATES.some((x) => x.id === t)) return t as TemplateId; } catch {}
  return "classic";
};

export function ResumeDesign({ doc }: { doc: ResumeDoc }) {
  const [template, setTemplate] = useState<TemplateId>(savedTemplate);
  const [state, setState] = useState<State>({ kind: "loading", progress: null });
  const canvas = useRef<HTMLCanvasElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const supported = typstSupported();

  useEffect(() => {
    if (!supported) return;
    let stale = false;
    // Edits made on the Content tab arrive together; wait for a pause before laying out again.
    const timer = setTimeout(async () => {
      try {
        const pdf = await compileResume(template, doc, (f) => { if (!stale) setState((s) => (s.kind === "ready" ? s : { kind: "loading", progress: f })); });
        if (stale || !canvas.current) return;
        const pages = await drawFirstPage(pdf, canvas.current, box.current?.clientWidth ?? 360);
        if (!stale) setState({ kind: "ready", pdf, pages });
      } catch (e) {
        if (!stale) setState({ kind: "error", message: (e as Error).message });
      }
    }, 250);
    return () => { stale = true; clearTimeout(timer); };
  }, [template, doc, supported]);

  const choose = (t: TemplateId) => {
    setTemplate(t);
    try { localStorage.setItem(TEMPLATE_KEY, t); } catch {}
  };
  const label = TEMPLATES.find((t) => t.id === template)?.label ?? "Classic";
  const plain = () => exportPlainPdf(doc).catch(() => {});

  return (
    <div className="grid gap-3">
      <div role="radiogroup" aria-label="Template" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {TEMPLATES.map((t) => (
          <button key={t.id} type="button" role="radio" aria-checked={template === t.id} onClick={() => choose(t.id)}
            className={`rounded-md border px-2.5 py-2 text-left transition-colors duration-quick ${template === t.id ? "border-ink bg-card shadow-raised" : "border-line hover:border-ink/40"}`}>
            <span className="block text-meta font-medium">{t.label}</span>
            <span className="block text-caption leading-snug text-muted">{t.note}</span>
          </button>
        ))}
      </div>

      {!supported ? (
        <p className="rounded-md bg-surface px-3 py-2 text-meta">This browser can&apos;t run the layout engine. <button type="button" onClick={plain} className="font-medium text-accent-text underline underline-offset-2">Download a plain PDF</button> instead.</p>
      ) : (
        <>
          <div ref={box} className="relative overflow-hidden rounded-md border border-card-line bg-white" style={{ aspectRatio: "1 / 1.414" }}>
            <canvas ref={canvas} aria-label={`Preview of page 1 in the ${label} template`} role="img" className={`block transition-opacity duration-quick ${state.kind === "ready" ? "opacity-100" : "opacity-40"}`} />
            {state.kind === "loading" && (
              <div className="absolute inset-0 grid place-items-center p-6 text-center text-meta text-[#3a3a3e]">
                {state.progress !== null && state.progress < 1 ? (
                  <div className="w-full max-w-56">
                    <p>Getting the layout engine ready (11 MB, the first time only)</p>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#e4e4e7]" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(state.progress * 100)}>
                      <div className="h-full origin-left bg-[#1c1c1e] transition-transform duration-quick" style={{ transform: `scaleX(${state.progress})` }} />
                    </div>
                  </div>
                ) : <Loader2 aria-label="Laying out" className="size-5 animate-spin" />}
              </div>
            )}
          </div>
          {state.kind === "error" && (
            <p role="alert" className="text-meta text-card-fail">Couldn&apos;t lay it out: {state.message}. <button type="button" onClick={plain} className="font-medium underline underline-offset-2">Download a plain PDF</button></p>
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <button type="button" disabled={state.kind !== "ready"} onClick={() => state.kind === "ready" && savePdf(state.pdf, doc.name, label)}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-meta font-medium text-canvas transition-transform duration-quick active:scale-[0.98] disabled:opacity-50">
              <Download aria-hidden className="size-4" />Download PDF
            </button>
            {state.kind === "ready" && (
              <span className="text-caption text-muted">
                {state.pages === 1 ? "1 page" : <span className="text-card-fail">{state.pages} pages: try Compact, or trim a few bullets</span>} · text a hiring system can read
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
