// Fails when src/design/tokens.ts and the CSS variables in src/app/globals.css disagree, so the
// web and the future mobile app can't drift apart. Run: npm run check:tokens
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");
const ts = readFileSync(new URL("../src/design/tokens.ts", import.meta.url), "utf8");

const kebab = (s) => s.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
const block = (src, start) => {
  const i = src.indexOf(start);
  if (i < 0) throw new Error(`missing block: ${start}`);
  return src.slice(i, src.indexOf("}", i));
};
const vars = (src) => Object.fromEntries([...src.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2].toLowerCase()]));
const tsTheme = (name) => {
  const body = block(ts, `${name}: {`);
  return Object.fromEntries([...body.matchAll(/(\w+):\s*"(#[0-9a-f]{6})"/gi)].map((m) => [kebab(m[1]), m[2].toLowerCase()]));
};

const themes = { light: vars(block(css, ":root {")), dark: vars(block(css, ':root[data-theme="dark"]')) };
const mediaDark = vars(block(css, ':root:not([data-theme="light"])'));
let problems = [];
for (const [k, v] of Object.entries(themes.dark)) if (mediaDark[k] !== v) problems.push(`dark: --${k} differs between the media query and [data-theme=dark]`);
for (const name of ["light", "dark"]) {
  const want = tsTheme(name);
  for (const [k, v] of Object.entries(want)) if (themes[name][k] !== v) problems.push(`${name}: --${k} is ${themes[name][k]} in CSS, ${v} in tokens.ts`);
  for (const k of Object.keys(themes[name])) if (!(k in want)) problems.push(`${name}: --${k} is missing from tokens.ts`);
}
for (const [n, px] of [["sm", 4], ["md", 8], ["lg", 12]]) if (!css.includes(`--radius-${n}: ${px}px`) || !ts.includes(`${n}: ${px}`)) problems.push(`radius ${n} differs`);

if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
console.log(`tokens in sync: ${Object.keys(themes.light).length} colours × 2 themes, 3 radii`);
