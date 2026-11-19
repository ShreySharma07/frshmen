// Turns an error reply from our API (api/src/jobs_api.py) into the line the person sees.
// FastAPI's own errors carry `detail` (a string, or an object with `message`); unexpected ones
// carry a generic `error` and a random `id` that matches the server's log entry
// (docs/decisions.md, 2026-11-19). The id is shown so a screenshot can be matched to the logs;
// it is random, looks nothing up, and is shown only if it has the exact shape the server sends.

const ERROR_ID = /^[0-9a-f]{8}$/;

export function apiErrorMessage(body: unknown, status: number, statusText = ""): string {
  const b = (body && typeof body === "object" ? body : {}) as Record<string, unknown>;
  const detail = b.detail as { message?: unknown } | string | undefined;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  if (typeof b.error === "string") {
    return typeof b.id === "string" && ERROR_ID.test(b.id) ? `${b.error} (ref ${b.id})` : b.error;
  }
  return `${status} ${statusText}`.trim();
}
