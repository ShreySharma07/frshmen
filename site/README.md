# Kario site (Next.js)

Kario's web front end (M4.6), live since 2026-10-17.

    npm install
    python ../scripts/dev_api.py --dsn postgresql://...   # the API on :8000, in another terminal
    npm run dev      # http://localhost:3000; /api is forwarded to :8000
    npm run build    # static export into out/, served by the API Worker

It is a static export (`output: "export"` in `next.config.ts`): no Node server runs in
production. The page is printed at build time, and the browser fetches live jobs from the
FastAPI Worker under `/api` when it opens (see `docs/decisions.md`).

## Design tokens

Every colour, text size, radius, shadow and motion value lives in `src/app/globals.css`
(CSS variables plus Tailwind's `@theme`, so `bg-canvas`, `text-ink`, `text-title`, `rounded-lg`
and `duration-quick` work as classes). `src/design/tokens.ts` mirrors them for the future mobile
app; `npm run check:tokens` fails if the two disagree. `/design` shows them all, in light and dark.
