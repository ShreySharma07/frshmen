// The resume's templates on the page (docs/decisions.md, 2026-11-17): compile in a worker
// (scripts/typst.worker.mjs, served by scripts/typst-assets.mjs), preview page 1 with pdf.js, download. Loaded only with the resume panel.
import type { ResumeDoc } from "./resumeDoc";
import { TEMPLATES, type TemplateId } from "./resumeTemplates";

// The worker's messages (site/scripts/typst.worker.mjs).
type ToWorker = { id: number; source: string; data: string; fonts: string[] };
type FromWorker =
  | { id: number; kind: "progress"; loaded: number; total: number }
  | { id: number; kind: "done"; pdf: Uint8Array }
  | { id: number; kind: "error"; message: string };

// All the templates' fonts load with the compiler, so switching template never waits on the network.
const ALL_FONTS = [...new Set(TEMPLATES.flatMap((t) => t.fonts))];
let worker: Promise<Worker> | null = null;
let nextId = 1;
const waiting = new Map<number, { resolve: (pdf: Uint8Array) => void; reject: (e: Error) => void; progress?: (f: number) => void }>();

function typst(): Promise<Worker> {
  worker ??= (async () => {
    // Named by content hash (scripts/typst-assets.mjs), so the browser keeps it until it changes.
    const manifest = (await (await fetch("/resume/typst/manifest.json")).json()) as { worker: string };
    const w = new Worker(`/resume/typst/${manifest.worker}`, { type: "module" });
    w.onmessage = (e: MessageEvent<FromWorker>) => {
      const m = e.data;
      const job = waiting.get(m.id);
      if (!job) return;
      if (m.kind === "progress") job.progress?.(m.loaded / m.total);
      else {
        waiting.delete(m.id);
        if (m.kind === "done") job.resolve(m.pdf); else job.reject(new Error(m.message));
      }
    };
    w.onerror = (e) => {
      for (const job of waiting.values()) job.reject(new Error(e.message || "the layout engine stopped"));
      waiting.clear();
      worker = null;
    };
    return w;
  })();
  worker.catch(() => { worker = null; });
  return worker;
}

/** Whether this browser can run the compiler (WebAssembly in a module worker, and gzip streams). */
export const typstSupported = () => typeof WebAssembly === "object" && typeof DecompressionStream === "function" && typeof Worker === "function";

/** The resume laid out in a template, as PDF bytes. `progress` reports the first download, 0 to 1. */
export function compileResume(template: TemplateId, doc: ResumeDoc, progress?: (f: number) => void): Promise<Uint8Array> {
  const t = TEMPLATES.find((x) => x.id === template) ?? TEMPLATES[0];
  const id = nextId++;
  return new Promise((resolve, reject) => {
    waiting.set(id, { resolve, reject, progress });
    const msg: ToWorker = { id, source: t.source, data: JSON.stringify({ ...doc, paper: "a4" }), fonts: ALL_FONTS };
    typst().then((w) => w.postMessage(msg), (e: Error) => { waiting.delete(id); reject(e); });
  });
}

/** How many pages, and page 1 drawn into the canvas at the given CSS width (for the preview). */
export async function drawFirstPage(pdf: Uint8Array, canvas: HTMLCanvasElement, cssWidth: number): Promise<number> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  if (!pdfjs.GlobalWorkerOptions.workerPort) {
    pdfjs.GlobalWorkerOptions.workerPort = new Worker(new URL("pdfjs-dist/legacy/build/pdf.worker.min.mjs", import.meta.url), { type: "module" });
  }
  // pdf.js takes ownership of the bytes it is given; keep ours for the download.
  const task = pdfjs.getDocument({ data: pdf.slice() });
  const doc = await task.promise;
  try {
    const page = await doc.getPage(1);
    const base = page.getViewport({ scale: 1 });
    const ratio = Math.min(globalThis.devicePixelRatio || 1, 2);
    const viewport = page.getViewport({ scale: (cssWidth / base.width) * ratio });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${(viewport.height / ratio).toFixed(0)}px`;
    await page.render({ canvas, viewport }).promise;
    return doc.numPages;
  } finally {
    await task.destroy();
  }
}

/** Saves the PDF with a name like "Asha Rao resume (Classic).pdf". */
export function savePdf(pdf: Uint8Array, name: string, label: string) {
  const url = URL.createObjectURL(new Blob([pdf as BlobPart], { type: "application/pdf" }));
  const base = name.replace(/[^\p{L}\p{N} .-]+/gu, "").trim() || "Resume";
  const a = Object.assign(document.createElement("a"), { href: url, download: `${base} resume (${label}).pdf` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
