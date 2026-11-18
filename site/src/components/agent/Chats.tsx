"use client";
// Opening the agent (Shrey, 2026-11-15): the person's saved chats in the middle of the page, with
// "New chat" above them. Picking one opens it; "All chats" in a chat comes back here. Someone with
// no saved chats goes straight into a new one. Chats are kept 15 days (lib/chats.ts).
import { Loader2, MessageSquare, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { Turn } from "@/lib/agent";
import { deleteChat, listChats, loadChat, type ChatSummary } from "@/lib/chats";
import { shortDate } from "@/lib/format";
import type { ResumeSource } from "./ResumePanel";
import { Chat } from "./Chat";

// The chat open in this tab, so a reload comes back to it.
const OPEN_KEY = "aventra:agent-open";

type Open = { id: string; turns: Turn[]; saved: boolean };
type List = { kind: "loading" } | { kind: "ready"; chats: ChatSummary[] } | { kind: "error"; message: string };

const fresh = (): Open => ({ id: crypto.randomUUID(), turns: [], saved: false });

export function Chats({ name, initialRemaining, resume: initialResume }: { name: string; initialRemaining: number | null; resume: ResumeSource }) {
  // Kept here so an edit saved in one chat is what the next chat's editor opens.
  const [resume, setResume] = useState(initialResume);
  const [list, setList] = useState<List>({ kind: "loading" });
  const [open, setOpen] = useState<Open | null>(null);
  const [opening, setOpening] = useState<string | null>(null);

  const refresh = useCallback(() => listChats().then((chats) => { setList({ kind: "ready", chats }); return chats; }), []);

  useEffect(() => {
    refresh().then(async (chats) => {
      let last: string | null = null;
      try { last = sessionStorage.getItem(OPEN_KEY); } catch {}
      if (last && chats.some((c) => c.id === last)) {
        setOpen({ id: last, turns: await loadChat(last), saved: true });
      } else if (!chats.length) setOpen(fresh()); // nothing to list: start one
    }).catch((e: Error) => { setList({ kind: "error", message: e.message }); setOpen(fresh()); });
  }, [refresh]);

  useEffect(() => {
    try { if (open?.saved) sessionStorage.setItem(OPEN_KEY, open.id); else sessionStorage.removeItem(OPEN_KEY); } catch {}
  }, [open]);

  async function pick(id: string) {
    setOpening(id);
    try { setOpen({ id, turns: await loadChat(id), saved: true }); }
    catch (e) { setList({ kind: "error", message: (e as Error).message }); }
    finally { setOpening(null); }
  }

  async function remove(c: ChatSummary) {
    if (!confirm(`Delete "${c.title}"?`)) return;
    try { await deleteChat(c.id); await refresh(); }
    catch (e) { setList({ kind: "error", message: (e as Error).message }); }
  }

  if (open) {
    const hasList = list.kind !== "ready" || list.chats.length > 0 || open.saved;
    return (
      <Chat key={open.id} id={open.id} initialTurns={open.turns} saved={open.saved} name={name} initialRemaining={initialRemaining}
        onBack={hasList || open.turns.length ? () => { setOpen(null); refresh().catch(() => {}); } : null}
        onSaved={() => { setOpen((o) => (o && !o.saved ? { ...o, saved: true } : o)); refresh().catch(() => {}); }}
        resume={resume} onResumeSaved={(saved) => setResume((r) => ({ ...r, ...saved }))} />
    );
  }

  return (
    <section aria-labelledby="chats-title" className="detail-in mx-auto w-full max-w-[40rem] pt-[6vh]">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="chats-title" className="font-display text-headline leading-tight">Your chats</h2>
          <p className="mt-1 text-meta text-muted">Kept for 15 days, only for you.</p>
        </div>
        <button type="button" onClick={() => setOpen(fresh())}
          className="press inline-flex h-10 items-center gap-1.5 rounded-md bg-ink px-4 text-body font-medium text-canvas duration-quick">
          <Plus aria-hidden className="size-4" />New chat
        </button>
      </div>

      {list.kind === "loading" && <div aria-busy="true" className="mt-6 grid gap-2">{[0, 1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-surface" />)}</div>}
      {list.kind === "error" && <p role="alert" className="mt-6 text-body text-muted">Couldn&apos;t load your chats: {list.message}</p>}
      {list.kind === "ready" && (
        <ul className="mt-6 grid gap-2">
          {list.chats.map((c) => (
            <li key={c.id} className="group flex items-center gap-1 rounded-lg border border-card-line bg-card transition-colors duration-quick hover:border-ink/30">
              <button type="button" onClick={() => pick(c.id)} disabled={opening !== null}
                className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 text-left">
                {opening === c.id ? <Loader2 aria-hidden className="size-4 shrink-0 animate-spin text-muted" /> : <MessageSquare aria-hidden className="size-4 shrink-0 text-muted" />}
                <span className="min-w-0 flex-1 truncate text-body font-medium">{c.title}</span>
                <span className="shrink-0 text-meta text-muted">{shortDate(c.updated_at)}</span>
              </button>
              <button type="button" onClick={() => remove(c)} aria-label={`Delete chat: ${c.title}`}
                className="mr-2 grid size-9 shrink-0 place-items-center rounded-md text-muted transition-colors duration-quick hover:bg-surface hover:text-ink">
                <Trash2 aria-hidden className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
