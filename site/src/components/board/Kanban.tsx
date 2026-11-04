"use client";
// The tracker as a board (docs/decisions.md, 2026-11-04): Saved, Applied, Interview, Offer,
// Rejected. Drag a card to another column, or use its "Move to" menu (keyboard, screen readers,
// phones). Empty columns shrink to a slim strip with a hint instead of a "0".
import { DndContext, KeyboardSensor, PointerSensor, TouchSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { GripVertical, X } from "lucide-react";
import { CompanyMark } from "@/components/CompanyMark";
import { shortDate } from "@/lib/format";
import { STAGES, type Stage, type Tracked, type Verdict } from "@/lib/tracker";

const HINT: Record<Stage, string> = {
  saved: "Save jobs from the list to start here.",
  applied: "Drag a job here once you've applied.",
  interview: "Drag a job here when you get an interview.",
  offer: "Offers land here.",
  rejected: "Closed applications go here.",
};

export function Kanban({ items, verdicts, onMove, onRemove }: {
  items: Tracked[];
  verdicts: Record<string, Verdict["fit"]>; // job id -> latest Gemini verdict
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
      <div className="flex gap-2 overflow-x-auto pb-1 max-md:flex-col">
        {STAGES.map((s) => (
          <Column key={s.v} stage={s.v} label={s.label} items={items.filter((t) => t.status === s.v)}
            verdicts={verdicts} onMove={onMove} onRemove={onRemove} />
        ))}
      </div>
    </DndContext>
  );
}

function Column({ stage, label, items, verdicts, onMove, onRemove }: {
  stage: Stage; label: string; items: Tracked[]; verdicts: Record<string, Verdict["fit"]>;
  onMove: (t: Tracked, to: Stage) => void; onRemove: (t: Tracked) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  const empty = items.length === 0;
  const ring = isOver ? "border-accent bg-selected" : "border-line";
  if (empty) {
    return (
      <section ref={setNodeRef} aria-label={`${label}, empty`}
        className={`flex shrink-0 rounded-lg border border-dashed transition-colors duration-quick md:w-11 md:flex-col md:items-center md:py-3 max-md:items-center max-md:gap-2 max-md:px-3 max-md:py-2 ${ring}`}>
        <h3 className="text-meta font-medium text-muted md:[writing-mode:vertical-rl] md:rotate-180">{label}</h3>
        <p className="text-caption text-muted md:sr-only">{HINT[stage]}</p>
      </section>
    );
  }
  return (
    <section ref={setNodeRef} aria-label={label}
      className={`flex min-w-[11.5rem] flex-1 flex-col rounded-lg border p-2 transition-colors duration-quick ${ring}`}>
      <h3 className="mb-2 flex items-baseline justify-between px-1 text-meta font-medium">
        {label} <span className="font-mono text-caption text-muted">{items.length}</span>
      </h3>
      <ul className="space-y-2">
        {items.map((t) => <Card key={t.id} t={t} fit={verdicts[t.job_id]} onMove={onMove} onRemove={onRemove} />)}
      </ul>
    </section>
  );
}

const FIT_TONE = { strong: "bg-accent text-on-accent", partial: "border border-line bg-surface text-ink", weak: "border border-line text-muted" };

function Card({ t, fit, onMove, onRemove }: {
  t: Tracked; fit?: Verdict["fit"]; onMove: (t: Tracked, to: Stage) => void; onRemove: (t: Tracked) => void;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, isDragging } = useDraggable({ id: String(t.id) });
  const company = t.jobs?.companies?.name ?? "";
  // The pointer can drag from anywhere on the card; the handle is the card's one keyboard and
  // screen-reader control, so the link and buttons inside aren't nested in another button.
  return (
    <li ref={setNodeRef} {...listeners}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      className={`cursor-grab touch-manipulation rounded-md border border-line bg-canvas p-2.5 text-body shadow-raised ${isDragging ? "z-10 cursor-grabbing opacity-90 shadow-menu" : ""}`}>
      <div className="flex items-start gap-2">
        <button type="button" ref={setActivatorNodeRef} {...attributes} aria-label={`Drag ${t.jobs?.title ?? "job"}`}
          className="-ml-1 mt-0.5 grid h-5 w-4 shrink-0 cursor-grab place-items-center rounded-sm text-faint outline-none hover:text-muted focus-visible:ring-2 focus-visible:ring-accent/40">
          <GripVertical aria-hidden className="size-3.5" />
        </button>
        <CompanyMark company={company} size="sm" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-meta text-muted">{company}</p>
          <a href={t.jobs?.url} target="_blank" rel="noopener" onPointerDown={(e) => e.stopPropagation()}
            className="line-clamp-2 font-medium hover:underline">{t.jobs?.title}</a>
        </div>
        <button type="button" aria-label={`Remove ${t.jobs?.title ?? "job"}`} onPointerDown={(e) => e.stopPropagation()} onClick={() => onRemove(t)}
          className="-mr-1 -mt-1 grid size-6 shrink-0 place-items-center rounded-sm text-muted hover:bg-surface hover:text-ink">
          <X aria-hidden className="size-3.5" />
        </button>
      </div>
      <div className="mt-2 flex items-center gap-2 text-caption text-muted">
        <span>{shortDate(t.applied_at ?? t.created_at)}</span>
        {fit && <span className={`rounded-sm px-1.5 capitalize ${FIT_TONE[fit]}`}>{fit}</span>}
        <select aria-label={`Move ${t.jobs?.title ?? "job"} to`} value={t.status} onPointerDown={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}
            onChange={(e) => onMove(t, e.target.value as Stage)}
            className="ml-auto h-6 rounded-sm border border-line bg-canvas px-1 text-caption outline-none focus:border-accent">
            {STAGES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
        </select>
      </div>
    </li>
  );
}
