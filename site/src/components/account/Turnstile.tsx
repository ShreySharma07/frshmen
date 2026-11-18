"use client";
// Cloudflare Turnstile on the email sign-in link (docs/decisions.md, 2026-11-18, security review M1):
// a script asking for thousands of sign-in links, one per throwaway inbox, has to pass it first.
// Supabase checks the token itself (Authentication > Attack Protection > CAPTCHA), so our API doesn't
// change. Usually invisible: Cloudflare asks a person to click only when something looks off.
// On only when NEXT_PUBLIC_TURNSTILE_SITE_KEY is set (site/.env.example).
import { useEffect, useRef } from "react";

export const TURNSTILE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render(el: HTMLElement, opts: Record<string, unknown>): string;
  reset(id: string): void;
  remove(id: string): void;
}
declare global { interface Window { turnstile?: TurnstileApi } }

let loading: Promise<TurnstileApi> | null = null;
function load(): Promise<TurnstileApi> {
  loading ??= new Promise((resolve, reject) => {
    if (window.turnstile) return resolve(window.turnstile);
    const s = Object.assign(document.createElement("script"), { src: SCRIPT, async: true, defer: true });
    s.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile didn't load")));
    s.onerror = () => { loading = null; reject(new Error("Turnstile didn't load")); };
    document.head.append(s);
  });
  return loading;
}

/** The check. `onToken` gets a token (or null when it expires or fails); `resetKey` changing asks for a
 * fresh one, since each token works once. */
export function Turnstile({ onToken, resetKey, onError }: { onToken: (t: string | null) => void; resetKey: number; onError: (m: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const widget = useRef<string | null>(null);
  const handlers = useRef({ onToken, onError });
  // The latest callbacks, for Turnstile's (which are registered once).
  useEffect(() => { handlers.current = { onToken, onError }; }, [onToken, onError]);

  useEffect(() => {
    let gone = false;
    load().then((api) => {
      if (gone || !box.current) return;
      widget.current = api.render(box.current, {
        sitekey: TURNSTILE_KEY,
        theme: "auto",
        appearance: "interaction-only", // shown only when a person needs to click
        callback: (t: string) => handlers.current.onToken(t),
        "expired-callback": () => handlers.current.onToken(null),
        "error-callback": () => { handlers.current.onToken(null); handlers.current.onError("The security check didn't load. Refresh and try again."); },
      });
    }).catch((e: Error) => handlers.current.onError(e.message));
    return () => {
      gone = true;
      if (widget.current && window.turnstile) window.turnstile.remove(widget.current);
      widget.current = null;
    };
  }, []);

  useEffect(() => {
    if (resetKey && widget.current && window.turnstile) {
      handlers.current.onToken(null);
      window.turnstile.reset(widget.current);
    }
  }, [resetKey]);

  return <div ref={box} className="flex justify-center empty:hidden" />;
}
