# Kario site (Next.js)

The new web front end, replacing the Vite app in `web/` once the job list is ported (M4.6).

    npm install
    npm run dev      # http://localhost:3000
    npm run build    # static export into out/, served by the API Worker

It is a static export (`output: "export"` in `next.config.ts`): no Node server runs in
production. Data comes from the FastAPI Worker under `/api` (see `docs/decisions.md`).

## Design tokens

Every colour, text size, radius, shadow and motion value lives in `src/app/globals.css`
(CSS variables plus Tailwind's `@theme`, so `bg-canvas`, `text-ink`, `text-title`, `rounded-lg`
and `duration-quick` work as classes). `src/design/tokens.ts` mirrors them for the future mobile
app; `npm run check:tokens` fails if the two disagree. `/design` shows them all, in light and dark.
