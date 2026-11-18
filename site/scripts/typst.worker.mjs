// Compiles resume templates to PDF off the main thread (docs/decisions.md, 2026-11-17), so the page
// stays responsive on budget phones while the compiler starts. Plain JavaScript on purpose: the build
// (Turbopack) copies worker files as they are, so scripts/typst-assets.mjs serves this file next to
// typst.ts's own self-contained bundle, both named by content hash in /resume/typst/manifest.json.
// The compiler (11 MB gzip) and the template fonts are fetched once, with progress, then cached.
//
// In:  { id, source, data, fonts: [font file names] }
// Out: { id, kind: "progress", loaded, total } | { id, kind: "done", pdf } | { id, kind: "error", message }

let ready = null;

async function download(url, onChunk) {
  const res = await fetch(url);
  if (!res.ok || !res.body) throw new Error(`couldn't load ${url.split("/").pop()} (HTTP ${res.status})`);
  const parts = [];
  const reader = res.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    onChunk(value.length);
  }
  return new Uint8Array(await new Blob(parts).arrayBuffer());
}

async function gunzip(bytes) {
  // A host may already have unpacked it (sent with Content-Encoding: gzip): only gzip starts 1f 8b.
  if (bytes[0] !== 0x1f || bytes[1] !== 0x8b) return bytes;
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

function start(id, fonts) {
  ready ??= (async () => {
    const manifest = await (await fetch("/resume/typst/manifest.json")).json();
    const { createTypstCompiler, loadFonts } = await import(`/resume/typst/${manifest.bundle}`);
    const total = manifest.bytes + manifest.fontBytes;
    let loaded = 0;
    const tick = (n) => { loaded += n; self.postMessage({ id, kind: "progress", loaded: Math.min(loaded, total), total }); };
    const [wasm, ...fontData] = await Promise.all([
      download(`/resume/typst/${manifest.file}`, tick).then(gunzip),
      ...fonts.map((f) => download(`/resume/fonts/${f}.ttf`, tick)),
    ]);
    const compiler = createTypstCompiler();
    // assets: false: only our own fonts, never typst.ts's default download from a public CDN.
    await compiler.init({ getModule: () => wasm, beforeBuild: [loadFonts(fontData, { assets: false })] });
    self.postMessage({ id, kind: "progress", loaded: total, total });
    return compiler;
  })();
  ready.catch(() => { ready = null; }); // a failed start (offline, say) may be tried again later
  return ready;
}

self.onmessage = async (e) => {
  const { id, source, data, fonts } = e.data;
  try {
    const compiler = await start(id, fonts);
    compiler.addSource("/main.typ", source);
    compiler.mapShadow("/data.json", new TextEncoder().encode(data));
    const r = await compiler.compile({ mainFilePath: "/main.typ", format: 1, diagnostics: "unix" });
    if (!r.result) throw new Error(`the template couldn't be laid out: ${JSON.stringify(r.diagnostics ?? []).slice(0, 300)}`);
    self.postMessage({ id, kind: "done", pdf: r.result }, [r.result.buffer]);
  } catch (err) {
    self.postMessage({ id, kind: "error", message: err?.message || String(err) });
  }
};
