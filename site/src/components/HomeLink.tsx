"use client";
// The app's logo: home is the landing page, even for a signed-in person (Shrey, 2026-11-15).
// Opening / from outside sends them on to /jobs (app/page.tsx); this note says they asked for it.
import type { ComponentProps } from "react";
import { HOME_KEY } from "@/lib/session";
import { IntentLink } from "./IntentLink";

export function HomeLink({ onClick, ...props }: Omit<ComponentProps<typeof IntentLink>, "href">) {
  return (
    <IntentLink href="/" aria-label="Aventra home" {...props}
      onClick={(e) => { try { sessionStorage.setItem(HOME_KEY, "1"); } catch {} onClick?.(e); }} />
  );
}
