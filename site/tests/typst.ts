// Compiles a template in Node with the same compiler the browser uses (for tests and screenshots).
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { createTypstCompiler } from "@myriaddreamin/typst.ts/compiler";
import { disableDefaultFontAssets, loadFonts } from "@myriaddreamin/typst.ts/options.init";
import type { ResumeDoc } from "../src/lib/resumeDoc.ts";
import { TEMPLATES } from "../src/lib/resumeTemplates.ts";

const require = createRequire(import.meta.url);
const FONTS = join(import.meta.dirname, "..", "public", "resume", "fonts");
let compiler: Promise<ReturnType<typeof createTypstCompiler>> | null = null;

function ready() {
  compiler ??= (async () => {
    const c = createTypstCompiler();
    const wasm = readFileSync(require.resolve("@myriaddreamin/typst-ts-web-compiler/wasm"));
    const fonts = [...new Set(TEMPLATES.flatMap((t) => t.fonts))].map((f) => new Uint8Array(readFileSync(join(FONTS, `${f}.ttf`))));
    await c.init({ getModule: () => wasm, beforeBuild: [disableDefaultFontAssets(), loadFonts(fonts)] });
    return c;
  })();
  return compiler;
}

export async function compile(template: string, doc: ResumeDoc): Promise<{ pdf?: Uint8Array; diagnostics: unknown }> {
  const c = await ready();
  const t = TEMPLATES.find((x) => x.id === template)!;
  c.addSource("/main.typ", t.source);
  c.mapShadow("/data.json", new TextEncoder().encode(JSON.stringify(doc)));
  const r = await c.compile({ mainFilePath: "/main.typ", format: 1, diagnostics: "unix" });
  return { pdf: r.result, diagnostics: r.diagnostics };
}
