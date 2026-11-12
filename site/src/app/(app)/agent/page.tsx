import type { Metadata } from "next";
import { Agent } from "@/components/agent/Agent";

export const metadata: Metadata = { title: "Agent · Aventra", robots: { index: false } };

export default function AgentPage() {
  return <Agent />;
}
