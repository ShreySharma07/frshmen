"use client";

// A link from the landing page to the job list that crosses over with the View Transitions API
// (critique 2026-10-23, the micro layer): the landing settles back and the list rises into place,
// so the move reads as going deeper into the same product rather than to another site. Plain
// navigation with reduced motion, modifier clicks, or browsers without the API.
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ComponentProps, MouseEvent } from "react";

type Doc = Document & { startViewTransition?: (update: () => Promise<void>) => unknown };

export function JobsLink({ href, onClick, ...rest }: ComponentProps<typeof Link> & { href: string }) {
  const router = useRouter();
  const go = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    const doc = document as Doc;
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (!doc.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    e.preventDefault();
    const from = location.href;
    // The snapshot of the new page is taken when this resolves: once the router has moved (it
    // updates the address after the new page commits), plus a frame for it to paint.
    doc.startViewTransition(() => new Promise<void>((done) => {
      const started = performance.now();
      const wait = () => {
        if (location.href !== from || performance.now() - started > 1500) requestAnimationFrame(() => done());
        else requestAnimationFrame(wait);
      };
      router.push(href);
      wait();
    }));
  };
  return <Link href={href} onClick={go} {...rest} />;
}
