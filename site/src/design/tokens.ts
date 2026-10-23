// Kario design tokens for code that can't read CSS, such as the future React Native app.
// Mirrors the CSS variables in src/app/globals.css; `npm run check:tokens` fails if they differ.

export const color = {
  light: {
    canvas: "#ffffff",
    surface: "#fafafb",
    line: "#e7e7ea",
    ink: "#0a0a12",
    muted: "#6b6b76",
    faint: "#a1a1aa",
    accent: "#5851ec",
    accentHover: "#4a42d9",
    onAccent: "#ffffff",
    selected: "#f6f5ff",
    card: "#0a0a12",
    cardText: "#ffffff",
    cardMuted: "#d4d4d8",
    cardAccent: "#a5a0ff",
    code: "#f4f4f5",
  },
  dark: {
    canvas: "#0b0b10",
    surface: "#121218",
    line: "#24242c",
    ink: "#ededf2",
    muted: "#9b9ba6",
    faint: "#6e6e78",
    accent: "#8f8aff",
    accentHover: "#a5a0ff",
    onAccent: "#0b0b10",
    selected: "#17162a",
    card: "#17171f",
    cardText: "#ededf2",
    cardMuted: "#d4d4d8",
    cardAccent: "#a5a0ff",
    code: "#1c1c24",
  },
  /** Landing chapters (midnight navy, warm parchment, Klein cobalt), `.lp-dark` and `.lp-light` in globals.css. */
  landingDark: {
    bg: "#080d1a",
    surface: "#0f172a",
    raised: "#1e293b",
    line: "#273449",
    ink: "#f1f5f9",
    muted: "#94a3b8",
    accent: "#2563eb",
    onAccent: "#ffffff",
    accentText: "#60a5fa",
    add: "#34d399",
    addBg: "#0b2a24",
    del: "#f87171",
    delBg: "#2a1418",
    mark: "#1e3a8a",
    windowBar: "#111a2e",
    windowLine: "#273449",
    ok: "#059669",
    warn: "#d97706",
    warnText: "#fbbf24",
    term: "#080d1a",
    termInk: "#e2e8f0",
    termMuted: "#94a3b8",
    termOk: "#34d399",
  },
  landingLight: {
    bg: "#faf8f5",
    surface: "#efece6",
    raised: "#ffffff",
    line: "#e2ded5",
    ink: "#0f172a",
    muted: "#5b6475",
    accent: "#2563eb",
    onAccent: "#ffffff",
    accentText: "#1d4ed8",
    add: "#047857",
    addBg: "#e6f6f0",
    del: "#9b3b3b",
    delBg: "#fdf0f0",
    mark: "#dbe7ff",
    windowBar: "#faf9f7",
    windowLine: "#e5e7eb",
    ok: "#059669",
    warn: "#d97706",
    warnText: "#b45309",
    term: "#080d1a",
    termInk: "#e2e8f0",
    termMuted: "#94a3b8",
    termOk: "#34d399",
  },
} as const;

/** Font sizes in px with line heights (unitless ratios), matching the --text-* scale. */
export const text = {
  caption: { size: 11, lineHeight: 16 / 11 },
  meta: { size: 12, lineHeight: 16 / 12 },
  body: { size: 13.5, lineHeight: 22 / 13.5 },
  base: { size: 15, lineHeight: 24 / 15 },
  title: { size: 24, lineHeight: 1.2 },
  display: { size: 30, lineHeight: 1 },
} as const;

/** Spacing follows a 4px step: space(4) = 16. */
export const space = (steps: number) => steps * 4;

export const radius = { sm: 4, md: 8, lg: 12 } as const;

/** Durations in ms; easings as cubic-bezier control points. */
export const motion = {
  quick: 150,
  move: 250,
  layout: 400,
  easeOutSoft: [0.2, 0.8, 0.2, 1],
  easeInOutSoft: [0.4, 0, 0.2, 1],
  landing: 800,
  easeOutExpo: [0.16, 1, 0.3, 1],
} as const;

export const font = { sans: "Geist", mono: "Geist Mono" } as const;
