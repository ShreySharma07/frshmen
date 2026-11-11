// The landing page, built here until every feature it describes works; then it replaces / and the
// job list moves to /jobs (docs/decisions.md 2026-10-19). Unlinked and kept out of search.
import type { Metadata } from "next";
import { Landing } from "@/components/landing/Landing";

export const metadata: Metadata = {
  title: "Aventra: an agent that gets you your next job",
  description: "Aventra reads every opening to the line that decides who it's for, checks your fit, finds people to ask for a referral and prepares each application with you.",
  robots: { index: false },
};

export default function Preview() {
  return (
    <Landing />
  );
}
