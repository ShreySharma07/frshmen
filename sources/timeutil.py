from __future__ import annotations

from datetime import datetime, timezone


def to_utc_iso(value: str | int | float | None) -> str | None:
    """Normalise ATS timestamps (ISO strings with offsets, or epoch milliseconds) to ISO UTC."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError):
        return None
