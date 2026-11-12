// The frame around /login and the signed-in pages: the page's top bar, then one column of content.
import Link from "next/link";
import { PageBar } from "@/components/shell/PageBar";

export function AccountShell({ title = "Aventra", sub, actions, wide, children }: {
  title?: string; sub?: React.ReactNode; actions?: React.ReactNode; wide?: boolean; children: React.ReactNode;
}) {
  return (
    <>
      <PageBar title={title} sub={sub}>{actions}</PageBar>
      <main className={`page-in mx-auto w-full px-4 py-8 lg:px-6 lg:py-10 ${wide ? "" : "max-w-[560px]"}`}>{children}</main>
    </>
  );
}

/** Shown when the build has no Supabase settings yet (see src/lib/supabase.ts). */
export function NotSetUp() {
  return (
    <p className="text-body text-muted">
      Sign-in isn&apos;t switched on yet. <Link href="/" className="font-medium text-accent-text underline">See open jobs</Link>
    </p>
  );
}
