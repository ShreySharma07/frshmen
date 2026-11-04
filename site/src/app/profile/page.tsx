import type { Metadata } from "next";
import { Dashboard } from "@/components/account/Dashboard";

// Where sign-in lands. Unlinked from the landing page until launch, like /login.
export const metadata: Metadata = { title: "Your profile · Aventra", robots: { index: false } };

export default function ProfilePage() {
  return <Dashboard />;
}
