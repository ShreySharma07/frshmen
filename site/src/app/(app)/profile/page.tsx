import type { Metadata } from "next";
import { ToApplications } from "@/components/applications/ToApplications";

// Where sign-in lands (the magic link points here), and the old address of the board. The
// tracker now lives at /applications; this page finishes the sign-in and goes there.
export const metadata: Metadata = { title: "Aventra", robots: { index: false } };

export default function ProfilePage() {
  return <ToApplications />;
}
