// The app's frame (docs/decisions.md, 2026-11-11 layout): a sidebar on wide screens, a tab bar on
// phones, and the search bar at the foot of every page. A layout, so it stays mounted while pages
// change underneath and the sidebar's marker can slide from one section to the next.
import { AppChrome } from "@/components/shell/AppChrome";
import { Wordmark } from "@/components/Wordmark";

export default function AppLayout({ children }: LayoutProps<"/">) {
  // The wordmark is drawn here, on the server, so its SVG paths stay out of the browser bundle.
  return <AppChrome logo={<Wordmark className="h-[22px] w-auto text-ink" />}>{children}</AppChrome>;
}
