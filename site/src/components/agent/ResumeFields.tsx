"use client";
// The resume as fields (docs/decisions.md, 2026-11-17, concept A's Content tab): name, contact lines,
// and sections of entries (title … right, second row … right, bullets) or plain lines, as read from
// the person's PDF. Order is changed with up/down buttons, which a keyboard and a screen reader reach.
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { emptyEntry, type Entry, type Item, type ResumeDoc, type Section } from "@/lib/resumeDoc";

const input = "w-full min-w-0 rounded-md border border-line bg-canvas px-2.5 py-1.5 text-body outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent/40";
const icon = "grid size-8 shrink-0 place-items-center rounded-md text-muted transition-colors duration-quick hover:bg-surface hover:text-ink disabled:opacity-30";
const add = "inline-flex items-center gap-1 text-meta font-medium text-accent-text underline-offset-2 hover:underline";

function move<T>(xs: T[], i: number, by: number): T[] {
  const j = i + by;
  if (j < 0 || j >= xs.length) return xs;
  const next = [...xs];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** A text box that grows with its text, for bullets and lines that wrap. */
function Grow({ value, onChange, label, placeholder }: { value: string; onChange: (v: string) => void; label: string; placeholder?: string }) {
  return <textarea rows={1} value={value} aria-label={label} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
    className={`${input} resize-none leading-snug [field-sizing:content]`} />;
}

function Order({ i, n, onMove, onDelete, what }: { i: number; n: number; onMove: (by: number) => void; onDelete: () => void; what: string }) {
  return (
    <span className="flex shrink-0">
      <button type="button" onClick={() => onMove(-1)} disabled={i === 0} aria-label={`Move ${what} up`} className={icon}><ArrowUp aria-hidden className="size-4" /></button>
      <button type="button" onClick={() => onMove(1)} disabled={i === n - 1} aria-label={`Move ${what} down`} className={icon}><ArrowDown aria-hidden className="size-4" /></button>
      <button type="button" onClick={onDelete} aria-label={`Delete ${what}`} className={icon}><Trash2 aria-hidden className="size-4" /></button>
    </span>
  );
}

function EntryFields({ e, set, label }: { e: Entry; set: (e: Entry) => void; label: string }) {
  const bullet = (k: number, v: string) => set({ ...e, bullets: e.bullets.map((b, j) => (j === k ? v : b)) });
  return (
    <div className="grid gap-1.5">
      <input value={e.title} onChange={(x) => set({ ...e, title: x.target.value })} aria-label={`${label}: title`} placeholder="Title, e.g. ML Intern" className={`${input} font-medium`} />
      <input value={e.sub} onChange={(x) => set({ ...e, sub: x.target.value })} aria-label={`${label}: organisation`} placeholder="Where, e.g. Acme Labs" className={input} />
      <div className="grid grid-cols-2 gap-1.5">
        <input value={e.right} onChange={(x) => set({ ...e, right: x.target.value })} aria-label={`${label}: dates`} placeholder="Dates" className={input} />
        <input value={e.subRight} onChange={(x) => set({ ...e, subRight: x.target.value })} aria-label={`${label}: place`} placeholder="Place" className={input} />
      </div>
      <ul className="grid gap-1.5">
        {e.bullets.map((b, k) => (
          // Bullets keep only Delete, so their text gets the width; entries and sections carry the ordering.
          <li key={k} className="flex items-start gap-1">
            <span aria-hidden className="pt-2 text-muted">•</span>
            <Grow value={b} onChange={(v) => bullet(k, v)} label={`${label}: bullet ${k + 1}`} />
            <button type="button" onClick={() => set({ ...e, bullets: e.bullets.filter((_, j) => j !== k) })} aria-label={`Delete ${label} bullet ${k + 1}`} className={icon}><Trash2 aria-hidden className="size-4" /></button>
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => set({ ...e, bullets: [...e.bullets, ""] })} className={`${add} justify-self-start pl-4`}><Plus aria-hidden className="size-3.5" />Bullet</button>
    </div>
  );
}

function SectionFields({ s, set, si }: { s: Section; set: (s: Section) => void; si: number }) {
  const item = (i: number, it: Item) => set({ ...s, items: s.items.map((x, j) => (j === i ? it : x)) });
  const name = s.heading || `Section ${si + 1}`;
  return (
    <div className="grid gap-2">
      {s.items.map((it, i) => it.kind === "entry" ? (
        // An entry's controls sit in a header row, so its fields get the panel's full width on a phone.
        <div key={i} className="rounded-md border border-card-line bg-canvas/60 p-2">
          <div className="-mt-1 mb-1 flex items-center justify-between">
            <span className="min-w-0 truncate text-caption text-muted">{it.title || `Entry ${i + 1}`}</span>
            <Order i={i} n={s.items.length} what={`entry ${i + 1}`}
              onMove={(by) => set({ ...s, items: move(s.items, i, by) })} onDelete={() => set({ ...s, items: s.items.filter((_, j) => j !== i) })} />
          </div>
          <EntryFields e={it} set={(e) => item(i, e)} label={`${name}, entry ${i + 1}`} />
        </div>
      ) : (
        <div key={i} className="flex items-start gap-1">
          <div className="min-w-0 flex-1"><Grow value={it.text} onChange={(v) => item(i, { ...it, text: v })} label={`${name}, line ${i + 1}`} /></div>
          <Order i={i} n={s.items.length} what={`line ${i + 1}`}
            onMove={(by) => set({ ...s, items: move(s.items, i, by) })} onDelete={() => set({ ...s, items: s.items.filter((_, j) => j !== i) })} />
        </div>
      ))}
      <div className="flex gap-4">
        <button type="button" onClick={() => set({ ...s, items: [...s.items, emptyEntry()] })} className={add}><Plus aria-hidden className="size-3.5" />Entry</button>
        <button type="button" onClick={() => set({ ...s, items: [...s.items, { kind: "text", text: "" }] })} className={add}><Plus aria-hidden className="size-3.5" />Line</button>
      </div>
    </div>
  );
}

export function ResumeFields({ doc, set }: { doc: ResumeDoc; set: (d: ResumeDoc) => void }) {
  const section = (si: number, s: Section) => set({ ...doc, sections: doc.sections.map((x, j) => (j === si ? s : x)) });
  return (
    <div className="grid gap-5">
      <div className="grid gap-1.5">
        <input value={doc.name} onChange={(e) => set({ ...doc, name: e.target.value })} aria-label="Your name" placeholder="Your name" className={`${input} text-[1.0625rem] font-medium`} />
        {doc.contact.map((c, k) => (
          <div key={k} className="flex items-center gap-1">
            <input value={c} onChange={(e) => set({ ...doc, contact: doc.contact.map((x, j) => (j === k ? e.target.value : x)) })} aria-label={`Contact line ${k + 1}`} className={input} />
            <Order i={k} n={doc.contact.length} what={`contact line ${k + 1}`} onMove={(by) => set({ ...doc, contact: move(doc.contact, k, by) })}
              onDelete={() => set({ ...doc, contact: doc.contact.filter((_, j) => j !== k) })} />
          </div>
        ))}
        <button type="button" onClick={() => set({ ...doc, contact: [...doc.contact, ""] })} className={`${add} justify-self-start`}><Plus aria-hidden className="size-3.5" />Contact line</button>
      </div>
      {doc.sections.map((s, si) => (
        <section key={si} aria-label={s.heading || `Section ${si + 1}`} className="grid gap-2 border-t border-line pt-4">
          <div className="flex items-center gap-1">
            <input value={s.heading} onChange={(e) => section(si, { ...s, heading: e.target.value })} aria-label={`Section ${si + 1} heading`}
              placeholder="Section, e.g. Projects" className={`${input} text-caption font-medium uppercase tracking-wide`} />
            <Order i={si} n={doc.sections.length} what={`section ${s.heading || si + 1}`} onMove={(by) => set({ ...doc, sections: move(doc.sections, si, by) })}
              onDelete={() => { if (confirm(`Delete the ${s.heading || "untitled"} section?`)) set({ ...doc, sections: doc.sections.filter((_, j) => j !== si) }); }} />
          </div>
          <SectionFields s={s} si={si} set={(x) => section(si, x)} />
        </section>
      ))}
      <button type="button" onClick={() => set({ ...doc, sections: [...doc.sections, { heading: "", items: [emptyEntry()] }] })}
        className={`${add} justify-self-start border-t border-line pt-4`}><Plus aria-hidden className="size-3.5" />Section</button>
    </div>
  );
}
