"""Run the API and the built page locally against a Postgres database.

  SUPABASE_DB_URL=postgresql://... scripts/apply_pg_migrations.sh
  python scripts/fetch_jobs.py && SUPABASE_DB_URL=... python scripts/publish_pg.py
  python scripts/dev_api.py --dsn postgresql://...   # http://127.0.0.1:8000 (or `npm run dev` in web/)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api" / "src"))

import uvicorn  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from jobs_api import create_app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", default=os.environ.get("SUPABASE_DB_URL"), help="defaults to $SUPABASE_DB_URL")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app = create_app()
    if not args.dsn:
        parser.error("pass --dsn or set SUPABASE_DB_URL")
    app.state.dsn = args.dsn
    dist = ROOT / "web" / "dist"
    if dist.exists():
        # Mirrors the Worker: /api/* is Python, everything else is the React build (SPA fallback).
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> FileResponse:
            file = dist / path
            return FileResponse(file if path and file.is_file() else dist / "index.html")

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
