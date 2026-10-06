"""Run the API and the built page locally against a SQLite file.

  python scripts/fetch_jobs.py && python scripts/publish_d1.py --sqlite data/local.db
  python scripts/dev_api.py            # http://127.0.0.1:8000  (or `npm run dev` in web/ for hot reload)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api" / "src"))

import uvicorn  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from jobs_api import create_app  # noqa: E402
from storage import SqliteDatabase  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "local.db")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app = create_app()
    app.state.db = SqliteDatabase(str(args.db))
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
