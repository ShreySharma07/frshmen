// Which catalogued skills a resume names: the browser side of extract/skills.py, with the same
// catalogue (skills.json, exported from config/skills.yaml) and the same whole-word rule.
import catalogue from "./skills.json";

interface Entry { name: string; terms: string[]; exact: boolean }

const escape = (t: string) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const PATTERNS = (catalogue as Entry[]).map((s) => ({
  name: s.name,
  re: new RegExp(`(?<![A-Za-z0-9+#])(?:${[...s.terms].sort((a, b) => b.length - a.length).map(escape).join("|")})(?![A-Za-z0-9+#])`, s.exact ? "" : "i"),
}));

export function skillsIn(text: string | null | undefined): Set<string> {
  return new Set(text ? PATTERNS.filter((p) => p.re.test(text)).map((p) => p.name) : []);
}
