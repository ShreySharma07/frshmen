// Turns a posting's plain text into display blocks, and finds the facts the fit card shows.
// Only what the posting itself says: nothing here guesses or scores.
import type { JobDetail } from "./api";

export type Block = { kind: "heading"; text: string } | { kind: "para"; text: string } | { kind: "list"; items: string[] };

/** Short lines without end punctuation read as headings; "-", "•" or "*" lines as bullets. */
export function blocks(text: string): Block[] {
  const out: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const bullet = /^[-•*]\s+/.exec(line);
    if (bullet) {
      const item = line.slice(bullet[0].length);
      const last = out[out.length - 1];
      if (last?.kind === "list") last.items.push(item);
      else out.push({ kind: "list", items: [item] });
    } else if (line.length <= 60 && !/[.,;:!]$/.test(line)) {
      out.push({ kind: "heading", text: line });
    } else {
      out.push({ kind: "para", text: line });
    }
  }
  return out;
}

// Tools and frameworks worth spotting. Case-sensitive whole words, so "Go" the verb and "Ray" the
// name don't count unless written like the tool.
const TECH = ["Python", "PyTorch", "TensorFlow", "JAX", "CUDA", "Triton", "Spark", "Ray", "Beam", "Dask", "Kubernetes",
  "Docker", "Rust", "Java", "C++", "TypeScript", "React", "SQL", "Postgres", "Kafka", "Airflow", "AWS", "GCP", "Azure",
  "LLM", "RAG", "FastAPI", "Django", "Terraform", "vLLM", "MLflow", "Kotlin", "Swift"];
const word = (t: string) => new RegExp(`(?<![\\w+])${t.replace(/[+]/g, "\\+")}(?![\\w+])`);

export function techMentioned(text: string): string[] {
  return TECH.filter((t) => word(t).test(text));
}

/** The posting's own sentence welcoming early-career or new-grad candidates, if any. */
export function earlyCareer(text: string): string | null {
  return text.split(/(?<=[.!?])\s+|\n/).map((s) => s.trim().replace(/^[-•*]\s*/, ""))
    .find((s) => s.length < 220 && /early[- ]career|new grad|recent grad|fresh graduate/i.test(s)) ?? null;
}

/** Splits text so tech terms and "N+ years" phrases can be shown as keyword pills. */
export function highlightParts(text: string, tech: string[]): { text: string; mark: boolean }[] {
  const terms = [...tech.map((t) => t.replace(/[+]/g, "\\+")), String.raw`\d+\s*[–-]\s*\d+\+?\s+years`, String.raw`\d+\+\s+years`];
  const re = new RegExp(`((?<![\\w+])(?:${terms.join("|")})(?![\\w+]))`, "g");
  // split() with one capture group alternates plain text and matches; mark before dropping empties.
  return text.split(re).map((part, i) => ({ text: part, mark: i % 2 === 1 })).filter((p) => p.text);
}

export const FAMILY: Record<string, string> = { ai_ml: "AI/ML", backend: "Backend", mobile: "Mobile", generic_swe: "Software engineering with Python + AI/ML" };
export const ATS: Record<string, string> = { ashby: "Ashby", greenhouse: "Greenhouse", lever: "Lever", workday: "Workday", keka: "Keka",
  workable: "Workable", smartrecruiters: "SmartRecruiters", eightfold: "Eightfold", oracle: "Oracle Recruiting", careersite: "Careers site" };

export const isDetail = (j: unknown): j is JobDetail => typeof j === "object" && j !== null && "description_text" in j;
