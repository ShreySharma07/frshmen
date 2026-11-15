// The person's own LinkedIn connections (docs/decisions.md, 2026-11-15), from LinkedIn's
// Connections.csv export. Parsed here in the browser and written straight to Supabase as the
// signed-in person; RLS keeps each person to their own rows (db/postgres/0015_connections.sql).
// Email addresses in the export are dropped here and never leave the browser.
import { rest } from "./session";

export const CONNECTIONS_MAX = 5000; // the table's cap per person
const LINKEDIN = /^https:\/\/([a-z]+\.)?linkedin\.com\//;

export interface Connection { name: string; company: string | null; position: string | null; linkedin: string | null; connected_on: string | null }

/** Rows of a CSV (RFC 4180: quoted fields may hold commas, quotes and line breaks). */
export function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

const clip = (s: string | undefined, n: number) => (s ?? "").trim().slice(0, n) || null;

/** "15 Nov 2026" (LinkedIn's format) as 2026-11-15, or null. */
function day(s: string | undefined): string | null {
  const t = Date.parse(`${s ?? ""} UTC`);
  return Number.isNaN(t) ? null : new Date(t).toISOString().slice(0, 10);
}

/** The connections in LinkedIn's export. The file opens with a "Notes:" paragraph before the header row. */
export function parseConnections(text: string): Connection[] {
  const rows = csvRows(text.replace(/^﻿/, ""));
  const at = rows.findIndex((r) => r.some((c) => c.trim() === "First Name") && r.some((c) => c.trim() === "Company"));
  if (at < 0) throw new Error("This doesn't look like LinkedIn's Connections.csv (no \"First Name\" and \"Company\" columns).");
  const head = rows[at].map((c) => c.trim());
  const col = (name: string) => head.indexOf(name);
  const [first, last, url, company, position, on] = ["First Name", "Last Name", "URL", "Company", "Position", "Connected On"].map(col);
  const out: Connection[] = [];
  for (const r of rows.slice(at + 1)) {
    const name = clip(`${r[first] ?? ""} ${last >= 0 ? r[last] ?? "" : ""}`, 120);
    if (!name) continue; // blank lines, and people who hid their name from exports
    const link = (url >= 0 ? r[url] ?? "" : "").trim();
    out.push({ name, company: company >= 0 ? clip(r[company], 120) : null, position: position >= 0 ? clip(r[position], 160) : null,
      linkedin: LINKEDIN.test(link) && link.length <= 300 ? link : null, connected_on: on >= 0 ? day(r[on]) : null });
  }
  // Over the cap: keep the most recent.
  return out.length <= CONNECTIONS_MAX ? out
    : [...out].sort((a, b) => (b.connected_on ?? "").localeCompare(a.connected_on ?? "")).slice(0, CONNECTIONS_MAX);
}

async function ok(res: Response) {
  if (res.ok) return res;
  const body = await res.json().catch(() => null);
  throw new Error(body?.message ?? `${res.status}`);
}

/** How many are saved, and when the last file was uploaded. */
export async function connectionsSummary(): Promise<{ count: number; added_at: string | null }> {
  const res = await ok(await rest("connections?select=added_at&order=added_at.desc&limit=1", { headers: { Prefer: "count=exact" } }));
  const rows: { added_at: string }[] = await res.json();
  const total = Number(res.headers.get("content-range")?.split("/")[1] ?? 0);
  return { count: Number.isFinite(total) ? total : 0, added_at: rows[0]?.added_at ?? null };
}

/** Replaces everything saved with this file's connections. */
export async function replaceConnections(userId: string, people: Connection[]) {
  await deleteConnections(userId);
  if (people.length) await ok(await rest("connections", { method: "POST", headers: { Prefer: "return=minimal" }, body: JSON.stringify(people) }));
}

export async function deleteConnections(userId: string) {
  await ok(await rest(`connections?student_id=eq.${encodeURIComponent(userId)}`, { method: "DELETE" }));
}
