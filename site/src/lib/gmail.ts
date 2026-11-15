// Sending a draft from the person's own Gmail (docs/decisions.md, 2026-11-15, Gmail option (a)).
// Google's sign-in asks for `gmail.send` only (a "sensitive" scope: Google verifies the app once,
// no paid assessment; never `gmail.compose`, which is "restricted"). The access token lives in
// this page's memory for about an hour and is never sent to Aventra's servers: the browser calls
// Gmail itself. Off unless NEXT_PUBLIC_GOOGLE_CLIENT_ID is set.
const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";
const SCOPE = "https://www.googleapis.com/auth/gmail.send";
const GIS = "https://accounts.google.com/gsi/client";

export const gmailSendOn = Boolean(CLIENT_ID);

interface TokenResponse { access_token?: string; expires_in?: number; scope?: string; error?: string; error_description?: string }
interface TokenClient { requestAccessToken(o?: { prompt?: string }): void }
declare global {
  interface Window {
    google?: { accounts: { oauth2: { initTokenClient(c: {
      client_id: string; scope: string; login_hint?: string; callback: (r: TokenResponse) => void;
      error_callback?: (e: { type: string; message?: string }) => void;
    }): TokenClient } } };
  }
}

let token: { value: string; expires: number } | null = null;
let loading: Promise<void> | null = null;

/** Google's sign-in library, loaded only on pages that can send (call it when the draft opens). */
export function preloadGmail(): Promise<void> {
  if (!gmailSendOn) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = GIS;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => { loading = null; reject(new Error("couldn't reach Google")); };
    document.head.appendChild(s);
  });
  return loading;
}

export const gmailConnected = () => token !== null && token.expires > Date.now();

/** Asks Google for permission to send. Call it straight from a click: it opens a popup. */
export function connectGmail(loginHint?: string): Promise<void> {
  const oauth = window.google?.accounts.oauth2;
  if (!oauth) return Promise.reject(new Error("Google's sign-in hasn't loaded yet; try again in a moment"));
  return new Promise((resolve, reject) => {
    oauth.initTokenClient({
      client_id: CLIENT_ID, scope: SCOPE, login_hint: loginHint,
      callback: (r) => {
        if (!r.access_token || r.error) return reject(new Error(r.error_description ?? r.error ?? "Google said no"));
        if (!(r.scope ?? "").split(" ").includes(SCOPE)) return reject(new Error("permission to send wasn't given"));
        // A minute early, so a send never starts with a token about to lapse.
        token = { value: r.access_token, expires: Date.now() + ((r.expires_in ?? 3600) - 60) * 1000 };
        resolve();
      },
      error_callback: (e) => reject(new Error(e.type === "popup_closed" ? "the Google window was closed" : e.message ?? e.type)),
    }).requestAccessToken({ prompt: "" });
  });
}

const b64 = (bytes: Uint8Array) => btoa(Array.from(bytes, (b) => String.fromCharCode(b)).join(""));
const utf8 = (s: string) => new TextEncoder().encode(s);

/** One plain-text email as RFC 2822, base64url as Gmail wants it. Exported for tests. */
export function mime(to: string, subject: string, body: string): string {
  if (/[\r\n]/.test(to) || /[\r\n]/.test(subject)) throw new Error("a line break in the address or subject");
  const lines = [
    `To: ${to}`,
    // Non-ASCII subjects (names, ₹) go as RFC 2047 encoded words.
    `Subject: ${/^[\x20-\x7e]*$/.test(subject) ? subject : `=?UTF-8?B?${b64(utf8(subject))}?=`}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    b64(utf8(body.replace(/\r?\n/g, "\r\n"))).replace(/.{76}/g, "$&\r\n"),
  ];
  return b64(utf8(lines.join("\r\n"))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Sends from the person's Gmail. Needs connectGmail first (gmailConnected()). */
export async function sendGmail(to: string, subject: string, body: string): Promise<void> {
  if (!gmailConnected()) throw new Error("connect Gmail first");
  const res = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", {
    method: "POST",
    headers: { Authorization: `Bearer ${token!.value}`, "Content-Type": "application/json" },
    body: JSON.stringify({ raw: mime(to, subject, body) }),
  });
  if (res.status === 401) token = null; // revoked or lapsed: the next send asks again
  if (!res.ok) {
    const e = await res.json().catch(() => null);
    throw new Error(e?.error?.message ?? `Gmail answered ${res.status}`);
  }
}
