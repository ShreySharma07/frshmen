import type { Metadata } from "next";
import { Admin } from "@/components/admin/Admin";

export const metadata: Metadata = { title: "Admin · Aventra", robots: { index: false } };

export default function AdminPage() {
  return <Admin />;
}
