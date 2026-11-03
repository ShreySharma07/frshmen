// The frame around /login and /profile: the job screen's header, one narrow column below.
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Wordmark } from "@/components/Wordmark";

export function AccountShell({ actions, children }: { actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-30 h-14 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1280px] items-center gap-4 px-4 lg:px-6">
          <Link href="/" aria-label="Kario, open jobs"><Wordmark className="h-[22px] w-auto shrink-0 text-ink" /></Link>
          <div className="ml-auto flex items-center gap-2">
            {actions}
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[560px] px-4 py-10 lg:py-16">{children}</main>
    </>
  );
}

/** Shown when the build has no Supabase settings yet (see src/lib/supabase.ts). */
export function NotSetUp() {
  return (
    <p className="text-body text-muted">
      Sign-in isn&apos;t switched on yet. <Link href="/" className="font-medium text-accent underline">See open jobs</Link>
    </p>
  );
}
