// Aventra design tokens for code that can't read CSS, such as the future React Native app.
// Mirrors the CSS variables in src/app/globals.css; `npm run check:tokens` fails if they differ.

export const color = {
  light: {
    canvas: "#f2eee4",
    surface: "#e9e3d6",
    line: "#d9d3c5",
    ink: "#121110",
    muted: "#625d53",
    faint: "#a39d8f",
    accent: "#ffb21a",
    accentHover: "#f0a400",
    onAccent: "#121110",
    accentText: "#1f4fd8",
    mark: "#ffb21a",
    selected: "#fbf9f4",
    card: "#fbf9f4",
    cardText: "#121110",
    cardMuted: "#625d53",
    cardAccent: "#121110",
    cardPass: "#276b43",
    cardFail: "#b5381f",
    code: "#e9e3d6",
  },
  dark: {
    canvas: "#14130f",
    surface: "#1c1b17",
    line: "#34312a",
    ink: "#ece7db",
    muted: "#a39d90",
    faint: "#6f6a5e",
    accent: "#ffb21a",
    accentHover: "#ffc24d",
    onAccent: "#121110",
    accentText: "#ffc24d",
    mark: "#4a3a12",
    selected: "#1f1e1a",
    card: "#1c1b17",
    cardText: "#ece7db",
    cardMuted: "#a39d90",
    cardAccent: "#ffb21a",
    cardPass: "#7fd49b",
    cardFail: "#f08a75",
    code: "#26241f",
  },
  /** Landing chapters ("Ink and Marigold"), `.lp-dark` and `.lp-light` in globals.css. */
  landingDark: {
    bg: "#14130f",
    surface: "#1c1b17",
    raised: "#26241f",
    line: "#34312a",
    ink: "#ece7db",
    muted: "#a39d90",
    accent: "#ffb21a",
    onAccent: "#121110",
    accentText: "#ffc24d",
    add: "#7fd49b",
    addBg: "#1b2a1f",
    del: "#f08a75",
    delBg: "#33201b",
    mark: "#4a3a12",
    windowBar: "#1f1e1a",
    windowLine: "#34312a",
    ok: "#3fa66a",
    warn: "#e0a100",
    warnText: "#ffc24d",
    term: "#0c0b09",
    termInk: "#ece7db",
    termMuted: "#a39d90",
    termOk: "#7fd49b",
  },
  landingLight: {
    bg: "#f2eee4",
    surface: "#e9e3d6",
    raised: "#fbf9f4",
    line: "#d9d3c5",
    ink: "#121110",
    muted: "#625d53",
    accent: "#ffb21a",
    onAccent: "#121110",
    accentText: "#1f4fd8",
    add: "#276b43",
    addBg: "#e4efe4",
    del: "#b5381f",
    delBg: "#f6e2dc",
    mark: "#ffd27a",
    windowBar: "#f6f3ec",
    windowLine: "#e3ddd0",
    ok: "#3fa66a",
    warn: "#e0a100",
    warnText: "#8a5300",
    term: "#0c0b09",
    termInk: "#ece7db",
    termMuted: "#a39d90",
    termOk: "#7fd49b",
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
  headline: { size: 32, lineHeight: 1.12 },
  hero: { size: 44, lineHeight: 1.05 },
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

export const font = { sans: "Instrument Sans", mono: "Geist Mono", display: "Instrument Serif", text: "Instrument Sans" } as const;
