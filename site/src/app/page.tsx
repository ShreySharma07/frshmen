// Placeholder home while the job list is ported (M4.6): proves the export and the logo work.
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 px-4">
      {/* eslint-disable-next-line @next/next/no-img-element -- a static SVG; next/image needs a loader in export mode */}
      <img src="/kario-wordmark.svg" alt="kario" className="h-9 w-auto self-start" />
      <p className="text-zinc-600">The new Kario site is being built. The job list arrives next.</p>
    </main>
  );
}
