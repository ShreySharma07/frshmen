// A resume's structure (docs/decisions.md, 2026-11-17): what the templates lay out and the editor's
// fields. Read from the uploaded PDF's text with its positions and fonts (lib/pdfLines.ts), or, with
// no PDF, from the saved text. Rules only, no model: a line is a heading, an entry, a bullet or text
// because of where it sits and how it is set, so a wrong read can be explained and fixed.
// No imports: tests run this file directly under Node (site/tests/resumeDoc.test.ts).

/** One job, project or degree: a bold first row (title … right), an optional second row, bullets. */
export interface Entry { kind: "entry"; title: string; right: string; sub: string; subRight: string; bullets: string[] }
export type Item = Entry | { kind: "text"; text: string } | { kind: "bullet"; text: string };
export interface Section { heading: string; items: Item[] }
export interface ResumeDoc { v: 1; name: string; contact: string[]; sections: Section[]; from: "pdf" | "text" }

/** A piece of a PDF line: text set in one place with one font (lib/pdfLines.ts makes these). */
export interface Segment { text: string; x: number; xEnd: number; size: number; bold: boolean; italic: boolean }
export interface PdfLine { page: number; y: number; width: number; segments: Segment[] }

export const emptyEntry = (): Entry => ({ kind: "entry", title: "", right: "", sub: "", subRight: "", bullets: [] });

// Word and Google Docs draw bullets from Symbol or Wingdings, which land in Unicode's private-use area.
const BULLET = /^\s*(?:[•●▪◦∙‣·■□➢➤►✓✔\ue000-\uf8ff]|[-–*](?=\s))\s*/;
const KNOWN = /^(summary|profile|objective|about( me)?|education|(work |professional |relevant )?experience|employment|internships?|(personal |academic |key |selected )?projects?|(technical )?skills|skills (&|and) (tools|interests)|tools|certifications?|courses|achievements|awards|honou?rs|publications|research|leadership|activities|extra-?curriculars?( activities)?|volunteering|languages|interests|hobbies|contact|(relevant )?coursework|positions? of responsibility|open source)\s*:?$/i;
const MONTH = "(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\\.?";
const WHEN = `(?:${MONTH}\\s*'?\\d{2,4}|(?:19|20)\\d{2}|\\d{1,2}/(?:19|20)?\\d{2})`;
/** "Jun 2024 – Aug 2024", "2022 - Present", "May 2025": a date or a range at the end of a line. */
export const DATE_AT_END = new RegExp(`\\s*(?:\\||,|·)?\\s*(${WHEN}(?:\\s*(?:–|—|-|to)\\s*(?:${WHEN}|present|current|now|ongoing))?)\\s*$`, "i");

const squash = (s: string) => s.replace(/\s+/g, " ").trim();

/** A section heading: a known section name, or a short line in capitals without digits ("OPEN SOURCE"). */
export function isHeading(line: string): boolean {
  const t = squash(line);
  if (!t || t.length > 40 || BULLET.test(t) || /[.,;]$/.test(t)) return false;
  return KNOWN.test(t) || (/[A-Z]/.test(t) && t === t.toUpperCase() && !/\d/.test(t) && t.split(" ").length <= 4);
}

// --- From the PDF ---------------------------------------------------------------------------------

interface Row { text: string; left: string; right: string; x: number; size: number; bold: boolean; italic: boolean; page: number }

function rows(lines: PdfLine[]): Row[] {
  return lines.map((l) => {
    const segs = l.segments.filter((s) => s.text.trim());
    // A wide gap past the middle of the page starts the right-hand column of a row (dates, places).
    let cut = segs.length;
    for (let i = 1; i < segs.length; i++) {
      const gap = segs[i].x - segs[i - 1].xEnd;
      if (gap > Math.max(3 * segs[i].size, l.width * 0.06) && segs[i].x > l.width * 0.45) { cut = i; break; }
    }
    const left = squash(segs.slice(0, cut).map((s) => s.text).join(" "));
    const right = squash(segs.slice(cut).map((s) => s.text).join(" "));
    const first = segs[0];
    return { text: squash(`${left} ${right}`), left, right, x: first?.x ?? 0, size: Math.max(...segs.map((s) => s.size), 0),
      bold: Boolean(first?.bold), italic: Boolean(first?.italic), page: l.page };
  }).filter((r) => r.text);
}

/**
 * A section name in a left-hand label column shares its baseline with the section's first line
 * (the "Sidebar labels" layout): it becomes a line of its own, above that line.
 */
function splitLabel(l: PdfLine): PdfLine[] {
  const [first, next] = l.segments;
  if (!next || !isHeading(first.text) || next.x - first.xEnd < next.size || first.x > l.width * 0.3) return [l];
  return [{ ...l, segments: [first] }, { ...l, segments: l.segments.slice(1) }];
}

