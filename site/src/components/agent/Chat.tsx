"use client";
// The agent chat (concept A in docs/wireframes/agent/, decided 2026-11-14): one conversation, with
// what the agent found as cards inside its answers. A draft opens beside the chat like a document
// (a sheet on phones) to read, edit, copy or open in Gmail. Each chat is saved for the person after
// every answer (lib/chats.ts, docs/decisions.md 2026-11-15) and reopened from the list (Chats.tsx).
import { ArrowLeft, ArrowUp, Check, Copy, ExternalLink, FileText, Loader2, Send, X } from "lucide-react";
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { saveChat } from "@/lib/chats";
import { connectGmail, gmailConnected, gmailSendOn, preloadGmail, sendGmail } from "@/lib/gmail";
import { gmailUrl, sendMessage, type AgentCard, type AgentDraft, type AgentNote, type AgentStartup, type Turn } from "@/lib/agent";
import { CATEGORY } from "@/lib/describe";
import type { ResumeSource } from "./ResumePanel";
import { EASE, SidePanel } from "./SidePanel";

// What opens beside the chat: an email draft, a LinkedIn message to one of the person's connections,
// or the resume editor (docs/decisions.md, 2026-11-16).
type Doc = AgentDraft | AgentNote;
type Open = Doc | { type: "resume" };

// The editor, pdf.js and pdf-lib load only when someone opens their resume.
const ResumePanel = dynamic(() => import("./ResumePanel").then((m) => m.ResumePanel), { ssr: false });
const EDIT_RESUME = "Edit my resume";

const MOVE = 0.34;
const SUGGESTIONS = [EDIT_RESUME, "Which YC startups would suit me?", "Jobs I fit that were posted this week", "Who do I know at Razorpay?"];

