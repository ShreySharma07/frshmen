// Static shell, printed at build time; JobWorkspace fills in live jobs in the browser.
import { JobWorkspace } from "@/components/JobWorkspace";
import { Wordmark } from "@/components/Wordmark";

export default function Home() {
  return <JobWorkspace logo={<Wordmark className="h-[22px] w-auto shrink-0 text-ink" />} />;
}