/** The size most of the text is set in. */
function bodySize(lines: PdfLine[]): number {
  const weight = new Map<number, number>();
  for (const s of lines.flatMap((l) => l.segments)) {
    const k = Math.round(s.size * 2) / 2;
    weight.set(k, (weight.get(k) ?? 0) + s.text.length);
  }
  return [...weight.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? 10;
}

/**
 * The structure of a resume from its PDF lines. Returns null when the layout can't be read as one
 * column (a two-column resume interleaves its columns line by line); the caller then reads the text.
 */
export function docFromPdfLines(input: PdfLine[]): ResumeDoc | null {
  const lines = input.flatMap(splitLabel);
  const all = rows(lines);
  if (!all.length) return null;
  const body = bodySize(lines);
  const margin = Math.min(...all.filter((r) => !isHeading(r.text)).map((r) => r.x));
  // Two columns side by side: many rows carry long right-hand text that isn't a date or a place.
  const odd = all.filter((r) => r.right && r.right.length > 28 && !DATE_AT_END.test(r.right)).length;
  if (odd > Math.max(3, all.length * 0.2)) return null;

  const top = all.slice(0, 4).filter((r) => r.page === all[0].page);
  const biggest = top.reduce((a, b) => (b.size > a.size ? b : a), top[0]);
  const nameRow = biggest.size >= body * 1.2 ? biggest : all[0];
  const doc: ResumeDoc = { v: 1, name: nameRow.text, contact: [], sections: [], from: "pdf" };
  // A name set large with the contact details beside it on the same line (Compact): split by size.
  const nameLine = lines[all.indexOf(nameRow)];
  const small = nameLine?.segments.filter((g) => g.text.trim() && g.size < body * 1.2) ?? [];
  if (nameRow.size >= body * 1.2 && small.length) {
    doc.name = squash(nameLine.segments.filter((g) => g.size >= body * 1.2).map((g) => g.text).join(" "));
    doc.contact.push(squash(small.map((g) => g.text).join(" ")));
  }
  const headingRow = (r: Row) => r !== nameRow && !r.right && (isHeading(r.text) || (r.size >= body * 1.12 && r.text.split(" ").length <= 4 && !BULLET.test(r.text) && !/[.,;]$/.test(r.text)));

  let section: Section | null = null;
  let lastBulletX = Infinity;
  for (const r of all.slice(all.indexOf(nameRow) + 1)) {
    if (headingRow(r)) {
      section = { heading: r.text.replace(/:$/, ""), items: [] };
      doc.sections.push(section);
      lastBulletX = Infinity;
      continue;
    }
    if (!section) { doc.contact.push(r.right ? `${r.left} · ${r.right}` : r.text); continue; }
    const items = section.items;
    const last = items[items.length - 1];
    const entry = last?.kind === "entry" ? last : null;
    if (BULLET.test(r.left)) {
      const text = squash(`${r.left.replace(BULLET, "")} ${r.right}`);
      if (entry) entry.bullets.push(text); else items.push({ kind: "bullet", text });
      lastBulletX = r.x;
      continue;
    }
    // A wrapped bullet: indented past the margin, under a bullet, in the body face.
    const wrapped = lastBulletX !== Infinity && !r.right && !r.bold && r.x > margin + body * 0.5 && r.x >= lastBulletX - 1;
    if (wrapped && ((entry && entry.bullets.length) || last?.kind === "bullet")) {
      if (entry) entry.bullets[entry.bullets.length - 1] += ` ${r.text}`; else (last as { text: string }).text += ` ${r.text}`;
      continue;
    }
    lastBulletX = Infinity;
    const openEntry = entry && !entry.bullets.length && !entry.sub;
    if (openEntry && !r.bold) { entry.sub = r.left; entry.subRight = r.right; continue; }
    if (r.bold || r.right) { items.push({ ...emptyEntry(), title: r.left, right: r.right }); continue; }
    if (last?.kind === "text" && /^[a-z(]/.test(r.text)) { last.text += ` ${r.text}`; continue; }
    items.push({ kind: "text", text: r.text });
  }
  return tidy(doc);
}

// --- From plain text (no PDF, or a layout the PDF reader refused) ---------------------------------

/** The structure of a resume from its plain text: the same rules, with only the words to go on. */
export function docFromText(text: string): ResumeDoc {
  const lines = text.split(/\r?\n/).map(squash).filter(Boolean);
  const doc: ResumeDoc = { v: 1, name: lines[0] ?? "", contact: [], sections: [], from: "text" };
  let section: Section | null = null;
  lines.slice(1).forEach((line, i, rest) => {
    if (isHeading(line)) { section = { heading: line.replace(/:$/, ""), items: [] }; doc.sections.push(section); return; }
    if (!section) { doc.contact.push(line); return; }
    const items = (section as Section).items;
    const last = items[items.length - 1];
    const entry = last?.kind === "entry" ? last : null;
    if (BULLET.test(line)) {
      const t = line.replace(BULLET, "");
      if (entry) entry.bullets.push(t); else items.push({ kind: "bullet", text: t });
      return;
    }
    const [left, right] = splitRight(line);
    const nextIsBullet = BULLET.test(rest[i + 1] ?? "");
    if (entry && !entry.bullets.length && !entry.sub && !isHeading(line)) { entry.sub = left; entry.subRight = right; return; }
    if (right || nextIsBullet) { items.push({ ...emptyEntry(), title: left, right }); return; }
    items.push({ kind: "text", text: line });
  });
  return tidy(doc);
}

/** "Title — right" (as docToText writes it) or a line ending in a date: [left, right]. */
function splitRight(line: string): [string, string] {
  const dash = line.lastIndexOf(" — ");
  if (dash > 0) return [line.slice(0, dash).trim(), line.slice(dash + 3).trim()];
  const m = line.match(DATE_AT_END);
  if (m && m.index && m.index > 3) return [line.slice(0, m.index).replace(/[\s|,·–-]+$/, ""), m[1]];
  return [line, ""];
}

/** Trimmed, with empty entries, lines and sections dropped. */
export function tidy(doc: ResumeDoc): ResumeDoc {
  const sections = doc.sections.map((s) => ({
    heading: squash(s.heading),
    items: s.items.map((it): Item => it.kind === "entry"
      ? { ...it, title: squash(it.title), right: squash(it.right), sub: squash(it.sub), subRight: squash(it.subRight), bullets: it.bullets.map(squash).filter(Boolean) }
      : { ...it, text: squash(it.text) })
      .filter((it) => (it.kind === "entry" ? it.title || it.right || it.sub || it.bullets.length : it.text)),
  })).filter((s) => s.heading || s.items.length);
  return { ...doc, name: squash(doc.name), contact: doc.contact.map(squash).filter(Boolean), sections };
}

// --- Back to text, for the agent, fit checks and "Ask agent to improve" ----------------------------

/** Where a line of docToText's text came from, so a reworded line goes back into its field. */
export type Path = { f: "name" } | { f: "contact"; c: number } | { f: "heading"; s: number }
  | { f: "title" | "sub"; s: number; i: number } | { f: "bullet"; s: number; i: number; b: number } | { f: "text"; s: number; i: number };

/** The resume as plain text (what resume_text stores), and the field each non-empty line came from. */
export function docToText(doc: ResumeDoc): { text: string; map: Path[] } {
  const out: string[] = [];
  const map: Path[] = [];
  const put = (line: string, p: Path) => { if (line.trim()) { out.push(line); map.push(p); } };
  put(doc.name, { f: "name" });
  doc.contact.forEach((c, k) => put(c, { f: "contact", c: k }));
  doc.sections.forEach((sec, s) => {
    out.push("");
    put(sec.heading.toUpperCase(), { f: "heading", s });
    sec.items.forEach((it, i) => {
      if (it.kind === "entry") {
        put([it.title, it.right].filter(Boolean).join(" — "), { f: "title", s, i });
        put([it.sub, it.subRight].filter(Boolean).join(" — "), { f: "sub", s, i });
        it.bullets.forEach((b, k) => put(`• ${b}`, { f: "bullet", s, i, b: k }));
      } else put(it.kind === "bullet" ? `• ${it.text}` : it.text, { f: "text", s, i });
    });
  });
  return { text: out.join("\n").replace(/\n{3,}/g, "\n\n").trim(), map };
}

/** A copy of the resume with one line (as docToText wrote it) replaced by new wording. */
export function setLine(doc: ResumeDoc, path: Path, line: string): ResumeDoc {
  const next: ResumeDoc = structuredClone(doc);
  const t = squash(line);
  if (path.f === "name") next.name = t;
  else if (path.f === "contact") next.contact[path.c] = t;
  else if (path.f === "heading") next.sections[path.s].heading = t;
  else {
    const it = next.sections[path.s].items[path.i];
    if (path.f === "bullet" && it.kind === "entry") it.bullets[path.b] = t.replace(BULLET, "");
    else if ((path.f === "title" || path.f === "sub") && it.kind === "entry") {
      const [left, right] = t.includes(" — ") ? splitRight(t) : [t, path.f === "title" ? it.right : it.subRight];
      if (path.f === "title") { it.title = left; it.right = right; } else { it.sub = left; it.subRight = right; }
    } else if (it.kind !== "entry") it.text = t.replace(BULLET, "");
  }
  return next;
}

export const docStats = (doc: ResumeDoc) => ({
  sections: doc.sections.length,
  entries: doc.sections.reduce((n, s) => n + s.items.filter((i) => i.kind === "entry").length, 0),
});