export function Chat({ id, initialTurns, saved, name, initialRemaining, onBack, onSaved, resume, onResumeSaved }: {
  id: string; initialTurns: Turn[]; saved: boolean; name: string; initialRemaining: number | null;
  onBack: (() => void) | null; onSaved: () => void; resume: ResumeSource; onResumeSaved: (saved: Pick<ResumeSource, "text" | "fileName" | "doc">) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>(initialTurns);
  const isSaved = useRef(saved);
  const [unsaved, setUnsaved] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The allowance loads after the page does: show it until a reply brings a newer count.
  const [counted, setRemaining] = useState<number | null>(null);
  const remaining = counted ?? initialRemaining;
  const [open, setOpen] = useState<Open | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // The newest message is at the bottom of the page.
    if (turns.length || busy) scrollTo({ top: document.documentElement.scrollHeight, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
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
      const answered: Turn[] = [...next, { role: "model", text: r.reply, cards: r.cards, sources: r.sources }];
      setTurns(answered);
      setRemaining(r.remaining);
      // Saved after every answer; a failed save leaves the chat usable and says so.
      saveChat(id, answered, !isSaved.current)
        .then(() => { isSaved.current = true; setUnsaved(false); onSaved(); })
        .catch(() => setUnsaved(true));
      const made = r.cards.find((c): c is Doc => c.type === "draft" || c.type === "linkedin");
      if (made) setOpen(made);
      // Asked in words ("customise my resume"): the agent opened the editor, so it opens here too.
      else if (r.cards.some((c) => c.type === "resume_editor")) setOpen({ type: "resume" });
    } catch (err) {
      const e = err as Error & { status?: number };
      setError(e.status === 429 ? "You've used today's messages. They come back 24 hours after each was sent."
        : e.status === 404 ? "The agent isn't switched on yet."
        : /busy|quota/i.test(e.message) ? "Gemini is busy right now. Try again in a minute; this message wasn't counted."
        : `Couldn't answer: ${e.message}`);
      setTurns(turns); // the message wasn't answered (or counted): give it back to edit
      setDraft(message);
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  };

  const still = useReducedMotion();
  // A new chat starts with the box in the middle of the screen; the first message sends it down to
  // the bottom, where it stays (Shrey, 2026-11-15). The same element moves (layoutId), so the eye
  // follows it instead of one box vanishing and another appearing.
  const empty = turns.length === 0 && !busy;
  const composer = (
    <motion.form layoutId="agent-composer" transition={{ duration: still ? 0 : 0.42, ease: EASE }}
      onSubmit={(e) => { e.preventDefault(); send(draft); }}
      className="rounded-2xl border border-line bg-card shadow-raised transition-[border-color,box-shadow] duration-quick focus-within:border-ink/30 focus-within:shadow-menu">
      <label htmlFor="agent-input" className="sr-only">Message the agent</label>
      <textarea id="agent-input" ref={input} rows={1} maxLength={2000} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus={empty}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft); } }}
        placeholder={empty ? "Ask about jobs, companies or people…" : "Reply…"}
        className={`block w-full resize-none bg-transparent px-4 pt-3.5 text-base outline-none placeholder:text-muted [field-sizing:content] ${empty ? "min-h-[4.5rem] max-h-60" : "min-h-11 max-h-40"}`} />
      <div className="flex items-center justify-between gap-3 px-3 pb-3 pt-1">
        <span className="pl-1 text-caption text-muted max-sm:hidden">Enter to send · Shift + Enter for a new line</span>
        <button type="submit" disabled={busy || !draft.trim() || remaining === 0} aria-label="Send"
          className="ml-auto grid size-9 shrink-0 place-items-center rounded-full bg-ink text-canvas transition-[transform,opacity] duration-quick active:scale-[0.94] disabled:opacity-30">
          <ArrowUp aria-hidden className="size-[1.125rem]" />
        </button>
      </div>
    </motion.form>
  );
  const suggestions = (
    <div className="mt-4 flex flex-wrap justify-center gap-2">
      {SUGGESTIONS.map((s) => (
        // Opening the editor is free: no message is sent until they ask the agent to improve it.
        <button key={s} type="button" onClick={() => (s === EDIT_RESUME ? setOpen({ type: "resume" }) : send(s))}
          className="rounded-full border border-line bg-canvas px-3.5 py-1.5 text-meta transition-colors duration-quick hover:border-ink/40 hover:bg-card">{s}</button>
      ))}
    </div>
  );
  return (
    <LayoutGroup>
    <div className={`grid gap-6 ${open ? (open.type === "resume" ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]" : "lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]") : ""}`}>
      {/* The conversation scrolls with the page, like any page of the site, not inside a box of its
          own (Shrey, 2026-11-15: a scroll area here read as a window inside the browser). The box
          to write in stays pinned to the bottom of the screen, above the app's tab bar on phones
          (wide screens have no command bar on /agent). */}
      {/* When a draft opens, the conversation slides left to make room rather than jumping. */}
      <motion.section layout="position" transition={{ duration: still ? 0 : MOVE, ease: EASE }} aria-label="Conversation" className="mx-auto flex w-full max-w-[46rem] flex-col">
        <div className="mb-3 flex items-center justify-between gap-3">
          {onBack ? (
            <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-meta font-medium text-accent-text underline-offset-2 hover:underline">
              <ArrowLeft aria-hidden className="size-4" />All chats
            </button>
          ) : <span />}
          <p className="text-meta text-muted">
            {unsaved && <span className="mr-2 text-card-fail">Couldn&apos;t save this chat ·</span>}
            {remaining === null ? "" : `${remaining} of 20 messages left today`}
            {!empty && <> · <button type="button" onClick={() => setOpen({ type: "resume" })} className="font-medium text-accent-text underline-offset-2 hover:underline">Your resume</button></>}
          </p>
        </div>

        {empty ? (
          <div className="flex min-h-[calc(100svh-19rem)] flex-col justify-center pb-[6vh]">
            <h2 className="text-center font-display text-[clamp(1.875rem,4vw,2.75rem)] leading-tight">Hi {name.split(" ")[0]}. What should we look for?</h2>
            <p className="mx-auto mt-2 max-w-[34rem] text-center text-body text-muted">Jobs at your experience, people you know at a company, YC founders, and emails or LinkedIn messages you send yourself.</p>
            <div className="mt-7">{composer}</div>
            {error && <p role="alert" className="mt-3 text-center text-meta text-card-fail">{error}</p>}
            {suggestions}
          </div>
        ) : <>
        <ol aria-live="polite" className="flex flex-col gap-4">
          {turns.map((t, i) => t.role === "user"
            ? <li key={i} className="msg-sent max-w-[85%] self-end whitespace-pre-wrap rounded-lg bg-ink px-4 py-2.5 text-body text-canvas">{t.text}</li>
            : <li key={i} className="detail-in max-w-full self-start rounded-lg border border-card-line bg-card px-4 py-3 text-body">
                <p className="whitespace-pre-wrap">{t.text}</p>
                {/* Each card arrives just after the text, one after another: the order the agent found them. */}
                {t.cards?.map((c, j) => <div key={j} className="card-in" style={{ animationDelay: `${120 + j * 80}ms` }}><Card card={c} onOpen={setOpen} /></div>)}
                {!!t.sources?.length && <p className="mt-3 border-t border-line pt-2 text-caption text-muted">From: {t.sources.join(" · ")}</p>}
              </li>)}
          {busy && (
            <li aria-busy="true" className="detail-in flex items-center gap-2.5 self-start rounded-lg border border-card-line bg-card px-4 py-3 text-body text-muted">
              <span aria-hidden className="flex gap-1">
                {[0, 1, 2].map((d) => <span key={d} className="typing-dot size-1.5 rounded-full bg-muted" />)}
              </span>
              Looking through jobs and people…
            </li>
          )}
        </ol>

        {error && <p role="alert" className="mt-3 text-meta text-card-fail">{error}</p>}
        {/* The canvas fades in above the box so messages slide under it, not behind a hard edge. */}
        <div className="sticky bottom-[calc(4rem+env(safe-area-inset-bottom))] z-10 -mb-8 bg-gradient-to-t from-canvas from-75% pb-4 pt-6 lg:bottom-0 lg:-mb-10 lg:pb-6">
        {composer}
        </div>
        </>}
      </motion.section>

      <AnimatePresence mode="wait">
        {open?.type === "resume" ? <ResumePanel key="resume" source={resume} onClose={() => setOpen(null)} onSaved={onResumeSaved} onRemaining={setRemaining} />
          : open && <DraftPanel key={open.type === "draft" ? `${open.contact.id}:${open.subject}` : `li:${open.person.id}:${open.body.slice(0, 40)}`} doc={open} onClose={() => setOpen(null)} />}
      </AnimatePresence>
    </div>
    </LayoutGroup>
  );
}

