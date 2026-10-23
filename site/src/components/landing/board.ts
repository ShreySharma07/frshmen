// The departures board's rows. STARTER is the newest openings of the 2026-10-23 11:42 UTC run (from
// /api/jobs, every role), so the board shows real jobs before (or without) the API answering.
import type { JobSummary } from "@/lib/api";

export interface BoardRow {
  id: string;
  company: string;
  title: string;
  city: string;
  posted: string | null; // ISO time the company posted it (or Kario first saw it)
  asks: string; // what it asks for, as the board prints it
  tone: "fits" | "years" | "quiet";
  url: string;
}

export function toRow(j: Pick<JobSummary, "id" | "company" | "title" | "url" | "cities" | "countries" | "location_raw" | "location_type" | "posted_at" | "first_seen_at" | "level" | "yoe_min" | "yoe_max">): BoardRow {
  // A city when the posting names one; "Hybrid" or "Remote" alone is a way of working, not a place.
  const raw = j.cities[0] ?? j.location_raw?.split(/[,/;-]/)[0]?.trim() ?? "";
  const place = /^(hybrid|remote|on-?site)$/i.test(raw) ? "" : raw;
  const city = place || (j.location_type === "remote" ? "Remote" : j.countries[0] ?? "");
  const n = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));
  const asks = j.level === "fresher" ? "Freshers"
    : j.yoe_min != null && j.yoe_min > 0 ? (j.yoe_max != null && j.yoe_max > j.yoe_min ? `${n(j.yoe_min)}-${n(j.yoe_max)} yrs` : `${n(j.yoe_min)}+ yrs`)
    : j.level === "experienced" ? "Senior" : "Unstated";
  return {
    id: j.id,
    company: j.company,
    title: j.title,
    city,
    posted: j.posted_at ?? j.first_seen_at,
    asks,
    tone: j.level === "fresher" ? "fits" : asks.endsWith("yrs") ? "years" : "quiet",
    url: j.url,
  };
}

/** Fits the text into a fixed number of flaps, the way a split-flap board would: capitals, cut short. */
export const flaps = (text: string, width: number) => text.toUpperCase().slice(0, width).padEnd(width, " ");

const j = (id: string, company: string, title: string, url: string, city: string, posted: string, level: JobSummary["level"], yoe_min: number | null, yoe_max: number | null) =>
  toRow({ id, company, title, url, cities: [city], countries: [], location_raw: city, location_type: city === "Remote" ? "remote" : null, posted_at: posted, first_seen_at: posted, level, yoe_min, yoe_max });

export const STARTER: BoardRow[] = [
  j("greenhouse:andurilindustries:5272848007", "Anduril", "CNC Operator", "https://boards.greenhouse.io/andurilindustries/jobs/5272848007?gh_jid=5272848007", "Morrisville", "2026-10-23T11:19:12Z", "experienced", 5, null),
  j("greenhouse:anthropic:5460837008", "Anthropic", "International Finance Program Management", "https://job-boards.greenhouse.io/anthropic/jobs/5460837008", "Dublin", "2026-10-23T10:48:50Z", "experienced", 10, null),
  j("ashby:sarvam:bba82f34-1544-421e-a393-3edd8a5f4cb2", "Sarvam AI", "Marketing internship (brand & communication)", "https://jobs.ashbyhq.com/sarvam/bba82f34-1544-421e-a393-3edd8a5f4cb2", "Bengaluru", "2026-10-23T10:47:51Z", "maybe", null, null),
  j("greenhouse:razorpaysoftwareprivatelimited:4746961005", "Razorpay", "Lead Software Development Engineer", "https://job-boards.greenhouse.io/razorpaysoftwareprivatelimited/jobs/4746961005", "Bengaluru", "2026-10-23T10:21:53Z", "experienced", null, null),
  j("ashby:sarvam:db89b576-2456-4cc4-ab0b-c45f8c6c27f0", "Sarvam AI", "Software Development Engineer - Tejas", "https://jobs.ashbyhq.com/sarvam/db89b576-2456-4cc4-ab0b-c45f8c6c27f0", "Bengaluru", "2026-10-23T10:19:22Z", "experienced", 3, 5),
  j("greenhouse:slice:8300434", "slice", "Software Developer, DevEx (Stateful Systems)", "https://slice.careers/careers-listing?gh_jid=8300434", "Remote", "2026-10-23T10:09:07Z", "maybe", null, null),
  j("ashby:harvey:ec9e2cd5-af31-4f9c-8b12-d2088a83753a", "Harvey", "Legal Engineer, Product Specialist (in-house)", "https://jobs.ashbyhq.com/harvey/ec9e2cd5-af31-4f9c-8b12-d2088a83753a", "London", "2026-10-23T09:54:01Z", "experienced", 3, null),
  j("ashby:iceye:6f4c8c5f-a335-4828-8826-e93e02700b34", "ICEYE", "SAR Training Specialist", "https://jobs.ashbyhq.com/iceye/6f4c8c5f-a335-4828-8826-e93e02700b34", "Espoo", "2026-10-23T09:51:55Z", "maybe", null, null),
  j("ashby:elevenlabs:750a8325-7ce1-45ea-b0b1-61dab78a456e", "ElevenLabs", "IT Support Engineer", "https://jobs.ashbyhq.com/elevenlabs/750a8325-7ce1-45ea-b0b1-61dab78a456e", "New York", "2026-10-23T09:32:46Z", "maybe", null, null),
  j("lever:Sprinto:99f385d5-5bc0-49b5-8f63-aea62f423c89", "Sprinto", "Senior Content Marketer", "https://jobs.lever.co/Sprinto/99f385d5-5bc0-49b5-8f63-aea62f423c89", "Bengaluru", "2026-10-23T09:07:41Z", "experienced", 5, 8),
];
