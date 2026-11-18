// The agent chat (api/src/agent.py, POST /api/agent/chat). The conversation lives in the browser;
// each message sends the recent turns. Contact emails arrive only on draft cards.
import { api } from "./tracker";

export interface AgentJob { id: string; title: string; company: string; location: string | null; asks_years: string | null; url: string }
export interface AgentPerson { id: number; kind: "hr" | "founder"; name: string; company: string; title: string | null; linkedin: string | null; has_email: boolean }
// Chats saved before 2026-11-16 hold startups without builds/described/matched_*, and with sample_titles.
export interface AgentStartup {
  company: string; yc_batch: string | null; company_url: string | null; founder_id: number; founder: string; open_jobs: number;
  builds?: string | null; described?: boolean; matched_kinds?: string[]; matched_skills?: string[]; sample_titles?: string[];
}
export interface AgentDraft {
  type: "draft";
  contact: { id: number; name: string; company: string; title: string | null; linkedin: string | null };
  to: string | null;
  subject: string;
  body: string;
  job_id: string | null;
  gmail_url: string | null;
  reveals_left?: number;
  held_back?: boolean; // this person had enough emails today across everyone, or the site hit its cap
  /** Set on drafts reopened from a saved chat: the address was shown then, and isn't stored. */
  address_removed?: boolean;
}
export interface AgentConnection { id: number; name: string; company: string | null; position: string | null; linkedin: string | null }
/** A LinkedIn message to one of the person's own connections: they copy it and send it themselves. */
export interface AgentNote { type: "linkedin"; person: AgentConnection; body: string; job_id: string | null }
export type AgentCard =
  | { type: "jobs"; jobs: AgentJob[] }
  | { type: "connections"; people: AgentConnection[] }
  | AgentNote
  | { type: "people"; people: AgentPerson[] }
  | { type: "startups"; startups: AgentStartup[]; offset?: number; has_more?: boolean }
  | AgentDraft
  | { type: "resume_editor" }; // the agent opened the resume editor beside the chat

export interface Turn { role: "user" | "model"; text: string; cards?: AgentCard[]; sources?: string[] }
export interface Reply { reply: string; cards: AgentCard[]; sources: string[]; remaining: number }

const SENT_TURNS = 12; // the API reads at most this many

export const sendMessage = (turns: Turn[]): Promise<Reply> =>
  api("/api/agent/chat", { method: "POST", body: JSON.stringify({ messages: turns.slice(-SENT_TURNS).map(({ role, text }) => ({ role, text })) }) });

/** Gmail's compose window with the (possibly edited) draft filled in. */
export const gmailUrl = (to: string, subject: string, body: string) =>
  `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
