// The app's sections, in sidebar order. Applications, Insights and Agent are the signed-in
// person's own pages, so they show only once signed in.
export const SECTIONS = [
  { href: "/", label: "Jobs", signedIn: false },
  { href: "/applications", label: "Applications", signedIn: true },
  { href: "/insights", label: "Insights", signedIn: true },
  { href: "/agent", label: "Agent", signedIn: true },
] as const;

export const isCurrent = (href: string, path: string) => (href === "/" ? path === "/" : path.startsWith(href));
