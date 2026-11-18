// The agent's resume editor (docs/decisions.md, 2026-11-16 and 2026-11-17): the agent's suggested
// rewording (api/src/tailor.py improve, held to the resume by the same guard as a tailored resume),
// and a plain PDF for browsers that can't run the template engine (the tailored resume's pdf-lib
// template, lib/resumePdf.ts).
import type { ResumeDoc } from "./resumeDoc";
import { resumePdf } from "./resumePdf";
import { api, type TailoredSection } from "./tracker";

export interface Improved { name: string; note: string; sections: TailoredSection[]; left_out: string[]; kept_original: number; remaining: number }

export const improveResume = (text: string): Promise<Improved> =>
  api("/api/agent/resume/improve", { method: "POST", body: JSON.stringify({ text }) });

/** A changed line: the guard kept neither an invented skill nor a number, and the wording differs. */
export const isChange = (l: { text: string; original: string; kept_original: boolean }) =>
  !l.kept_original && l.text.trim() !== l.original.trim();

const line = (text: string) => ({ text, original: text, sources: [], kept_original: false, reason: null });

/** Downloads the resume as a one-page, text-based PDF without the template engine. */
export async function exportPlainPdf(doc: ResumeDoc): Promise<void> {
  const sections: TailoredSection[] = [
    { heading: "", lines: doc.contact.map(line) },
    ...doc.sections.map((s) => ({
      heading: s.heading,
      lines: s.items.flatMap((it) => it.kind === "entry"
        ? [[it.title, it.right].filter(Boolean).join(" · "), [it.sub, it.subRight].filter(Boolean).join(" · "), ...it.bullets].filter(Boolean).map(line)
        : [line(it.text)]),
    })),
  ].filter((s) => s.lines.length);
  const blob = await resumePdf(doc.name || "Resume", sections);
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: `${doc.name.replace(/[^\p{L}\p{N} .-]+/gu, "").trim() || "Resume"} resume.pdf` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
