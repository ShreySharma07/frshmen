// Puts the Typst compiler where the site serves it (docs/decisions.md, 2026-11-17), in public/resume/typst/:
// - the WebAssembly, gzip-compressed: Cloudflare serves static files up to 25 MiB and it is 28 MB raw;
//   the browser unpacks it with DecompressionStream;
// - typst.ts's own self-contained bundle (no imports) and our worker (scripts/typst.worker.mjs): the
//   build copies worker files as they are, so they are served as plain modules;
// - manifest.json naming them. Every name carries a content hash, so each can be cached for good.
// Runs before `next build` and `next dev`; the output is ignored by git and rebuilt from node_modules.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { gzipSync } from "node:zlib";

const require = createRequire(import.meta.url);
const pkgDir = dirname(require.resolve("@myriaddreamin/typst-ts-web-compiler/package.json"));
const tsDir = dirname(require.resolve("@myriaddreamin/typst.ts/package.json"));
const { version } = JSON.parse(readFileSync(join(pkgDir, "package.json"), "utf8"));
const here = import.meta.dirname;
const out = join(here, "..", "public", "resume", "typst");
const fonts = join(here, "..", "public", "resume", "fonts");
const hash = (buf) => createHash("sha256").update(buf).digest("hex").slice(0, 12);

const wasm = readFileSync(join(pkgDir, "pkg", "typst_ts_web_compiler_bg.wasm"));
const bundle = readFileSync(join(tsDir, "dist", "esm", "main.bundle.js"));
const worker = readFileSync(join(here, "typst.worker.mjs"));
const names = {
  file: `compiler-${version}-${hash(wasm)}.wasm.gz`,
  bundle: `typst-${version}-${hash(bundle)}.mjs`,
  worker: `worker-${hash(worker)}.mjs`,
};
const manifestPath = join(out, "manifest.json");
let old = {};
try { old = JSON.parse(readFileSync(manifestPath, "utf8")); } catch {}
const fontBytes = readdirSync(fonts).filter((f) => f.endsWith(".ttf")).reduce((n, f) => n + statSync(join(fonts, f)).size, 0);

if (old.file === names.file && old.bundle === names.bundle && old.worker === names.worker) {
  console.log(`typst ${version} already in public/resume/typst`);
} else {
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });
  const gz = gzipSync(wasm, { level: 9 });
  writeFileSync(join(out, names.file), gz);
  writeFileSync(join(out, names.bundle), bundle);
  writeFileSync(join(out, names.worker), worker);
  writeFileSync(manifestPath, JSON.stringify({ version, ...names, bytes: gz.length, raw: wasm.length, fontBytes }, null, 2));
  console.log(`typst ${version}: compiler ${(wasm.length / 1e6).toFixed(1)} MB -> ${(gz.length / 1e6).toFixed(1)} MB gzip; ${names.bundle}; ${names.worker}`);
}
