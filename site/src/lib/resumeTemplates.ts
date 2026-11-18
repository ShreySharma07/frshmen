// The four resume templates (docs/decisions.md, 2026-11-17), in Typst, compiled in the browser
// (lib/typst.worker.ts). Every one is a single column of real text, the order a hiring system reads.
// The resume comes in as JSON at /data.json (lib/resumeDoc.ts's ResumeDoc): its words are data, never
// Typst markup, so nothing a person types can change the template. Fonts: IBM Plex Serif and Sans
// (OFL), static files in public/resume/fonts/ (variable fonts render at their lightest weight in Typst).

export type TemplateId = "classic" | "modern" | "compact" | "sidebar";
export interface Template { id: TemplateId; label: string; note: string; fonts: string[]; source: string }

const SERIF = ["IBMPlexSerif-Regular", "IBMPlexSerif-Bold", "IBMPlexSerif-Italic"];
const SANS = ["IBMPlexSans-Regular", "IBMPlexSans-SemiBold", "IBMPlexSans-Bold", "IBMPlexSans-Italic"];

// Shared: read the data, and draw an entry's rows and bullets with a template's own spacing.
const COMMON = `
#let d = json("/data.json")
#let nonempty(s) = s != none and s != ""
#let row(left, right, l-style: x => x, r-style: x => x) = if nonempty(left) or nonempty(right) {
  grid(columns: (1fr, auto), column-gutter: 10pt,
    if nonempty(left) { l-style(left) }, if nonempty(right) { r-style(right) })
}
// One entry: its rows and bullets close together (inner), entries further apart (outer).
#let entry-block(it, inner, outer, title, sub) = block(above: outer, below: 0pt, breakable: true, {
  set block(spacing: inner)
  title(it)
  sub(it)
  if it.bullets.len() > 0 { list(..it.bullets.map(b => [#b])) }
})
#let items(xs, entry, gap) = for it in xs {
  if it.kind == "entry" { entry(it) }
  else if it.kind == "bullet" { block(above: gap, below: 0pt, list([#it.text])) }
  else { block(above: gap, below: 0pt, [#it.text]) }
}
`;

const CLASSIC = `${COMMON}
#set page(paper: d.at("paper", default: "a4"), margin: (x: 1.8cm, y: 1.5cm))
#set text(font: "IBM Plex Serif", size: 10.3pt, lang: "en")
#set par(leading: 0.5em)
#set list(indent: 2pt, body-indent: 6pt, marker: [•])
#align(center, block(below: 12pt)[
  #text(size: 22pt, weight: "bold", d.name)
  #if d.contact.len() > 0 { v(-4pt); text(size: 9.3pt, d.contact.join("  ·  ")) }
])
#set list(spacing: 3pt)
#let entry(it) = entry-block(it, 4pt, 9pt,
  it => row(it.title, it.right, l-style: x => strong(x)),
  it => row(it.sub, it.subRight, l-style: x => emph(x), r-style: x => emph(x)))
#for s in d.sections {
  block(above: 15pt, below: 0pt, sticky: true, {
    text(size: 10pt, weight: "bold", tracking: 0.09em, upper(s.heading))
    v(-6pt)
    line(length: 100%, stroke: 0.6pt)
  })
  items(s.items, entry, 4pt)
}
`;

const MODERN = `${COMMON}
#let accent = rgb("#1d5b79")
#set page(paper: d.at("paper", default: "a4"), margin: (x: 1.9cm, y: 1.6cm))
#set text(font: "IBM Plex Sans", size: 10pt, lang: "en", fill: rgb("#1c1c1e"))
#set par(leading: 0.55em)
#set list(indent: 0pt, body-indent: 7pt, marker: text(fill: accent)[•], spacing: 3.5pt)
#block(below: 14pt)[
  #text(size: 24pt, weight: "semibold", d.name)
  #if d.contact.len() > 0 { v(-6pt); text(size: 9.3pt, fill: rgb("#55575c"), d.contact.join("   |   ")) }
]
#let entry(it) = entry-block(it, 4pt, 11pt,
  it => row(it.title, it.right, l-style: x => text(weight: "semibold", x), r-style: x => text(fill: rgb("#55575c"), x)),
  it => row(it.sub, it.subRight, l-style: x => text(fill: accent, x), r-style: x => text(fill: rgb("#55575c"), x)))
#for s in d.sections {
  block(above: 17pt, below: 0pt, sticky: true,
    text(size: 10.5pt, weight: "semibold", fill: accent, tracking: 0.05em, upper(s.heading)))
  items(s.items, entry, 4pt)
}
`;

