// Saved agent chats (docs/decisions.md, 2026-11-15): read and written straight to Supabase as the
// signed-in person; RLS keeps each person to their own (db/postgres/0017_agent_chats.sql).
import type { AgentCard, Turn } from "./agent";
import { rest } from "./session";

export interface ChatSummary { id: string; title: string; updated_at: string }

const KEEP_DAYS = 15; // Shrey, 2026-11-15 (first planned as 90)

async function ok(res: Response) {
  if (res.ok) return res;
  const body = await res.json().catch(() => null);
  throw new Error(body?.message ?? `${res.status}`);
}

/** The person's chats, most recent first: the last 30, used within 15 days. */
export async function listChats(): Promise<ChatSummary[]> {
  const since = new Date(Date.now() - KEEP_DAYS * 864e5).toISOString();
  const res = await ok(await rest(`agent_chats?select=id,title,updated_at&updated_at=gt.${encodeURIComponent(since)}&order=updated_at.desc&limit=30`));
  return res.json();
}

export async function loadChat(id: string): Promise<Turn[]> {
  const res = await ok(await rest(`agent_chats?select=turns&id=eq.${encodeURIComponent(id)}`));
  const rows: { turns: Turn[] }[] = await res.json();
  if (!rows.length) throw new Error("that chat is gone (chats are kept 15 days)");
  return rows[0].turns;
}

/** A draft's address is shown once and never stored: the saved copy keeps who it was for, not
 *  the email (the table refuses one). */
function stripped(card: AgentCard): AgentCard {
  return card.type === "draft" ? { ...card, to: null, gmail_url: null, address_removed: card.to !== null } : card;
}

const forStorage = (turns: Turn[]) => turns.slice(-40).map((t) => (t.cards ? { ...t, cards: t.cards.map(stripped) } : t));

/** The first thing the person asked, as the chat's name. */
export const titleOf = (turns: Turn[]) => (turns.find((t) => t.role === "user")?.text ?? "New chat").replace(/\s+/g, " ").trim().slice(0, 80) || "New chat";

/** Saves the chat: creates it the first time (with the id the page already uses), then updates it. */
export async function saveChat(id: string, turns: Turn[], isNew: boolean) {
  const body = JSON.stringify(isNew ? { id, title: titleOf(turns), turns: forStorage(turns) } : { turns: forStorage(turns) });
  await ok(await rest(isNew ? "agent_chats" : `agent_chats?id=eq.${encodeURIComponent(id)}`,
    { method: isNew ? "POST" : "PATCH", headers: { Prefer: "return=minimal" }, body }));
}

export async function deleteChat(id: string) {
  await ok(await rest(`agent_chats?id=eq.${encodeURIComponent(id)}`, { method: "DELETE" }));
}
