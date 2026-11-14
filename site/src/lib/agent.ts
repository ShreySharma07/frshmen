// The agent chat (api/src/agent.py, POST /api/agent/chat). The conversation lives in the browser;
// each message sends the recent turns. Contact emails arrive only on draft cards.
import { api } from "./tracker";

export interface AgentJob { id: string; title: string; company: string; location: string | null; asks_years: string | null; url: string }
export interface AgentPerson { id: number; kind: "hr" | "founder"; name: string; company: string; title: string | null; linkedin: string | null; has_email: boolean }
export interface AgentStartup { company: string; yc_batch: string | null; notes: string | null; company_url: string | null; founder_id: number; founder: string; open_jobs: number; sample_titles: string[] }
export interface AgentDraft {
  type: "draft";
  contact: { id: number; name: string; company: string; title: string | null; linkedin: string | null };
  to: string | null;
  subject: string;
  body: string;
  job_id: string | null;
  gmail_url: string | null;
  reveals_left?: number;
}
export type AgentCard =
  | { type: "jobs"; jobs: AgentJob[] }
  | { type: "people"; people: AgentPerson[] }
  | { type: "startups"; startups: AgentStartup[] }
  | AgentDraft;

export interface Turn { role: "user" | "model"; text: string; cards?: AgentCard[]; sources?: string[] }
export interface Reply { reply: string; cards: AgentCard[]; sources: string[]; remaining: number }

const SENT_TURNS = 12; // the API reads at most this many

export const sendMessage = (turns: Turn[]): Promise<Reply> =>
  api("/api/agent/chat", { method: "POST", body: JSON.stringify({ messages: turns.slice(-SENT_TURNS).map(({ role, text }) => ({ role, text })) }) });

/** Gmail's compose window with the (possibly edited) draft filled in. */
export const gmailUrl = (to: string, subject: string, body: string) =>
  `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
