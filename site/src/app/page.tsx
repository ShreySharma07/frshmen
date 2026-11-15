// The landing page, at / since launch (docs/decisions.md 2026-10-19 and 2026-11-15): every
// feature it describes now works. The job list moved to /jobs.
import type { Metadata } from "next";
import { Landing } from "@/components/landing/Landing";
import { STORAGE_KEY } from "@/lib/session";

export const metadata: Metadata = {
  title: "Aventra: an agent that gets you your next job",
  description: "Aventra reads every opening to the line that decides who it's for, checks your fit, finds people to ask for a referral and prepares each application with you.",
};

// Runs while the page is still loading, before the landing paints, so nobody sees it flash:
// - old links to the job list (/?level=fresher, shared before the move) go on to /jobs with
//   their filters;
// - a signed-in person goes straight to /jobs: the landing is the pitch, and they are past it
//   (the signed-in start screen of 2026-10-19 is not built yet).
const toJobs = `try{if(location.search||(${JSON.stringify(STORAGE_KEY)}&&localStorage.getItem(${JSON.stringify(STORAGE_KEY)})))location.replace("/jobs"+location.search+location.hash)}catch(e){}`;

export default function Home() {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: toJobs }} />
      <Landing />
    </>
  );
}
