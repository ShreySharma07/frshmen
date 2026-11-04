// The tailored resume as a one-page, text-based PDF (docs/decisions.md, 2026-11-04: our own
// template, built in the browser). Standard Helvetica keeps it small and readable by applicant
// tracking systems; pdf-lib loads only when someone downloads.
import type { TailoredSection } from "./tracker";

const PAGE = { w: 595.28, h: 841.89 }; // A4 in points
const MARGIN = 50;

/** Helvetica can only draw WinAnsi characters; swap or drop the rest instead of failing. */
function printable(text: string): string {
  return text
    .replace(/₹/g, "Rs.").replace(/[‐-‒]/g, "-").replace(/ /g, " ")
    .replace(/[^\x20-\x7e\xa0-\xff–—‘’“”•…€]/g, "");
}

export async function resumePdf(name: string, sections: TailoredSection[]): Promise<Blob> {
  const { PDFDocument, StandardFonts, rgb } = await import("pdf-lib");
  const doc = await PDFDocument.create();
  doc.setTitle(`${name} resume`);
  const regular = await doc.embedFont(StandardFonts.Helvetica);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);
  let page = doc.addPage([PAGE.w, PAGE.h]);
  let y = PAGE.h - MARGIN;
  const width = PAGE.w - 2 * MARGIN;
  const ink = rgb(0.07, 0.07, 0.09), muted = rgb(0.4, 0.4, 0.45);

  const room = (needed: number) => {
    if (y - needed < MARGIN) { page = doc.addPage([PAGE.w, PAGE.h]); y = PAGE.h - MARGIN; }
  };
  const wrap = (text: string, size: number, font: typeof regular, max: number) => {
    const lines: string[] = [];
    let line = "";
    for (const word of text.split(/\s+/).filter(Boolean)) {
      const next = line ? `${line} ${word}` : word;
      if (font.widthOfTextAtSize(next, size) > max && line) { lines.push(line); line = word; } else line = next;
    }
    if (line) lines.push(line);
    return lines;
  };

  page.drawText(printable(name), { x: MARGIN, y: y - 18, size: 18, font: bold, color: ink });
  y -= 30;
  for (const [s, sec] of sections.entries()) {
    const heading = printable(sec.heading).toUpperCase();
    const bulleted = Boolean(heading) || s > 0; // a heading-less first section is the contact line
    if (heading) {
      room(30);
      y -= 8;
      page.drawText(heading, { x: MARGIN, y: y - 10, size: 9.5, font: bold, color: muted });
      y -= 14;
      page.drawLine({ start: { x: MARGIN, y }, end: { x: PAGE.w - MARGIN, y }, thickness: 0.5, color: muted });
      y -= 6;
    }
    for (const item of sec.lines) {
      const indent = bulleted ? 12 : 0;
      for (const [k, text] of wrap(printable(item.text), 10, regular, width - indent).entries()) {
        room(14);
        if (bulleted && k === 0) page.drawText("•", { x: MARGIN, y: y - 10, size: 10, font: regular, color: ink });
        page.drawText(text, { x: MARGIN + indent, y: y - 10, size: 10, font: regular, color: ink });
        y -= 13.5;
      }
      y -= 1.5;
    }
  }
  const bytes = await doc.save();
  return new Blob([bytes as BlobPart], { type: "application/pdf" });
}
