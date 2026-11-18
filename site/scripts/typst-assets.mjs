// Puts the Typst compiler where the site serves it (docs/decisions.md, 2026-11-17): gzip-compressed,
// because Cloudflare serves static files up to 25 MiB and the raw WebAssembly is 28 MB. The browser
// unpacks it with DecompressionStream (lib/typst.worker.ts). Runs before `next build` and `next dev`;
// the output is ignored by git and rebuilt from node_modules, so the version follows package.json.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { gzipSync } from "node:zlib";

const require = createRequire(import.meta.url);
const pkgDir = dirname(require.resolve("@myriaddreamin/typst-ts-web-compiler/package.json"));
const { version } = JSON.parse(readFileSync(join(pkgDir, "package.json"), "utf8"));
const out = join(import.meta.dirname, "..", "public", "resume", "typst");
const manifest = join(out, "manifest.json");

if (existsSync(manifest) && JSON.parse(readFileSync(manifest, "utf8")).version === version) {
  console.log(`typst compiler ${version} already in public/resume/typst`);
} else {
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });
  const wasm = readFileSync(join(pkgDir, "pkg", "typst_ts_web_compiler_bg.wasm"));
  const gz = gzipSync(wasm, { level: 9 });
  // The file name carries a content hash, so it can be cached forever and a new version is a new URL.
  const name = `compiler-${version}-${createHash("sha256").update(wasm).digest("hex").slice(0, 12)}.wasm.gz`;
  writeFileSync(join(out, name), gz);
  writeFileSync(manifest, JSON.stringify({ version, file: name, bytes: gz.length, raw: wasm.length }, null, 2));
  console.log(`typst compiler ${version}: ${(wasm.length / 1e6).toFixed(1)} MB -> ${(gz.length / 1e6).toFixed(1)} MB gzip (${name})`);
}
