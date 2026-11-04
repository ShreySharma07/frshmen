"use client";
// A Link that prefetches only when someone shows intent (hover, focus or touch), not when it
// scrolls into view. The job list's "Sign in" and profile links would otherwise pull the
// /login and /profile chunks, supabase-js included (~75 KB gzip), on every visit to `/`.
// Pattern from the Next.js prefetching guide ("Hover-triggered prefetch").
import Link from "next/link";
import { useState, type ComponentProps } from "react";

export function IntentLink({ onMouseEnter, onFocus, onTouchStart, ...props }: ComponentProps<typeof Link>) {
  const [active, setActive] = useState(false);
  return (
    <Link
      {...props}
      prefetch={active ? null : false}
      onMouseEnter={(e) => { setActive(true); onMouseEnter?.(e); }}
      onFocus={(e) => { setActive(true); onFocus?.(e); }}
      onTouchStart={(e) => { setActive(true); onTouchStart?.(e); }}
    />
  );
}
