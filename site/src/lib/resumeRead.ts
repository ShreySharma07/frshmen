// A resume PDF read into structure and text in the browser (docs/decisions.md, 2026-11-17): on upload,
// and once for people who signed up before resume_doc existed, from the PDF they stored then.
import { pdfLines } from "./pdfLines";
import { docFromPdfLines, docFromText, docToText, type ResumeDoc } from "./resumeDoc";
import { resumeText } from "./resumeText";
import { RESUME_BUCKET, RESUME_TEXT_MAX, supabase } from "./supabase";

async function pdfjsReady() {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  if (!pdfjs.GlobalWorkerOptions.workerPort) {
    pdfjs.GlobalWorkerOptions.workerPort = new Worker(new URL("pdfjs-dist/legacy/build/pdf.worker.min.mjs", import.meta.url), { type: "module" });
  }
  return pdfjs;
}

/** Structure from the PDF's layout; a layout it can't read as one column falls back to its words. */
export async function readResume(file: File): Promise<{ doc: ResumeDoc; text: string }> {
  const lines = await pdfLines(await pdfjsReady(), new Uint8Array(await file.arrayBuffer()));
  const fromLayout = docFromPdfLines(lines);
  const doc = fromLayout ?? docFromText(await resumeText(file));
  return { doc, text: docToText(doc).text.slice(0, RESUME_TEXT_MAX) };
}

/** The PDF stored at sign-up (private bucket, the person's own path), or null if there is none. */
export async function storedResume(path: string): Promise<File | null> {
  const { data, error } = await supabase().storage.from(RESUME_BUCKET).download(path);
  if (error || !data) return null;
  return new File([data], "resume.pdf", { type: "application/pdf" });
}
