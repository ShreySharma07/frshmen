// The resume structure reader (src/lib/resumeDoc.ts, src/lib/pdfLines.ts) and the four Typst
// templates (src/lib/resumeTemplates.ts). Run: npm test (node --test, no extra packages).
// Each template's PDF is read back into the same structure: if the reader can't read our own
// layouts, it won't read anyone's.
import assert from "node:assert/strict";
import { test } from "node:test";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { pdfLines } from "../src/lib/pdfLines.ts";
import { docFromPdfLines, docFromText, docToText, isHeading, setLine, type ResumeDoc } from "../src/lib/resumeDoc.ts";
import { TEMPLATES } from "../src/lib/resumeTemplates.ts";
import { FRESHER } from "./fixtures.ts";
import { compile } from "./typst.ts";

const strip = (d: ResumeDoc) => ({ ...d, from: "pdf" as const });

for (const t of TEMPLATES) {
  test(`${t.label}: compiles, and reads back as the same resume`, async () => {
    const { pdf, diagnostics } = await compile(t.id, FRESHER);
    assert.ok(pdf, `Typst failed: ${JSON.stringify(diagnostics)}`);
    const doc = docFromPdfLines(await pdfLines(pdfjs, pdf));
    assert.ok(doc, "read as one column");
    if (t.id === "compact") {
      // Compact joins the title and second row on one line ("ML Intern — Acme Labs"); the words survive.
      assert.equal(doc.name, FRESHER.name);
      assert.deepEqual(doc.sections.map((s) => s.heading.toLowerCase()), FRESHER.sections.map((s) => s.heading.toLowerCase()));
      assert.equal(docToText(doc).text.replace(/[^a-z0-9]/gi, "").length > 400, true);
      return;
    }
    const want = strip(FRESHER);
    assert.deepEqual({ ...doc, sections: doc.sections.map((s) => ({ ...s, heading: s.heading.toLowerCase() })) },
      { ...want, sections: want.sections.map((s) => ({ ...s, heading: s.heading.toLowerCase() })) });
  });
}

test("text round trip keeps the structure", () => {
  const doc = docFromText(docToText(FRESHER).text);
  assert.equal(doc.name, "Asha Rao");
  assert.equal(doc.sections.length, 4);
  const intern = doc.sections[1].items[0];
  assert.equal(intern.kind, "entry");
  if (intern.kind === "entry") {
    assert.deepEqual([intern.title, intern.right, intern.sub, intern.subRight], ["ML Intern", "May 2025 – Jul 2025", "Acme Labs", "Bengaluru"]);
    assert.equal(intern.bullets.length, 2);
  }
  assert.deepEqual(doc.sections[3].items, FRESHER.sections[3].items);
});

test("plain text: a dated line is an entry, a line before bullets is an entry", () => {
  const doc = docFromText("Ravi K\nravi@example.com\nPROJECTS\nChat app with FastAPI Jan 2024 - Mar 2024\n- Built websockets\nTodo CLI\n• Wrote it in Go\nSKILLS\nPython, Go");
  const [a, b] = doc.sections[0].items;
  assert.deepEqual(a.kind === "entry" && [a.title, a.right, a.bullets], ["Chat app with FastAPI", "Jan 2024 - Mar 2024", ["Built websockets"]]);
  assert.deepEqual(b.kind === "entry" && [b.title, b.bullets], ["Todo CLI", ["Wrote it in Go"]]);
  assert.deepEqual(doc.sections[1].items, [{ kind: "text", text: "Python, Go" }]);
});

test("headings", () => {
  for (const h of ["EDUCATION", "Work Experience", "Projects:", "OPEN SOURCE", "Positions of Responsibility"]) assert.ok(isHeading(h), h);
  for (const h of ["B.Tech CS, 2026", "Built a RAG search.", "• SKILLS", "Python, PyTorch"]) assert.ok(!isHeading(h), h);
});

test("a reworded line goes back into its field", () => {
  const { map } = docToText(FRESHER);
  const lines = docToText(FRESHER).text.split("\n").filter(Boolean);
  const n = lines.findIndex((l) => l.startsWith("• Wrote CUDA"));
  const next = setLine(FRESHER, map[n], "• Wrote CUDA kernels for verification: 30% less latency.");
  const p = next.sections[2].items[0];
  assert.equal(p.kind === "entry" && p.bullets[1], "Wrote CUDA kernels for verification: 30% less latency.");
  const t = lines.findIndex((l) => l.startsWith("ML Intern"));
  const renamed = setLine(FRESHER, map[t], "Machine Learning Intern — May 2025 – Jul 2025");
  const e = renamed.sections[1].items[0];
  assert.deepEqual(e.kind === "entry" && [e.title, e.right], ["Machine Learning Intern", "May 2025 – Jul 2025"]);
  assert.equal(FRESHER.sections[2].items[0].kind === "entry" && FRESHER.sections[2].items[0].bullets[1], "Wrote CUDA kernels for the verification step.");
});

test("a two-column layout is refused, not misread", () => {
  const line = (y: number, l: string, r: string) => ({ page: 1, y, width: 595, segments: [
    { text: l, x: 40, xEnd: 200, size: 10, bold: false, italic: false },
    { text: r, x: 320, xEnd: 560, size: 10, bold: false, italic: false }] });
  const lines = Array.from({ length: 12 }, (_, i) => line(800 - i * 14, `Left column text ${i}`, `Right column sentence number ${i} about projects`));
  assert.equal(docFromPdfLines(lines), null);
});

test("a resume exported from Word reads as entries, bullets and text", async () => {
  const { readFileSync } = await import("node:fs");
  const data = new Uint8Array(readFileSync(new URL("./fixtures/word-resume.pdf", import.meta.url)));
  const doc = docFromPdfLines(await pdfLines(pdfjs, data));
  assert.ok(doc);
  assert.equal(doc.name, "Rohan Mehta");
  assert.deepEqual(doc.sections.map((s) => s.heading), ["EDUCATION", "WORK EXPERIENCE", "PROJECTS", "SKILLS"]);
  const job = doc.sections[1].items[0];
  assert.deepEqual(job.kind === "entry" && [job.title, job.right, job.sub, job.subRight, job.bullets.length],
    ["Backend Developer Intern", "Jan 2025 – Jun 2025", "Example Payments Pvt Ltd", "Mumbai", 2]);
  assert.match(job.kind === "entry" ? job.bullets[0] : "", /^Built a Django REST API .* alerts on failures\.$/); // a wrapped bullet is one bullet
  assert.deepEqual(doc.sections[3].items, [{ kind: "text", text: "Python, Django, FastAPI, PostgreSQL, Docker, React Native" }]);
});

test("bold font names, LaTeX's included", async () => {
  const { isBoldName } = await import("../src/lib/pdfLines.ts");
  for (const n of ["ABCDEF+Arial-BoldMT", "Calibri-Bold", "IBMPlexSans-SemiBold", "CMBX10", "HelveticaNeue-Bd"]) assert.ok(isBoldName(n), n);
  for (const n of ["CMR10", "Calibri", "ArialMT", "Abadi"]) assert.ok(!isBoldName(n), n);
});
