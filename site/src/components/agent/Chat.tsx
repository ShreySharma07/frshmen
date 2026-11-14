"use client";
// The agent chat (concept A in docs/wireframes/agent/, decided 2026-11-14): one conversation, with
// what the agent found as cards inside its answers. A draft opens beside the chat like a document
// (a sheet on phones) to read, edit, copy or open in Gmail. The conversation is kept in this tab
// only (sessionStorage); the server stores nothing but a count of messages.
import { ArrowUp, Copy, ExternalLink, FileText, X } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { gmailUrl, sendMessage, type AgentCard, type AgentDraft, type Turn } from "@/lib/agent";

const STORE = "aventra:agent-chat";
const SUGGESTIONS = ["Which YC startups would suit me?", "Jobs I fit that were posted this week", "Who could I ask for a referral at Razorpay?"];

export function Chat({ name, initialRemaining }: { name: string; initialRemaining: number | null }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<number | null>(initialRemaining);
  const [open, setOpen] = useState<AgentDraft | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORE);
      // Restored once from this tab's storage, which only exists in the browser.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (saved) setTurns(JSON.parse(saved));
    } catch {}
  }, []);
  useEffect(() => {
    try { sessionStorage.setItem(STORE, JSON.stringify(turns.slice(-40))); } catch {}
    const el = list.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [turns, busy]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    const next: Turn[] = [...turns, { role: "user", text: message }];
    setTurns(next);
    setDraft("");
    setBusy(true);
    setError(null);
    try {
      const r = await sendMessage(next);
      setTurns([...next, { role: "model", text: r.reply, cards: r.cards, sources: r.sources }]);
      setRemaining(r.remaining);
      const made = r.cards.find((c): c is AgentDraft => c.type === "draft");
      if (made) setOpen(made);
    } catch (err) {
      const e = err as Error & { status?: number };
      setError(e.status === 429 ? "You've used today's messages. They come back 24 hours after each was sent."
        : e.status === 404 ? "The agent isn't switched on yet." : `Couldn't answer: ${e.message}`);
      setTurns(turns); // the message wasn't answered (or counted): give it back to edit
      setDraft(message);
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  };

  return (
    <div className={`grid gap-6 ${open ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]" : ""}`}>
      {/* The conversation scrolls inside its own area and the box to write in stays under it. The
          height leaves room for the page's header and tabs above, and the app's tab bar below on
          phones (wide screens have no command bar on /agent). */}
      <section aria-label="Conversation" className="mx-auto flex h-[calc(100svh-15rem)] min-h-[24rem] w-full max-w-[46rem] flex-col lg:h-[calc(100svh-12rem)]">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-meta text-muted">{remaining === null ? "" : `${remaining} of 20 messages left today`}</p>
          {turns.length > 0 && (
            <button type="button" onClick={() => { setTurns([]); setOpen(null); }} className="text-meta font-medium text-accent-text underline-offset-2 hover:underline">New chat</button>
          )}
        </div>

        <ol ref={list} aria-live="polite" className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain pr-1">
          {turns.length === 0 && (
            <li className="rounded-lg border border-card-line bg-card p-5">
              <p className="font-display text-headline leading-tight">Hi {name.split(" ")[0]}. Ask me about jobs, companies or people.</p>
              <p className="mt-2 text-body text-muted">I search the open jobs at your experience, find HR and founders at a company, suggest YC startups, and draft emails you send yourself.</p>
            </li>
          )}
          {turns.map((t, i) => t.role === "user"
            ? <li key={i} className="max-w-[85%] self-end whitespace-pre-wrap rounded-lg bg-ink px-4 py-2.5 text-body text-canvas">{t.text}</li>
            : <li key={i} className="detail-in max-w-full self-start rounded-lg border border-card-line bg-card px-4 py-3 text-body">
                <p className="whitespace-pre-wrap">{t.text}</p>
                {t.cards?.map((c, j) => <Card key={j} card={c} onOpen={setOpen} />)}
                {!!t.sources?.length && <p className="mt-3 border-t border-line pt-2 text-caption text-muted">From: {t.sources.join(" · ")}</p>}
              </li>)}
          {busy && <li aria-busy="true" className="self-start rounded-lg border border-card-line bg-card px-4 py-3 text-body text-muted">Looking…</li>}
        </ol>

        {error && <p role="alert" className="mt-3 text-meta text-card-fail">{error}</p>}
        {turns.length === 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-line px-3 py-1 text-meta transition-colors duration-quick hover:border-ink">{s}</button>
            ))}
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); send(draft); }}
          className="mt-4 flex shrink-0 items-end gap-2 rounded-lg border border-ink bg-canvas p-2">
          <label htmlFor="agent-input" className="sr-only">Message the agent</label>
          <textarea id="agent-input" ref={input} rows={1} maxLength={2000} value={draft} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft); } }}
            placeholder="Ask about jobs, companies or people…" className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-body outline-none [field-sizing:content]" />
          <button type="submit" disabled={busy || !draft.trim() || remaining === 0} aria-label="Send"
            className="grid size-10 shrink-0 place-items-center rounded-md bg-ink text-canvas transition-transform duration-quick active:scale-[0.96] disabled:opacity-40">
            <ArrowUp aria-hidden className="size-5" />
          </button>
        </form>
      </section>

      {open && <DraftPanel key={`${open.contact.id}:${open.subject}`} draft={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function Card({ card, onOpen }: { card: AgentCard; onOpen: (d: AgentDraft) => void }) {
  const box = "mt-3 rounded-md border border-line bg-canvas px-3 py-2";
  if (card.type === "jobs") return (
    <ul className={`${box} grid gap-1.5`}>
      {card.jobs.map((j) => (
        <li key={j.id} className="text-meta">
          <a href={j.url} target="_blank" rel="noopener" className="font-medium hover:underline">{j.title}</a>
          <span className="text-muted"> · {j.company}{j.location ? ` · ${j.location}` : ""} · {j.asks_years ? `asks ${j.asks_years} yrs` : "years not stated"}</span>
        </li>
      ))}
    </ul>
  );
  if (card.type === "people") return (
    <ul className={`${box} grid gap-1.5`}>
      {card.people.map((p) => (
        <li key={p.id} className="text-meta">
          <span className="font-medium">{p.name}</span>
          <span className="text-muted"> · {p.title ?? (p.kind === "founder" ? "Founder" : "HR")} · {p.company}{p.has_email ? "" : " · no email on file"}</span>
          {p.linkedin && <a href={p.linkedin} target="_blank" rel="noopener" className="ml-1 inline-flex items-center gap-0.5 text-accent-text hover:underline">LinkedIn<ExternalLink aria-hidden className="size-3" /></a>}
        </li>
      ))}
    </ul>
  );
  if (card.type === "startups") return (
    <ul className={`${box} grid gap-2`}>
      {card.startups.map((s) => (
        <li key={s.company} className="text-meta">
          <span className="font-medium">{s.company}</span>{s.yc_batch && <span className="text-muted"> ({s.yc_batch})</span>}
          <span className="text-muted"> · founder {s.founder} · {s.open_jobs} open {s.open_jobs === 1 ? "job" : "jobs"} at your experience</span>
          {s.sample_titles?.length > 0 && <span className="block text-muted">{s.sample_titles.join(" · ")}</span>}
        </li>
      ))}
    </ul>
  );
  return (
    <div className={box}>
      <p className="text-meta text-muted">Draft to {card.contact.name}, {card.contact.company}</p>
      <p className="mt-0.5 font-medium">{card.subject}</p>
      <p className="mt-1 line-clamp-2 text-meta text-muted">{card.body}</p>
      <button type="button" onClick={() => onOpen(card)}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-ink px-3 py-1.5 text-meta font-medium transition-transform duration-quick active:scale-[0.98]">
        <FileText aria-hidden className="size-4" />Open draft
      </button>
    </div>
  );
}

// Wide screens show the draft beside the chat; phones cover the page with it. On phones it is
// rendered into <body>: inside the page's animated column a fixed sheet can't rise above the app's
// header and tab bar.
const WIDE = "(min-width: 64rem)";
const subscribeWide = (cb: () => void) => { const m = matchMedia(WIDE); m.addEventListener("change", cb); return () => m.removeEventListener("change", cb); };
const useWide = () => useSyncExternalStore(subscribeWide, () => matchMedia(WIDE).matches, () => true);

function DraftPanel({ draft, onClose }: { draft: AgentDraft; onClose: () => void }) {
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [copied, setCopied] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${draft.to ? `To: ${draft.to}\n` : ""}Subject: ${subject}\n\n${body}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };
  const wide = useWide();
  const field = "mt-1 w-full rounded-md border border-line bg-canvas px-3 py-2 text-body outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent/40";

  const panel = (
    // Beside the chat on wide screens, like a document opened next to a conversation; a sheet on phones.
    // The wide panel stops above the app's command bar (about 6rem at the bottom of the column).
    <aside aria-labelledby="draft-title"
      className={wide ? "panel-in sticky top-4 flex max-h-[calc(100svh-6rem)] flex-col self-start rounded-lg border border-card-line bg-card p-5"
        : "sheet-in fixed inset-0 z-50 flex flex-col bg-card p-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-[max(1.25rem,env(safe-area-inset-bottom))]"}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="draft-title" ref={heading} tabIndex={-1} className="font-display text-[1.375rem] leading-tight outline-none">Draft to {draft.contact.name}</h2>
          <p className="text-meta text-muted">{[draft.contact.title, draft.contact.company].filter(Boolean).join(", ")}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close draft" className="grid size-9 shrink-0 place-items-center rounded-md hover:bg-surface">
          <X aria-hidden className="size-5" />
        </button>
      </div>
      <div className="mt-4 grid min-h-0 flex-1 content-start gap-3 overflow-y-auto">
        <p className="text-meta"><span className="font-medium">To </span>
          {draft.to ?? <span className="text-muted">{draft.reveals_left === 0 ? "today's 5 email addresses are used; copy the text and find them on LinkedIn" : "no email on file for them"}</span>}
        </p>
        <label className="text-meta font-medium">Subject<input value={subject} maxLength={200} onChange={(e) => setSubject(e.target.value)} className={field} /></label>
        <label className="text-meta font-medium">Email
          <textarea value={body} maxLength={4000} onChange={(e) => setBody(e.target.value)} rows={wide ? 11 : 14} className={`${field} resize-y leading-relaxed`} />
        </label>
        <p className="text-caption text-muted">Read it, make it yours, then send it from your own Gmail. Aventra never sends anything for you.</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {draft.to && (
          <a href={gmailUrl(draft.to, subject, body)} target="_blank" rel="noopener"
            className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-body font-medium text-canvas transition-transform duration-quick active:scale-[0.98]">
            Open in Gmail<ExternalLink aria-hidden className="size-4" />
          </a>
        )}
        <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 rounded-md border border-ink px-4 py-2 text-body font-medium">
          <Copy aria-hidden className="size-4" />{copied ? "Copied" : "Copy"}
        </button>
        {draft.contact.linkedin && (
          <a href={draft.contact.linkedin} target="_blank" rel="noopener" className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-body text-accent-text hover:underline">
            LinkedIn<ExternalLink aria-hidden className="size-4" />
          </a>
        )}
      </div>
    </aside>
  );
  return wide ? panel : createPortal(panel, document.body);
}
