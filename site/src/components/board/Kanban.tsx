"use client";
// The tracker as a board (docs/decisions.md, 2026-11-04 and 2026-11-12): Saved, Applied,
// Interview, Offer, Closed. Drag a card to another column, or use its "Move to" menu (keyboard,
// screen readers, phones).
//
// Built to stay readable with hundreds of applications: a column shows its first few cards and
// a "Show more"; applications that have gone quiet, and the Closed column, fold into one stack
// until opened. A marigold tape on a card means it needs you this week.
import { DndContext, KeyboardSensor, PointerSensor, TouchSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { GripVertical, X } from "lucide-react";
import { useState } from "react";
import { CompanyMark } from "@/components/CompanyMark";
import type { Step } from "@/lib/board";
import { shortDate } from "@/lib/format";
import { STAGES, type Stage, type Tracked, type Verdict } from "@/lib/tracker";

const HINT: Record<Stage, string> = {
  saved: "Save jobs from the list to start here.",
  applied: "Drag a job here once you've applied.",
  interview: "Drag a job here when you get an interview.",
  offer: "Offers land here.",
  rejected: "Closed applications go here.",
};
const SHOWN = 6; // cards a column shows before "Show more"
export const stageLabel = (s: Stage) => (s === "rejected" ? "Closed" : STAGES.find((x) => x.v === s)!.label);

export interface CardInfo { step: Step; fit?: Verdict["fit"]; onResume?: () => void }

export function Kanban({ items, info, onMove, onRemove }: {
  items: Tracked[];
  info: (t: Tracked) => CardInfo;
  onMove: (t: Tracked, to: Stage) => void;
  onRemove: (t: Tracked) => void;
}) {
  // A small drag distance (and a touch hold) so clicks, scrolling and the Move menu still work.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } }),
    useSensor(KeyboardSensor),
  );
  function onDragEnd(e: DragEndEvent) {
    const t = items.find((x) => String(x.id) === String(e.active.id));
    const to = e.over?.id as Stage | undefined;
    if (t && to && to !== t.status) onMove(t, to);
  }
  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}
      accessibility={{ screenReaderInstructions: { draggable: "Press space to pick up a job, arrow keys to move it to another column, space again to drop it." } }}>
      <div className="grid gap-4 md:grid-cols-5">
        {STAGES.map((s) => (
          <Column key={s.v} stage={s.v} items={items.filter((t) => t.status === s.v)} info={info} onMove={onMove} onRemove={onRemove} />
        ))}
      </div>
    </DndContext>
  );
}

