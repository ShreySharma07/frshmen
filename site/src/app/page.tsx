// Static shell, printed at build time; JobList fills in live jobs in the browser.
import { JobList } from "@/components/JobList";

export default function Home() {
  return (
    <>
      <header className="sticky top-0 z-30 h-14 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1280px] items-center px-4 lg:px-6">
          {/* eslint-disable-next-line @next/next/no-img-element -- static SVG; next/image needs a loader in export mode */}
          <img src="/kario-wordmark.svg" alt="kario" className="h-[22px] w-auto dark:invert" />
        </div>
      </header>
      <main className="mx-auto max-w-[720px] px-2 py-4 lg:px-6">
        <JobList />
      </main>
    </>
  );
}
