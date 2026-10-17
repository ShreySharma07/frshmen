// Static shell, printed at build time; JobWorkspace fills in live jobs in the browser.
import { JobWorkspace } from "@/components/JobWorkspace";

export default function Home() {
  return <JobWorkspace />;
}
