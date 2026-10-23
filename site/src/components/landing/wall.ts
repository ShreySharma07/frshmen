// The Highlighter's material: real deciding lines from postings. The starter set (from the real
// postings in tests/fixtures, made by scripts/landing_wall_snapshot.py) shows at once; a live
// sample from /api/evidence replaces it when the API answers.
import type { EvidenceLine } from "@/lib/api";
import snapshot from "./wall-snapshot.json";

export const STARTER = snapshot as EvidenceLine[];

/** The reader's experience, as the picker offers it: the most years they have. */
export const YEARS = [
  { years: 0, label: "Fresher" },
  { years: 2, label: "1–2 years" },
  { years: 5, label: "3–5 years" },
  { years: 10, label: "5+ years" },
] as const;

export type Fit = "fits" | "over" | "unclear";

/** Does this posting take someone with `years`? Same rule as the job list's years filter:
 *  a stated minimum decides; a fresher label fits everyone; a "Senior"-style label without a
 *  number fits only the most experienced; a posting that never says stays unclear. */
export function fit(line: EvidenceLine, years: number): Fit {
  if (line.level === "fresher") return "fits";
  if (line.yoe_min != null) return line.yoe_min <= years ? "fits" : "over";
  if (line.level === "experienced") return years >= 10 ? "fits" : "over";
  return "unclear";
}

/** Fills `count` rows by cycling the lines, shuffled once with a fixed seed so the wall looks
 *  the same on the server and in the browser. */
export function rows(lines: EvidenceLine[], count: number): EvidenceLine[] {
  if (!lines.length) return [];
  const order = lines.map((_, i) => i);
  let seed = 7;
  for (let i = order.length - 1; i > 0; i--) {
    seed = (seed * 16807) % 2147483647;
    const j = seed % (i + 1);
    [order[i], order[j]] = [order[j], order[i]];
  }
  return Array.from({ length: count }, (_, i) => lines[order[i % order.length]]);
}

/** One line of the wall: the requirement, trimmed to fit a row. */
export const clip = (text: string, max = 78) => (text.length > max ? text.slice(0, max - 1).trimEnd() + "…" : text);