function Card({ card, onOpen }: { card: AgentCard; onOpen: (d: Open) => void }) {
  const box = "mt-3 rounded-md border border-line bg-canvas px-3 py-2";
  if (card.type === "resume_editor") return (
    <button type="button" onClick={() => onOpen({ type: "resume" })}
      className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-ink px-3 py-1.5 text-meta font-medium transition-transform duration-quick active:scale-[0.98]">
      <FileText aria-hidden className="size-4" />Open your resume
    </button>
  );
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
  if (card.type === "connections") return (
    <ul className={`${box} grid gap-1.5`}>
      {card.people.map((p) => (
        <li key={p.id} className="text-meta">
          <span className="font-medium">{p.name}</span>
          <span className="text-muted"> · {[p.position, p.company].filter(Boolean).join(", ")} · you&apos;re connected</span>
          {p.linkedin && <a href={p.linkedin} target="_blank" rel="noopener" className="ml-1 inline-flex items-center gap-0.5 text-accent-text hover:underline">LinkedIn<ExternalLink aria-hidden className="size-3" /></a>}
        </li>
      ))}
    </ul>
  );
  if (card.type === "linkedin") return (
    <div className={box}>
      <p className="text-meta text-muted">LinkedIn message to {card.person.name}{card.person.company ? `, ${card.person.company}` : ""}</p>
      <p className="mt-1 line-clamp-2 text-meta text-muted">{card.body}</p>
      <button type="button" onClick={() => onOpen(card)}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-ink px-3 py-1.5 text-meta font-medium transition-transform duration-quick active:scale-[0.98]">
        <FileText aria-hidden className="size-4" />Open message
      </button>
    </div>
  );
  if (card.type === "startups") {
    // Startups whose work is known come first; the rest are listed, never guessed (decisions.md, 2026-11-16).
    const known = card.startups.filter((s) => s.described !== false);
    const unknown = card.startups.filter((s) => s.described === false);
    return (
      <div className={`${box} grid gap-3`}>
        {known.length > 0 && <ul className="grid gap-2">{known.map((s) => <StartupRow key={s.company} s={s} />)}</ul>}
        {unknown.length > 0 && (
          <div>
            <p className="text-meta text-muted">Couldn&rsquo;t tell what these build</p>
            <ul className="mt-1 grid gap-1">{unknown.map((s) => <StartupRow key={s.company} s={s} />)}</ul>
          </div>
        )}
        {card.has_more && <p className="text-meta text-muted">More fit. Ask &ldquo;show more&rdquo; to see the next ones.</p>}
      </div>
    );
  }
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
function DraftPanel({ doc, onClose }: { doc: Doc; onClose: () => void }) {
  const draft = doc.type === "draft" ? doc : null;
  const person = doc.type === "draft" ? doc.contact : doc.person;
  const role = doc.type === "draft" ? doc.contact.title : doc.person.position;
  const [subject, setSubject] = useState(draft?.subject ?? "");
  const [body, setBody] = useState(doc.body);
  const [copied, setCopied] = useState(false);
  const [sending, setSending] = useState<{ kind: "idle" | "asking" | "sending" | "sent" } | { kind: "error"; message: string }>({ kind: "idle" });
  const canSend = gmailSendOn && Boolean(draft?.to);
  useEffect(() => { if (canSend) preloadGmail().catch(() => {}); }, [canSend]);
  // The person presses Send themselves, after reading; the first time, Google asks them to allow it.
  const send = async () => {
    if (!draft?.to) return;
    try {
      if (!gmailConnected()) {
        setSending({ kind: "asking" });
        await connectGmail(); // opens Google's window: must start inside this click
      }
      setSending({ kind: "sending" });
      await sendGmail(draft.to, subject, body);
      setSending({ kind: "sent" });
    } catch (e) {
      setSending({ kind: "error", message: (e as Error).message });
    }
  };
  const sent = sending.kind === "sent";
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft ? `${draft.to ? `To: ${draft.to}\n` : ""}Subject: ${subject}\n\n${body}` : body);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      return true;
    } catch { return false; }
  };
  // LinkedIn has no way to fill a message in from a link: copy it, then open their profile to paste.
  const copyAndOpen = async () => {
    // Copy first: the clipboard needs this page to have focus, which the new tab would take.
    await copy();
    window.open(person.linkedin ?? "", "_blank", "noopener");
  };
  const field = "mt-1 w-full rounded-md border border-line bg-canvas px-3 py-2 text-body outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent/40";

  return (
    <SidePanel labelledBy="draft-title" onClose={onClose}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="draft-title" ref={heading} tabIndex={-1} className="font-display text-[1.375rem] leading-tight outline-none">{draft ? "Draft to" : "Message to"} {person.name}</h2>
          <p className="text-meta text-muted">{[role, person.company].filter(Boolean).join(", ")}{draft ? "" : " · on LinkedIn"}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close draft" className="grid size-9 shrink-0 place-items-center rounded-md hover:bg-surface">
          <X aria-hidden className="size-5" />
        </button>
      </div>
      <div className="mt-4 grid min-h-0 flex-1 content-start gap-3 overflow-y-auto [scrollbar-width:thin]">
        {draft && <>
          <p className="text-meta"><span className="font-medium">To </span>
            {draft.to ?? <span className="text-muted">{draft.address_removed ? "not kept in saved chats; ask the agent to draft it again to see the address"
              : draft.held_back ? "they've had enough emails from Aventra today; copy the text and reach them on LinkedIn"
              : draft.reveals_left === 0 ? "today's 5 email addresses are used; copy the text and find them on LinkedIn" : "no email on file for them"}</span>}
          </p>
          <label className="text-meta font-medium">Subject<input value={subject} maxLength={200} readOnly={sent} onChange={(e) => setSubject(e.target.value)} className={field} /></label>
        </>}
        <label className="text-meta font-medium">{draft ? "Email" : "Message"}
          <textarea value={body} maxLength={4000} readOnly={sent} onChange={(e) => setBody(e.target.value)} rows={6} className={`${field} resize-none leading-relaxed [field-sizing:content]`} />
        </label>
        <p className="text-caption text-muted">{draft ? `Read it, make it yours, then ${canSend ? "send it" : "send it from your own Gmail"}.` : "Read it, make it yours, then paste it into a message on LinkedIn."}{" "}
          {canSend ? "It goes from your Gmail only when you press Send." : "Aventra never sends anything for you."}</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {!draft && person.linkedin && (
          <button type="button" onClick={copyAndOpen}
            className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-body font-medium text-canvas transition-transform duration-quick active:scale-[0.98]">
            {copied ? "Copied, opening LinkedIn" : "Copy and open LinkedIn"}<ExternalLink aria-hidden className="size-4" />
          </button>
        )}
        {canSend && (
          <button type="button" onClick={send} disabled={sent || sending.kind === "asking" || sending.kind === "sending" || !subject.trim() || !body.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-body font-medium text-canvas transition-transform duration-quick active:scale-[0.98] disabled:opacity-60">
            {sending.kind === "asking" || sending.kind === "sending" ? <Loader2 aria-hidden className="size-4 animate-spin" />
              : sent ? <Check aria-hidden className="size-4" /> : <Send aria-hidden className="size-4" />}
            {sending.kind === "asking" ? "Waiting for Google…" : sending.kind === "sending" ? "Sending…" : sent ? "Sent from your Gmail" : "Send from Gmail"}
          </button>
        )}
        {draft?.to && !sent && (
          <a href={gmailUrl(draft.to, subject, body)} target="_blank" rel="noopener"
            className={canSend ? "inline-flex items-center gap-1.5 rounded-md border border-ink px-4 py-2 text-body font-medium"
              : "inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-body font-medium text-canvas transition-transform duration-quick active:scale-[0.98]"}>
            Open in Gmail<ExternalLink aria-hidden className="size-4" />
          </a>
        )}
        <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 rounded-md border border-ink px-4 py-2 text-body font-medium">
          <Copy aria-hidden className="size-4" />{copied ? "Copied" : "Copy"}
        </button>
        {draft && person.linkedin && (
          <a href={person.linkedin} target="_blank" rel="noopener" className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-body text-accent-text hover:underline">
            LinkedIn<ExternalLink aria-hidden className="size-4" />
          </a>
        )}
      </div>
      <p aria-live="polite" className="mt-2 text-meta empty:hidden">{sending.kind === "error" && <span role="alert" className="text-card-fail">Couldn&apos;t send: {sending.message}</span>}{sent && <span className="text-muted">Sent to {draft?.to}. It&apos;s in your Gmail&apos;s Sent folder.</span>}</p>
    </SidePanel>
  );
}

function StartupRow({ s }: { s: AgentStartup }) {
  const fits = [...(s.matched_kinds ?? []).map((k) => CATEGORY[k] ?? k), ...(s.matched_skills ?? [])];
  return (
    <li className="text-meta">
      <span className="font-medium">{s.company}</span>{s.yc_batch && <span className="text-muted"> ({s.yc_batch})</span>}
      <span className="text-muted"> · founder {s.founder}</span>
      {s.open_jobs > 0 && <span className="ml-1.5 rounded-sm border border-line px-1.5 py-px text-muted">{s.open_jobs} open {s.open_jobs === 1 ? "role" : "roles"}</span>}
      {s.builds && <span className="block">{s.builds}</span>}
      {fits.length > 0 && <span className="block text-muted">Fits: {fits.join(" · ")}</span>}
      {!s.builds && (s.sample_titles?.length ?? 0) > 0 && <span className="block text-muted">{s.sample_titles!.join(" · ")}</span>}
    </li>
  );
}
