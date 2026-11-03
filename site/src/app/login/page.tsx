import type { Metadata } from "next";
import { LoginPanel } from "@/components/account/LoginPanel";

// Unlinked until launch, like /preview (docs/decisions.md, Part B).
export const metadata: Metadata = { title: "Sign in · Kario", robots: { index: false } };

export default function Login() {
  return <LoginPanel />;
}
