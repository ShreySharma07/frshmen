// The landing page, built here until every feature it describes works; then it replaces / and the
// job list moves to /jobs (docs/decisions.md 2026-10-19). Unlinked and kept out of search.
import type { Metadata } from "next";
import { Bricolage_Grotesque } from "next/font/google";
import { Landing } from "@/components/landing/Landing";

// Loaded here, not in the root layout, so the job list never downloads it.
const bricolage = Bricolage_Grotesque({ variable: "--font-bricolage", subsets: ["latin"], weight: ["600"] });

export const metadata: Metadata = {
  title: "Kario: an agent that gets you your next job",
  description: "Kario finds the jobs that really take freshers, checks your fit, finds people to ask for a referral and prepares each application with you.",
  robots: { index: false },
};

export default function Preview() {
  return (
    <div className={bricolage.variable}>
      <Landing />
    </div>
  );
}
