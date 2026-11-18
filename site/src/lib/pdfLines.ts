// A resume PDF as lines of positioned, styled text (docs/decisions.md, 2026-11-17), for
// lib/resumeDoc.ts to read its structure from. pdf.js reports each run of text with its position
// (transform), size and font; the font's own name says bold or italic ("…-Bold", "…-Italic").
// Takes the pdf.js module as an argument so tests can pass the Node build (no imports of its own).
import type { PdfLine, Segment } from "./resumeDoc";

type PdfJs = typeof import("pdfjs-dist/legacy/build/pdf.mjs");
interface Run { str: string; x: number; y: number; w: number; size: number; bold: boolean; italic: boolean }

export async function pdfLines(pdfjs: PdfJs, data: Uint8Array): Promise<PdfLine[]> {
  // fontExtraProperties: the font's name and style flags come back with it (unused for drawing, so off by default).
  const task = pdfjs.getDocument({ data, fontExtraProperties: true });
  const doc = await task.promise;
  try {
    const out: PdfLine[] = [];
    for (let n = 1; n <= Math.min(doc.numPages, 4); n++) {
      const page = await doc.getPage(n);
      await page.getOperatorList(); // loads the page's fonts, so their names can be read below
      const content = await page.getTextContent();
      const [x0, , x1] = page.view;
      const runs: Run[] = [];
      for (const it of content.items) {
        if (!("str" in it) || !it.str.trim()) continue;
        const [, , c, d, e, f] = it.transform as number[];
        let font: { name?: string; bold?: boolean; italic?: boolean } = {};
        try { font = page.commonObjs.get(it.fontName) ?? {}; } catch { /* a font pdf.js couldn't load: plain */ }
        const name = font.name ?? "";
        runs.push({ str: it.str, x: e - x0, y: f, w: it.width, size: Math.hypot(c, d) || it.height,
          bold: Boolean(font.bold) || isBoldName(name), italic: Boolean(font.italic) || /italic|oblique|cmti|cmsl/i.test(name) });
      }
      out.push(...group(runs, n, x1 - x0));
    }
    return out;
  } finally {
    await task.destroy();
  }
}

/** "Arial-BoldMT", "Calibri-Bold", "IBMPlexSans-SemiBold", and LaTeX's Computer Modern bold "CMBX10". */
export const isBoldName = (name: string) => /bold|black|heavy|semibold|demi|[-,]bd\b|cmbx|sfbx|lmroman\d*-bold/i.test(name);

/** Runs on the same baseline are one line; within it, neighbouring runs in the same font are one segment. */
function group(runs: Run[], page: number, width: number): PdfLine[] {
  runs.sort((a, b) => b.y - a.y || a.x - b.x);
  const lines: Run[][] = [];
  for (const r of runs) {
    const line = lines[lines.length - 1];
    if (line && Math.abs(line[0].y - r.y) <= Math.max(line[0].size, r.size) * 0.45) line.push(r);
    else lines.push([r]);
  }
  return lines.map((line) => {
    line.sort((a, b) => a.x - b.x);
    const segments: Segment[] = [];
    for (const r of line) {
      const prev = segments[segments.length - 1];
      const gap = prev ? r.x - prev.xEnd : Infinity;
      if (prev && prev.bold === r.bold && prev.italic === r.italic && gap < r.size * 1.2) {
        prev.text += (gap > r.size * 0.12 && !prev.text.endsWith(" ") && !r.str.startsWith(" ") ? " " : "") + r.str;
        prev.xEnd = r.x + r.w;
        prev.size = Math.max(prev.size, r.size);
      } else segments.push({ text: r.str, x: r.x, xEnd: r.x + r.w, size: r.size, bold: r.bold, italic: r.italic });
    }
    return { page, y: line[0].y, width, segments };
  });
}