function Column({ stage, items, info, onMove, onRemove }: {
  stage: Stage; items: Tracked[]; info: (t: Tracked) => CardInfo;
  onMove: (t: Tracked, to: Stage) => void; onRemove: (t: Tracked) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  const [all, setAll] = useState(false); // past the first SHOWN
  const [folded, setFolded] = useState(true); // the quiet or closed stack
  const closed = stage === "rejected";
  const live = closed ? [] : items.filter((t) => !info(t).step.quiet);
  const tucked = closed ? items : items.filter((t) => info(t).step.quiet);
  const shown = all ? live : live.slice(0, SHOWN);
  const card = (t: Tracked) => <Card key={t.id} t={t} info={info(t)} onMove={onMove} onRemove={onRemove} />;
  return (
    <section ref={setNodeRef} aria-label={`${stageLabel(stage)}, ${items.length}`}
      className={`min-w-0 rounded-lg p-1.5 transition-colors duration-quick ${isOver ? "bg-selected shadow-[inset_0_0_0_2px_var(--accent)]" : ""}`}>
      <h3 className={`mb-3 flex items-baseline gap-2 px-1 font-display text-[1.75rem] leading-none ${closed ? "text-muted" : ""}`}>
        {stageLabel(stage)}
        {/* A new key when the count changes, so the number ticks: something moved here or left. */}
        <span key={items.length} className="tick font-mono text-meta text-muted">{items.length}</span>
      </h3>
      {items.length === 0 && (
        <p className="grid h-24 place-items-center rounded-md border-2 border-dashed border-line px-3 text-center text-meta text-muted">{HINT[stage]}</p>
      )}
      <ul className="space-y-2.5">{shown.map(card)}</ul>
      {live.length > SHOWN && (
        <button type="button" onClick={() => setAll((a) => !a)} aria-expanded={all}
          className="press mt-2.5 w-full rounded-md border border-dashed border-line py-2 text-meta font-medium text-muted hover:bg-surface hover:text-ink">
          {all ? "Show fewer" : `Show ${live.length - SHOWN} more`}
        </button>
      )}
      {tucked.length > 0 && (
        <div className="mt-2.5">
          <button type="button" onClick={() => setFolded((f) => !f)} aria-expanded={!folded}
            // Two edges peeking out below: a pile, not one card.
            className="press w-full rounded-md border border-line bg-card px-3 py-2.5 text-left shadow-[0_4px_0_-1px_var(--card),0_4px_0_0_var(--line),0_8px_0_-2px_var(--card),0_8px_0_-1px_var(--line)] hover:bg-surface">
            <span className="block text-body font-medium">{closed ? `${tucked.length} closed` : `Gone quiet: ${tucked.length}`}</span>
            <span className="block text-meta text-muted">{closed ? "Rejected, withdrawn or the posting closed." : "No reply in 30 days. Kept, but off the board."} {folded ? "Open" : "Fold away"}</span>
          </button>
          {!folded && <ul className="mt-4 space-y-2.5">{tucked.map(card)}</ul>}
        </div>
      )}
    </section>
  );
}

const FIT_TONE = { strong: "bg-accent text-on-accent", partial: "border border-line bg-surface text-ink", weak: "border border-line text-muted" };

function Card({ t, info, onMove, onRemove }: {
  t: Tracked; info: CardInfo; onMove: (t: Tracked, to: Stage) => void; onRemove: (t: Tracked) => void;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, isDragging } = useDraggable({ id: String(t.id) });
  const company = t.jobs?.companies?.name ?? "";
  const { step, fit, onResume } = info;
  // The pointer can drag from anywhere on the card; the handle is the card's one keyboard and
  // screen-reader control, so the link and buttons inside aren't nested in another button.
  return (
    <li ref={setNodeRef} {...listeners}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0) rotate(1.5deg)` } : undefined}
      // card-in: a card that has just landed in this column settles in, so the move is seen.
      className={`card-in relative cursor-grab touch-manipulation rounded-md border border-card-line bg-card p-3 text-body shadow-raised ${isDragging ? "z-10 cursor-grabbing shadow-menu" : "transition-shadow duration-quick hover:shadow-menu"}`}>
      {step.due && <span aria-hidden className="absolute -top-1.5 left-1/2 h-3 w-10 -translate-x-1/2 -rotate-2 rounded-[1px] bg-accent/80" />}
      <div className="flex items-center gap-2">
        <button type="button" ref={setActivatorNodeRef} {...attributes} aria-label={`Drag ${t.jobs?.title ?? "job"}`}
          className="-ml-1.5 grid h-5 w-4 shrink-0 cursor-grab place-items-center rounded-sm text-faint outline-none hover:text-muted focus-visible:ring-2 focus-visible:ring-accent/40">
          <GripVertical aria-hidden className="size-3.5" />
        </button>
        <CompanyMark company={company} size="sm" />
        <p className="min-w-0 flex-1 truncate text-meta text-muted">{company}</p>
        <button type="button" aria-label={`Remove ${t.jobs?.title ?? "job"}`} onPointerDown={(e) => e.stopPropagation()} onClick={() => onRemove(t)}
          className="-mr-1.5 grid size-6 shrink-0 place-items-center rounded-sm text-muted hover:bg-surface hover:text-ink">
          <X aria-hidden className="size-3.5" />
        </button>
      </div>
      <a href={t.jobs?.url} target="_blank" rel="noopener" onPointerDown={(e) => e.stopPropagation()}
        className="mt-2 line-clamp-2 font-medium leading-snug hover:underline">{t.jobs?.title}</a>
      <p className="mt-2 text-meta">
        <span className={step.due ? "rounded-sm bg-mark px-1 font-medium" : "text-muted"}>{step.text}</span>
      </p>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">
        <span className="whitespace-nowrap">{shortDate(t.applied_at ?? t.created_at)}</span>
        {fit && <span className={`whitespace-nowrap rounded-sm px-1.5 first-letter:uppercase ${FIT_TONE[fit]}`}>{fit} fit</span>}
        {onResume && (
          <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={onResume} className="font-medium text-accent-text underline underline-offset-2">Tailored resume</button>
        )}
        <select aria-label={`Move ${t.jobs?.title ?? "job"} to`} value={t.status} onPointerDown={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}
          onChange={(e) => onMove(t, e.target.value as Stage)}
          className="ml-auto h-6 rounded-sm border border-line bg-canvas px-1 text-caption outline-none focus:border-ink">
          {STAGES.map((s) => <option key={s.v} value={s.v}>{stageLabel(s.v)}</option>)}
        </select>
      </div>
    </li>
  );
}
