import type { Metadata } from "next";
import { ProfileForm } from "@/components/account/ProfileForm";

export const metadata: Metadata = { title: "Your details · Aventra", robots: { index: false } };

export default function ProfilePage() {
  return <ProfileForm />;
}
