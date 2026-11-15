import type { Metadata } from "next";
import { LoginPanel } from "@/components/account/LoginPanel";

// Linked from the sidebar and the landing page (docs/decisions.md, Part B).
export const metadata: Metadata = { title: "Sign in · Aventra", robots: { index: false } };

export default function Login() {
  return <LoginPanel />;
}
