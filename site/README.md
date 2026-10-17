# Kario site (Next.js)

The new web front end, replacing the Vite app in `web/` once the job list is ported (M4.6).

    npm install
    npm run dev      # http://localhost:3000
    npm run build    # static export into out/, served by the API Worker

It is a static export (`output: "export"` in `next.config.ts`): no Node server runs in
production. Data comes from the FastAPI Worker under `/api` (see `docs/decisions.md`).
