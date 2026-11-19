// How the site words our API's error replies (src/lib/apiError.ts). Run: npm test.
import assert from "node:assert/strict";
import { test } from "node:test";
import { apiErrorMessage } from "../src/lib/apiError.ts";

test("an unexpected error shows the generic message and its ref id", () => {
  assert.equal(apiErrorMessage({ error: "Something went wrong", id: "a1b2c3d4" }, 500), "Something went wrong (ref a1b2c3d4)");
});

test("an id that isn't the server's exact shape is never shown", () => {
  for (const id of ["A1B2C3D4", "a1b2c3d4e5", "a1b2", "<img src=x>", "../admin", 12345678, null]) {
    assert.equal(apiErrorMessage({ error: "Something went wrong", id }, 500), "Something went wrong");
  }
});

test("FastAPI's detail wins, as a string or an object with a message", () => {
  assert.equal(apiErrorMessage({ detail: "Job not found" }, 404), "Job not found");
  assert.equal(apiErrorMessage({ detail: { message: "Out of checks today", frees_at: "x" } }, 429), "Out of checks today");
});

test("anything else falls back to the status line", () => {
  assert.equal(apiErrorMessage(null, 502, "Bad Gateway"), "502 Bad Gateway");
  assert.equal(apiErrorMessage({ detail: [{ loc: ["query"], msg: "bad" }] }, 422), "422");
  assert.equal(apiErrorMessage("oops", 500), "500");
});
