"""Cloudflare Worker entrypoint. Only /api/* reaches Python (see wrangler.jsonc);
everything else is the React build, served directly from Workers Static Assets."""

from workers import asgi

from jobs_api import create_app

app = create_app()
Default = asgi.entrypoint(app)
