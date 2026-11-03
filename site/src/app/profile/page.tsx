import type { Metadata } from "next";
import { ProfileForm } from "@/components/account/ProfileForm";

export const metadata: Metadata = { title: "Your profile · Kario", robots: { index: false } };

export default function ProfilePage() {
  return <ProfileForm />;
}
