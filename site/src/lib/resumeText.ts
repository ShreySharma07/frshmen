// Pulls the text out of a resume PDF in the browser (docs/decisions.md, 2026-10-30: the Worker's
// 10 ms CPU can't parse PDFs). pdf.js is loaded only when someone picks a file, and its legacy
// build is used because budget Android phones often run older Chrome versions.
import { RESUME_TEXT_MAX } from "./supabase";

export async function resumeText(file: File): Promise<string> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  if (!pdfjs.GlobalWorkerOptions.workerPort) {
    // Parsing runs in a worker so a long resume doesn't freeze the page.
    pdfjs.GlobalWorkerOptions.workerPort = new Worker(new URL("pdfjs-dist/legacy/build/pdf.worker.min.mjs", import.meta.url), { type: "module" });
  }
  const task = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
  const doc = await task.promise;
  try {
    const pages: string[] = [];
    for (let n = 1; n <= doc.numPages; n++) {
      const content = await (await doc.getPage(n)).getTextContent();
      // Items are runs of text; hasEOL marks where the PDF broke the line.
      pages.push(content.items.map((it) => ("str" in it ? it.str + (it.hasEOL ? "\n" : "") : "")).join(""));
    }
    return tidy(pages.join("\n\n")).slice(0, RESUME_TEXT_MAX);
  } finally {
    await task.destroy();
  }
}

/** Collapses the runs of spaces and blank lines PDFs leave behind. */
export function tidy(text: string): string {
  return text.replace(/[ \t ]+/g, " ").replace(/ *\n */g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}
