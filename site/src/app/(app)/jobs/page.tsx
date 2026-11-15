// The job list, at /jobs since launch (docs/decisions.md 2026-10-19; it was / before). Static
// shell, printed at build time; JobWorkspace fills in live jobs in the browser.
import type { Metadata } from "next";
import { JobWorkspace } from "@/components/JobWorkspace";

export const metadata: Metadata = { title: "Open jobs · Aventra" };

export default function Jobs() {
  return <JobWorkspace />;
}
