import type { JobSummary } from "@/lib/api";

const MAX = 8; // the scale runs 0 to 8+ years; anything above sits at the end
const pct = (n: number) => (Math.min(n, MAX) / MAX) * 100;

/** What a posting asks, as numbers: null when it states no years; `open` for "3+". */
export function asks(job: JobSummary): { min: number; max: number; open: boolean } | null {
  if (job.yoe_min == null) return job.level === "fresher" ? { min: 0, max: 0, open: false } : null;
  const open = job.yoe_min > 0 && (job.yoe_max == null || job.yoe_max === job.yoe_min);
  return { min: job.yoe_min, max: job.yoe_max ?? job.yoe_min, open };
}

/**
 * The years a job asks for, drawn on a 0 to 8+ scale: the bar is the job, the tick is you. A bar
 * that fades out to the right has no upper limit ("3+"); a dashed track means the posting states
 * no years. Decorative: the same facts are always in text next to it.
 */
export function Ruler({ job, you, size = "sm" }: { job: JobSummary; you: number | null; size?: "sm" | "lg" }) {
  const a = asks(job);
  const lg = size === "lg";
  return (
    <span aria-hidden className={`relative block rounded-full ${lg ? "h-3" : "h-1.5"} ${a ? "bg-line" : "bg-[repeating-linear-gradient(90deg,var(--line)_0_4px,transparent_4px_8px)]"}`}>
      {a && (
        <span
          // Keyed by the caller per job, so the bar grows in when a different job opens.
          className={`absolute inset-y-0 origin-left rounded-full ${a.open ? "bg-[linear-gradient(90deg,var(--accent)_45%,transparent)]" : "bg-accent"} ${lg ? "animate-[grow-x_400ms_var(--ease-out-soft)_both]" : ""}`}
          style={{ left: `${pct(a.min)}%`, width: a.open ? `${100 - pct(a.min)}%` : `max(${pct(a.max) - pct(a.min)}%, ${lg ? 12 : 6}px)` }}
        />
      )}
      {you != null && (
        <span className={`absolute w-0.5 -translate-x-1/2 rounded-full bg-ink ${lg ? "-inset-y-1.5" : "-inset-y-1"}`} style={{ left: `${pct(you)}%` }} />
      )}
    </span>
  );
}

/** The numbers under the large ruler. */
export function RulerScale() {
  return (
    <span aria-hidden className="mt-2.5 flex justify-between font-mono text-caption text-muted">
      {Array.from({ length: MAX + 1 }, (_, i) => <span key={i}>{i === MAX ? `${i}+` : i}</span>)}
    </span>
  );
}
