"use client";

// The departures board (critique 2026-10-23): the newest openings as a split-flap board, in place
// of the marquees. Each cell is a row of flaps; when a value changes the flaps spin through the
// alphabet and settle a few milliseconds apart, as a real board does. Rows arrive at the top while
// the board is on screen, newest last, until the board is up to date. Times are the reader's own
// clock, written after load. Every row links to its posting. With reduced motion the board is
// simply printed.
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { fetchJobs } from "@/lib/api";
import { flaps, STARTER, toRow, type BoardRow } from "./board";

const ROWS = 7;
const ARRIVE_MS = 4200;
const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-";

// Columns per layout, in flaps. Phones keep what decides a click: who, what it asks, when.
type Col = "posted" | "company" | "title" | "city" | "asks";
const LAYOUTS: Record<"wide" | "mid" | "narrow", [Col, number][]> = {
  wide: [["posted", 5], ["company", 12], ["title", 26], ["city", 10], ["asks", 9]],
  mid: [["posted", 5], ["company", 12], ["title", 20], ["asks", 9]],
  narrow: [["posted", 5], ["company", 11], ["asks", 9]],
};
const HEAD: Record<Col, string> = { posted: "Posted", company: "Company", title: "Role", city: "City", asks: "Asks" };

const media = (q: string) => (typeof window === "undefined" ? null : matchMedia(q));
const subscribeLayout = (cb: () => void) => {
  const qs = [media("(min-width: 64rem)"), media("(min-width: 40rem)")];
  qs.forEach((m) => m?.addEventListener("change", cb));
  return () => qs.forEach((m) => m?.removeEventListener("change", cb));
};
const layoutNow = () => (media("(min-width: 64rem)")?.matches ? "wide" : media("(min-width: 40rem)")?.matches ? "mid" : "narrow");
const noChange = () => () => {};

export function Board() {
  const layout = useSyncExternalStore(subscribeLayout, layoutNow, () => "wide" as const);
  const mounted = useSyncExternalStore(noChange, () => true, () => false);
  const root = useRef<HTMLDivElement>(null);
  // `queue` holds what is still to arrive (oldest first); the board shows the newest ROWS seen so far.
  const [all, setAll] = useState<BoardRow[]>(STARTER);
  const [shown, setShown] = useState(ROWS);

  useEffect(() => {
    const ctl = new AbortController();
    fetchJobs({ role: "all" }, 1, false, ctl.signal)
      .then((r) => { if (r.jobs.length >= ROWS + 3) { setAll(r.jobs.map(toRow)); setShown(ROWS); } })
      .catch(() => {});
    return () => ctl.abort();
  }, []);

  // all[] is newest first. Start a few rows back and let the newer ones arrive one at a time.
  const backlog = Math.max(0, Math.min(all.length - ROWS, 5));
  const arrived = Math.min(backlog, Math.max(0, shown - ROWS));
  const rows = all.slice(backlog - arrived, backlog - arrived + ROWS);

  useEffect(() => {
    const el = root.current;
    if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches || arrived >= backlog) return;
    // Only while someone can see it: on screen, in a visible panel, in a visible tab.
    const t = setInterval(() => {
      const r = el.getBoundingClientRect();
      const onScreen = r.bottom > 0 && r.top < innerHeight && !document.hidden;
      if (onScreen && el.checkVisibility?.({ opacityProperty: true, visibilityProperty: true }) !== false) setShown((n) => n + 1);
    }, ARRIVE_MS);
    return () => clearInterval(t);
  }, [arrived, backlog]);

  const cols = LAYOUTS[layout];
  const time = (iso: string | null) => (mounted && iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) : "--:--");
  const value = (row: BoardRow, c: Col) => (c === "posted" ? time(row.posted) : row[c]);

  return (
    <div ref={root} className="board lp-dark rounded-2xl bg-lp-term p-3 text-lp-term-ink shadow-lg sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-3 px-1 font-mono text-[11px] tracking-[0.14em] text-lp-term-muted uppercase">
        <span className="flex items-center gap-2"><i aria-hidden className="size-1.5 rounded-full bg-lp-accent" />Arrivals</span>
        <span>{arrived >= backlog ? "Up to date" : "Newest openings"}</span>
      </div>
      <div className="board-body" style={{ ["--n" as string]: cols.reduce((n, [, w]) => n + w, 0) + cols.length * 1.6 }}>
      <div aria-hidden className="board-grid board-head">
        {cols.map(([c, w]) => <span key={c} style={{ width: `calc(${w} * var(--flap-step) - 1px)` }}><b>{HEAD[c]}</b></span>)}
      </div>
      <ol className="board-rows">
        {rows.map((row) => (
          <li key={row.id}>
            <a href={row.url} target="_blank" rel="noopener noreferrer" className="board-row board-grid">
              <span className="sr-only">{row.company}: {row.title}{row.city ? `, ${row.city}` : ""}. Asks: {row.asks}. Posted {time(row.posted)}.</span>
              {cols.map(([c, w]) => <Flaps key={c} text={flaps(value(row, c), w)} tone={c === "asks" ? row.tone : undefined} />)}
            </a>
          </li>
        ))}
      </ol>
      </div>
    </div>
  );
}

// One cell. React only ever sets the final text (as markup); the effect then spins the flaps it
// just wrote and lets each settle on its letter.
function Flaps({ text, tone }: { text: string; tone?: BoardRow["tone"] }) {
  const cell = useRef<HTMLSpanElement>(null);
  const html = [...text].map((ch) => `<span class="flap">${ch === " " ? "&nbsp;" : escape(ch)}</span>`).join("");

  useEffect(() => {
    const el = cell.current;
    if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const tiles = [...el.children] as HTMLElement[];
    const start = performance.now();
    const settle = tiles.map((_, i) => start + 90 + i * 22 + Math.random() * 120);
    let frame = 0, last = 0;
    const spin = (now: number) => {
      let busy = false;
      const tick = now - last > 40; // flaps turn ~25 times a second, not every frame
      if (tick) last = now;
      tiles.forEach((t, i) => {
        const ch = text[i];
        if (ch === " ") return;
        if (now < settle[i]) {
          busy = true;
          if (tick) { t.textContent = GLYPHS[(Math.random() * GLYPHS.length) | 0]; t.classList.add("is-turning"); }
        } else if (t.classList.contains("is-turning")) {
          t.textContent = ch;
          t.classList.remove("is-turning");
        }
      });
      frame = busy ? requestAnimationFrame(spin) : 0;
    };
    frame = requestAnimationFrame(spin);
    return () => {
      cancelAnimationFrame(frame);
      tiles.forEach((t, i) => { t.textContent = text[i] === " " ? " " : text[i]; t.classList.remove("is-turning"); });
    };
  }, [text]);

  return <span ref={cell} aria-hidden className={`flaps ${tone ? `tone-${tone}` : ""}`} dangerouslySetInnerHTML={{ __html: html }} />;
}

const escape = (ch: string) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch] ?? ch;
