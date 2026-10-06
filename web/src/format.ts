import type { Highlight, JobSummary, Level } from "./api";

export function timeAgo(iso: string | null, now = Date.now()): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  if (minutes < 60) return minutes <= 1 ? "just now" : `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export function locationLine(job: JobSummary): string {
  const place = job.location_raw?.trim() || "Location not stated";
  const type = job.location_type ? job.location_type[0].toUpperCase() + job.location_type.slice(1) : null;
  return type && !place.toLowerCase().includes(job.location_type ?? "") ? `${place} (${type})` : place;
}

export function experienceLabel(job: JobSummary): string | null {
  const { yoe_min: lo, yoe_max: hi } = job;
  if (lo === null) return null;
  if (hi === null) return `${lo}+ yrs`;
  return lo === hi ? `${lo} yrs` : `${lo}–${hi} yrs`;
}

const KIND_LABEL: Record<string, string> = {
  fresher_text: "Why fresher",
  fresher_title: "Why fresher",
  batch: "Batch",
  yoe_required: "Experience asked",
  yoe_preferred: "Experience preferred",
  senior_title: "Senior title",
  title: "Title",
  python_stack: "Python stack",
  swe_requirement: "Matches your skills",
  conversion: "Full-time conversion",
};

export const kindLabel = (h: Pick<Highlight, "kind">) => KIND_LABEL[h.kind] ?? h.kind;

export const FAMILY_LABEL: Record<string, string> = {
  ai_ml: "AI / ML",
  backend: "Python backend",
  generic_swe: "Software + AI",
  mobile: "Android / React Native",
};

export const levelLabel = (level: Level) =>
  level === "fresher" ? "Fresher" : level === "maybe" ? "Maybe" : "Experienced";

/** Bullet markers come from the posting's HTML lists; they shouldn't sit inside the highlight. */
export const cleanSnippet = (text: string) => text.replace(/^\s*[-•*]\s+/, "");

/** The classifier's reasons are terse; say them the way a person would. */
export function reasonText(level: Level, reason: string): string {
  if (reason.startsWith("fresher signal")) return "The posting says it's for new grads, freshers or entry level.";
  if (reason.startsWith("batch year")) return "The posting targets a graduation batch that includes yours.";
  if (reason.startsWith("requires at most")) return `It asks for at most ${reason.replace("requires at most ", "")}.`;
  if (reason.startsWith("requires")) return `It asks for ${reason.replace("requires ", "")} of experience.`;
  if (reason.startsWith("senior title")) return "The title is senior, so it isn't a fresher role.";
  if (reason.startsWith("targets batch")) return "It targets a graduation batch that doesn't include yours.";
  if (reason.startsWith("no experience requirement")) return "It states no experience requirement and no fresher signal.";
  if (reason.startsWith("only preferred")) return "Experience is only listed as preferred.";
  return level === "maybe" ? `Unclear: ${reason}.` : reason;
}
