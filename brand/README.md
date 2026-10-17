# Kario brand files

| File | Use |
|---|---|
| `kario-wordmark.svg` | The logo in the header. One path with `fill="currentColor"`, so it takes the text colour (ink on white, white on dark). |
| `kario-mark.svg` | A square "k" for the favicon, the app icon and social avatars. |
| `logo-preview.png` (in `docs/wireframes/`) | Both at several sizes, on light and dark. |

The wordmark is "kario" set in **Instrument Serif** (SIL Open Font License, which allows use in
a logo) and turned into outlines. The site never loads the serif font: that keeps it at two
font families (Geist and Geist Mono), as `CLAUDE.md` requires, and saves a font download.

To regenerate the files (needs `pip install fonttools brotli` and Instrument Serif Regular as a
`.ttf` or `.woff2`):

    python brand/make_logo.py path/to/InstrumentSerif-Regular.woff2 brand
