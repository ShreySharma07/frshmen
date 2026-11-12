import type { Metadata } from "next";
import { Applications } from "@/components/applications/Applications";

export const metadata: Metadata = { title: "Applications · Aventra", robots: { index: false } };

export default function ApplicationsPage() {
  return <Applications />;
}
