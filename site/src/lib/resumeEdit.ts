// The agent's resume editor (docs/decisions.md, 2026-11-16, concept A): the saved resume text, the
// agent's suggested rewording (api/src/tailor.py improve, held to the resume by the same guard as a
// tailored resume), and a PDF of whatever the editor holds.
import { resumePdf } from "./resumePdf";
import { api, type TailoredSection } from "./tracker";

export interface Improved { name: string; note: string; sections: TailoredSection[]; left_out: string[]; kept_original: number; remaining: number }

export const improveResume = (text: string): Promise<Improved> =>
  api("/api/agent/resume/improve", { method: "POST", body: JSON.stringify({ text }) });

/** The lines the API numbers, the same way (tailor.resume_lines): trimmed, non-empty, at most 150. */
export function resumeLines(text: string): string[] {
  return text.split(/\r?\n/).map((l) => l.trim().slice(0, 400)).filter(Boolean).slice(0, 150);
}

/** A changed line: the guard kept neither an invented skill nor a number, and the wording differs. */
export const isChange = (l: { text: string; original: string; kept_original: boolean }) =>
  !l.kept_original && l.text.trim() !== l.original.trim();

/**
 * The editor's text after review: each section's heading, then each line as accepted (the rewrite)
 * or undone (the original). Lines the rewrite didn't use are kept, never lost: those above the first
 * line it used (name, contact) stay on top, the rest go at the end, except old copies of a heading.
 */
export function applyReview(original: string, result: Improved, accepted: (si: number, li: number) => boolean): string {
  const lines = resumeLines(original);
  const used = new Set(result.sections.flatMap((s) => s.lines.flatMap((l) => l.sources)));
  const first = Math.min(...used);
  const headings = new Set(result.sections.map((s) => s.heading.trim().toLowerCase()).filter(Boolean));
  // Old copies of a heading the rewrite repeats are dropped wherever they were.
  const unused = lines.map((text, i) => ({ text, n: i + 1 }))
    .filter(({ n, text }) => !used.has(n) && !headings.has(text.replace(/:$/, "").trim().toLowerCase()));
  const top = unused.filter(({ n }) => n < first).map((u) => u.text);
  const rest = unused.filter(({ n }) => n >= first).map((u) => u.text);
  const body = result.sections.map((s, si) => [
    ...(s.heading ? [s.heading] : []),
    ...s.lines.map((l, li) => (isChange(l) && !accepted(si, li) ? l.original : l.text)),
  ].join("\n"));
  return [top.join("\n"), ...body, rest.join("\n")].filter(Boolean).join("\n\n");
}

const KNOWN = /^(summary|profile|objective|about( me)?|education|(work |professional )?experience|internships?|(personal |academic |key )?projects?|(technical )?skills|certifications?|achievements|awards|publications|research|leadership|activities|extra-?curriculars?|languages|interests|contact|(relevant )?coursework|positions? of responsibility)\s*:?$/i;

/** A heading: a known section name, or a short all-capitals line without digits ("OPEN SOURCE"). */
export function isHeading(line: string): boolean {
  const t = line.trim();
  return KNOWN.test(t) || (t.length <= 32 && /[A-Z]/.test(t) && t === t.toUpperCase() && !/\d/.test(t) && t.split(/\s+/).length <= 4);
}

/** Plain text → the sections the PDF template draws; a first line that is the person's name is the title. */
export function textToSections(text: string, name: string): { name: string; sections: TailoredSection[] } {
  const lines = resumeLines(text);
  let title = name.trim();
  if (lines.length && (!title || lines[0].toLowerCase() === title.toLowerCase())) title = lines.shift() ?? title;
  const sections: TailoredSection[] = [{ heading: "", lines: [] }];
  for (const line of lines) {
    if (isHeading(line)) sections.push({ heading: line.replace(/:$/, ""), lines: [] });
    else {
      const clean = line.replace(/^[•●▪\-*–]\s*/, "");
      sections[sections.length - 1].lines.push({ text: clean, original: clean, sources: [], kept_original: false, reason: null });
    }
  }
  return { name: title || "Resume", sections: sections.filter((s) => s.lines.length) };
}

/** Downloads the editor's text as a one-page, text-based PDF (the tailored resume's template). */
export async function exportResumePdf(text: string, name: string): Promise<void> {
  const doc = textToSections(text, name);
  const blob = await resumePdf(doc.name, doc.sections);
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: `${doc.name.replace(/[^\w .-]+/g, "").trim() || "Resume"} resume.pdf` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
