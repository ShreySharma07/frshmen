import type { Metadata } from "next";
import { Geist_Mono, Instrument_Sans, Instrument_Serif } from "next/font/google";
import "./globals.css";

// Serif for headings and the years, sans for text, mono for data (globals.css, --font-*).
const serif = Instrument_Serif({ variable: "--font-instrument-serif", subsets: ["latin"], weight: "400", style: ["normal", "italic"] });
const sans = Instrument_Sans({ variable: "--font-instrument-sans", subsets: ["latin"] });

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Aventra",
  description: "Jobs that match your years of experience, with the evidence behind every label.",
};

// Runs before first paint: the saved choice, else the device setting. Kept tiny and inline so
// dark-mode visitors never see a white flash. (ThemeToggle uses the same key.)
const THEME_SCRIPT = `try{var t=localStorage.getItem("aventra.theme");if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.dataset.theme=t}catch(e){}`;

// Cloudflare Web Analytics (docs/decisions.md, 2026-11-13): page views with no cookies, read in the
// Cloudflare dashboard. The token only names the site, but like every key it comes from the build
// environment (site/.env.example), not the source. Unset, no beacon. Deferred, ~6 KB, so it never
// holds up the job list's first paint.
const CF_TOKEN = process.env.NEXT_PUBLIC_CF_BEACON_TOKEN ?? "";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: the script above sets data-theme before React loads.
    <html
      lang="en"
      className={`${serif.variable} ${sans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full">
        {children}
        {CF_TOKEN && <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon={JSON.stringify({ token: CF_TOKEN })} />}
      </body>
    </html>
  );
}
