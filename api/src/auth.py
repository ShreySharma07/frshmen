"""Who is asking: the Supabase access token the site sends, checked by Supabase itself.

Asking Supabase's /auth/v1/user is one small request and needs no signing keys or crypto in
the Worker. Signed-in endpoints (the fit check) depend on `current_user`. Configured by the
Worker vars SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY (set at deploy, .github/workflows/deploy.yml);
tests set app.state.auth instead.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request

# token -> the user's id, or None when Supabase doesn't accept it.
Verify = Callable[[str], Awaitable[str | None]]
Get = Callable[[str, dict[str, str]], Awaitable[tuple[int, Any]]]


def verifier(url: str, key: str, get: Get) -> Verify:
    async def verify(token: str) -> str | None:
        status, data = await get(f"{url.rstrip('/')}/auth/v1/user", {"apikey": key, "Authorization": f"Bearer {token}"})
        uid = data.get("id") if status == 200 and isinstance(data, dict) else None
        return str(uid) if uid else None
    return verify


def auth_config(request: Request) -> Verify | None:
    override = getattr(request.app.state, "auth", None)
    if override:
        return override
    env = request.scope.get("env")
    url = str(getattr(env, "SUPABASE_URL", "") or "") if env is not None else ""
    key = str(getattr(env, "SUPABASE_PUBLISHABLE_KEY", "") or "") if env is not None else ""
    return verifier(url, key, worker_get) if url and key else None


async def current_user(request: Request) -> str:
    verify = auth_config(request)
    if verify is None:
        raise HTTPException(status_code=503, detail="sign-in is not set up on the server")
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    uid = await verify(token) if token else None
    if not uid:
        raise HTTPException(status_code=401, detail="sign in again")
    return uid


async def worker_get(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    """The Worker's outbound request. pyodide.http exists only inside the Workers runtime."""
    from pyodide.http import pyfetch  # type: ignore[import-not-found]

    resp = await pyfetch(url, method="GET", headers=headers)
    try:
        data = await resp.json()
    except Exception:
        data = None
    return resp.status, data
