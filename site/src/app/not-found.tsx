// Served as out/404.html for any unknown path (wrangler "404-page").
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 px-4">
      {/* eslint-disable-next-line @next/next/no-img-element -- static SVG; next/image needs a loader in export mode */}
      <img src="/kario-wordmark.svg" alt="kario" className="h-8 w-auto self-start dark:invert" />
      <h1 className="text-title font-medium">This page doesn&apos;t exist.</h1>
      <p className="text-body text-muted">The link may be old, or the job may have closed.</p>
      <Link href="/" className="self-start rounded-md bg-accent px-4 py-2.5 text-meta font-medium text-on-accent transition-colors duration-quick hover:bg-accent-hover">
        See open jobs
      </Link>
    </main>
  );
}
