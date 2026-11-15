"use client";
// The LinkedIn connections block on the profile (docs/decisions.md, 2026-11-15). Separate from the
// profile form: it saves on its own, the moment a file is picked, and it needs a saved profile
// (each row belongs to one).
import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { connectionsSummary, deleteConnections, parseConnections, replaceConnections } from "@/lib/connections";
import { shortDate } from "@/lib/format";

type State = { kind: "loading" } | { kind: "idle" } | { kind: "busy"; what: string } | { kind: "error"; message: string };

export function LinkedInConnections({ userId }: { userId: string }) {
  const [saved, setSaved] = useState<{ count: number; added_at: string | null } | null>(null);
  const [state, setState] = useState<State>({ kind: "loading" });
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    connectionsSummary().then((s) => { setSaved(s); setState({ kind: "idle" }); })
      .catch((e: Error) => setState({ kind: "error", message: e.message }));
  }, []);

  async function pick(f: File | undefined) {
    if (!f) return;
    try {
      setState({ kind: "busy", what: "Reading the file…" });
      const people = parseConnections(await f.text());
      if (!people.length) throw new Error("No connections in that file.");
      setState({ kind: "busy", what: `Saving ${people.length.toLocaleString("en-IN")} connections…` });
      await replaceConnections(userId, people);
      setSaved(await connectionsSummary());
      setState({ kind: "idle" });
    } catch (e) {
      setState({ kind: "error", message: (e as Error).message });
    }
  }

  async function remove() {
    if (!confirm("Delete your LinkedIn connections from Aventra?")) return;
    try {
      setState({ kind: "busy", what: "Deleting…" });
      await deleteConnections(userId);
      setSaved({ count: 0, added_at: null });
      setState({ kind: "idle" });
    } catch (e) {
      setState({ kind: "error", message: (e as Error).message });
    }
  }

  const busy = state.kind === "busy" || state.kind === "loading";
  const has = (saved?.count ?? 0) > 0;
  return (
    <section aria-labelledby="connections-title" className="mt-12 border-t border-line pt-8">
      <h2 id="connections-title" className="text-base font-medium">LinkedIn connections</h2>
      <p className="mt-1 text-meta text-muted">
        The agent uses them to answer &ldquo;who do I know at Razorpay?&rdquo; and writes the note; you send it yourself.
        Names, companies and titles are kept, only for you. Email addresses in the file are skipped.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3 rounded-md border border-dashed border-line p-3">
        <button type="button" onClick={() => fileInput.current?.click()} disabled={busy} aria-busy={state.kind === "busy"}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-line bg-canvas px-3 text-meta font-medium shadow-raised transition-colors duration-quick hover:bg-surface disabled:opacity-60">
          {state.kind === "busy" && <Loader2 aria-hidden className="size-4 animate-spin" />}
          {has ? "Replace Connections.csv" : "Upload Connections.csv"}
        </button>
        <input ref={fileInput} type="file" accept=".csv,text/csv" className="sr-only" tabIndex={-1} aria-label="LinkedIn Connections.csv"
          onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        <span aria-live="polite" className="min-w-0 text-meta text-muted">
          {state.kind === "busy" ? state.what
            : state.kind === "loading" ? ""
            : has ? <><span className="font-mono text-ink">{saved!.count.toLocaleString("en-IN")}</span> saved{saved!.added_at && ` on ${shortDate(saved!.added_at)}`} · <button type="button" onClick={remove} className="font-medium text-accent-text underline">delete</button></>
            : "None yet."}
        </span>
      </div>
      {state.kind === "error" && <p role="alert" className="mt-2 text-meta text-card-fail">Couldn&apos;t save: {state.message}</p>}
      <details className="mt-3 text-meta text-muted">
        <summary className="cursor-pointer font-medium text-ink">How to get the file from LinkedIn</summary>
        <ol className="mt-2 list-decimal space-y-1 pl-5">
          <li>On LinkedIn, open Settings, then Data privacy, then &ldquo;Get a copy of your data&rdquo;.</li>
          <li>Pick &ldquo;Want something in particular?&rdquo;, tick only Connections, and request the archive.</li>
          <li>LinkedIn emails a link, usually within 10 minutes. Download it and upload Connections.csv here.</li>
        </ol>
      </details>
    </section>
  );
}