const COMPACT = `${COMMON}
#set page(paper: d.at("paper", default: "a4"), margin: (x: 1.3cm, y: 1.1cm))
#set text(font: "IBM Plex Sans", size: 9.2pt, lang: "en")
#set par(leading: 0.42em)
#set list(indent: 0pt, body-indent: 5pt, marker: [•])
#grid(columns: (auto, 1fr), column-gutter: 14pt, align: (left + bottom, right + bottom),
  text(size: 17pt, weight: "bold", d.name),
  text(size: 8.6pt, d.contact.join("  ·  ")))
#v(2pt)
#set list(spacing: 2pt)
// Title and second row share one line to fit more on the page.
#let entry(it) = entry-block(it, 2.5pt, 6pt,
  it => row((it.title, it.sub).filter(nonempty).join(" — "), (it.right, it.subRight).filter(nonempty).join(" · "), l-style: x => strong(x)),
  it => none)
#for s in d.sections {
  block(above: 10pt, below: 0pt, sticky: true, {
    text(size: 9pt, weight: "bold", upper(s.heading))
    v(-5.5pt)
    line(length: 100%, stroke: 0.4pt)
  })
  items(s.items, entry, 2.5pt)
}
`;

const SIDEBAR = `${COMMON}
#set page(paper: d.at("paper", default: "a4"), margin: (x: 1.6cm, y: 1.5cm))
#set text(font: "IBM Plex Sans", size: 9.8pt, lang: "en")
#set par(leading: 0.52em)
#set list(indent: 0pt, body-indent: 6pt, marker: [–], spacing: 3pt)
#let label-w = 3.3cm
#grid(columns: (label-w, 1fr), column-gutter: 14pt, [],
  block(below: 16pt)[
    #text(font: "IBM Plex Serif", size: 22pt, weight: "bold", d.name)
    #if d.contact.len() > 0 { v(-5pt); text(size: 9pt, fill: rgb("#4a4a4f"), d.contact.join("  ·  ")) }
  ])
#let entry(it) = entry-block(it, 3.5pt, 9pt,
  it => row(it.title, it.right, l-style: x => text(weight: "semibold", x), r-style: x => text(fill: rgb("#4a4a4f"), x)),
  it => row(it.sub, it.subRight, l-style: x => emph(x), r-style: x => text(fill: rgb("#4a4a4f"), x)))
#for s in d.sections {
  // Heading first, then the section, in reading order: the label column is only where it sits.
  grid(columns: (label-w, 1fr), column-gutter: 14pt, row-gutter: 0pt,
    align(right, text(font: "IBM Plex Serif", size: 9.5pt, weight: "bold", tracking: 0.04em, upper(s.heading))),
    // The first item sits level with the label: its own space above is dropped here.
    { show: it => block(above: 0pt, it); set block(spacing: 0pt); items(s.items.slice(0, 1), entry, 0pt); set block(spacing: 3pt); items(s.items.slice(1), entry, 3pt) })
  v(11pt)
}
`;

export const TEMPLATES: Template[] = [
  { id: "classic", label: "Classic", note: "Serif, centred name, ruled headings", fonts: SERIF, source: CLASSIC },
  { id: "modern", label: "Modern", note: "Sans, one accent colour", fonts: [...SANS], source: MODERN },
  { id: "compact", label: "Compact", note: "Smaller type, fits more on a page", fonts: ["IBMPlexSans-Regular", "IBMPlexSans-Bold", "IBMPlexSans-Italic"], source: COMPACT },
  { id: "sidebar", label: "Sidebar labels", note: "Section names in a left column", fonts: ["IBMPlexSerif-Bold", ...SANS], source: SIDEBAR },
];

export const fontUrl = (name: string) => `/resume/fonts/${name}.ttf`;
