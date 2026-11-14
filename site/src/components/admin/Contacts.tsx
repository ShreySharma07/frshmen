"use client";
// The HR and YC founder lists (docs/decisions.md, 2026-11-13, C1/C2): uploaded here as CSV,
// straight into a private table the browser can't read. Preview first (nothing saved), then save.
// The page shows counts per upload, never the people; removal is by email or by whole upload.
import { useCallback, useEffect, useState } from "react";
import { contactsSummary, deleteContacts, importContacts, type ContactKind, type ContactsSummary, type ImportReport } from "@/lib/admin";

const MAX_BYTES = 2_000_000; // the API's limit
const KIND: Record<ContactKind, string> = { hr: "HR and recruiters", founder: "YC founders" };
const n = (x: number) => x.toLocaleString("en-IN");

export function Contacts({ Card }: { Card: React.ComponentType<{ title: string; className?: string; children: React.ReactNode }> }) {
  const [summary, setSummary] = useState<ContactsSummary | null>(null);
  const [kind, setKind] = useState<ContactKind>("hr");
  const [source, setSource] = useState("");
  const [file, setFile] = useState<{ name: string; text: string } | null>(null);
  const [report, setReport] = useState<{ saved: boolean; r: ImportReport } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);
  const [removeEmail, setRemoveEmail] = useState("");
  const refresh = useCallback(() => { contactsSummary().then(setSummary).catch(() => {}); }, []);
  useEffect(refresh, [refresh]);

  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    setReport(null);
    setMessage(null);
    if (!f) return setFile(null);
    if (f.size > MAX_BYTES) { setFile(null); return setMessage({ error: true, text: "That file is over 2 MB. Split it into smaller files." }); }
    setFile({ name: f.name, text: await f.text() });
    if (!source) setSource(f.name.replace(/\.csv$/i, ""));
  };

  const run = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    try {
      const r = await importContacts({ kind, source: source.trim(), csv: file.text, dry_run: dryRun });
      setReport({ saved: !dryRun, r });
      if (!dryRun) {
        setMessage({ error: false, text: `Saved: ${n(r.added)} added, ${n(r.updated)} updated.` });
        setFile(null);
        refresh();
      }
    } catch (err) {
      setMessage({ error: true, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (body: { email: string } | { source: string }, what: string) => {
    if (!confirm(`Delete ${what}? This can't be undone.`)) return;
    try {
      const { deleted } = await deleteContacts(body);
      setMessage({ error: false, text: `Deleted ${n(deleted)} ${deleted === 1 ? "contact" : "contacts"}.` });
      setRemoveEmail("");
      refresh();
    } catch (err) {
      setMessage({ error: true, text: (err as Error).message });
    }
  };

  const input = "mt-1 w-full rounded-md border border-line bg-canvas px-3 py-2 text-body outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent/40";
  const button = "rounded-md px-4 py-2 text-body font-medium transition-transform duration-quick active:scale-[0.98] disabled:opacity-50";

  return (
    <Card title="Contact lists" className="mt-4">
      <p className="mb-4 max-w-[70ch] text-meta text-muted">
        For the agent only. Users never see phone numbers, and see an email only inside a draft the agent writes, a few a day, each one logged.
        A CSV needs a name and a company column; email, title, phone, LinkedIn, city, YC batch, website and notes are read when present.
      </p>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="grid content-start gap-3">
          <fieldset className="text-meta font-medium">
            <legend>Which list</legend>
            <div className="mt-1 flex gap-2">
              {(Object.keys(KIND) as ContactKind[]).map((k) => (
                <label key={k} className={`cursor-pointer rounded-full border px-3 py-1 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent/40 ${kind === k ? "border-ink bg-ink text-canvas" : "border-line"}`}>
                  <input type="radio" name="kind" value={k} checked={kind === k} onChange={() => { setKind(k); setReport(null); }} className="sr-only" />{KIND[k]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="text-meta font-medium">Where the list came from <span className="font-normal text-muted">(kept on every row)</span>
            <input required maxLength={200} value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. Campus placement cell, Nov 2026" className={input} />
          </label>
          <label className="text-meta font-medium">CSV file
            <input type="file" accept=".csv,text/csv" onChange={pick} className={`${input} file:mr-3 file:rounded file:border-0 file:bg-surface file:px-2 file:py-1`} />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={!file || !source.trim() || busy} onClick={() => run(true)} className={`${button} border border-ink`}>Preview</button>
            <button type="button" disabled={!file || !source.trim() || busy || !report || report.saved || report.r.valid === 0} onClick={() => run(false)}
              className={`${button} bg-ink text-canvas`}>Save {report && !report.saved ? n(report.r.valid) : ""} contacts</button>
          </div>
          {message && <p role="status" className={`text-meta ${message.error ? "text-card-fail" : "text-card-pass"}`}>{message.text}</p>}
        </div>
        <div aria-live="polite">{report && <Report r={report.r} />}</div>
      </div>

      <h3 className="mt-6 mb-2 text-meta font-medium uppercase tracking-wide text-muted">Saved lists</h3>
      {!summary ? <p className="text-body text-muted">Loading…</p> : !summary.lists.length ? <p className="text-body text-muted">None yet.</p> : (
        <>
          <ul className="grid">
            {summary.lists.map((l) => (
              <li key={`${l.kind}:${l.source}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 border-t border-line py-2 text-body sm:grid-cols-[8rem_minmax(0,1fr)_auto_auto]">
                <span className="text-meta text-muted max-sm:hidden">{KIND[l.kind]}</span>
                <span className="truncate font-medium max-sm:row-start-1">{l.source}</span>
                <span className="font-mono text-meta max-sm:col-span-2 max-sm:row-start-2">
                  <span className="font-sans text-muted sm:hidden">{KIND[l.kind]} · </span>{n(l.n)} · {n(l.with_email)} emails · {n(l.with_phone)} phones
                </span>
                <button type="button" onClick={() => remove({ source: l.source }, `all ${n(l.n)} contacts from "${l.source}"`)}
                  className="text-meta font-medium text-card-fail underline-offset-2 hover:underline max-sm:col-start-2 max-sm:row-start-1">Delete list</button>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-meta text-muted">{n(summary.total)} contacts · {n(summary.reveals_7d)} emails shown to users in the last 7 days</p>
        </>
      )}
      <form onSubmit={(e) => { e.preventDefault(); remove({ email: removeEmail.trim() }, removeEmail.trim()); }} className="mt-4 flex flex-wrap items-end gap-2">
        <label className="min-w-[16rem] flex-1 text-meta font-medium">Remove a person <span className="font-normal text-muted">(someone asked to be taken off)</span>
          <input type="email" required value={removeEmail} onChange={(e) => setRemoveEmail(e.target.value)} placeholder="their email" className={input} />
        </label>
        <button type="submit" className={`${button} border border-ink`}>Remove</button>
      </form>
    </Card>
  );
}

function Report({ r }: { r: ImportReport }) {
  return (
    <div className="rounded-md border border-line p-3 text-meta">
      <p className="text-body"><span className="font-medium">{r.valid}</span> rows ready{r.error_count > 0 && <>, <span className="font-medium text-card-fail">{r.error_count}</span> refused</>}.</p>
      {r.sample.length > 0 && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full">
            <thead><tr className="text-left text-muted"><th className="py-1 pr-3 font-medium">Name</th><th className="pr-3 font-medium">Company</th><th className="pr-3 font-medium">Title</th><th className="font-medium">Email</th></tr></thead>
            <tbody>{r.sample.map((s, i) => (
              <tr key={i} className="border-t border-line"><td className="py-1 pr-3">{s.name}</td><td className="pr-3">{s.company}</td><td className="pr-3">{s.title ?? "—"}</td><td>{s.email ?? "—"}</td></tr>
            ))}</tbody>
          </table>
          <p className="mt-1 text-muted">The first {r.sample.length} rows, to check the columns were read right.</p>
        </div>
      )}
      {r.errors.length > 0 && (
        <ul className="mt-2 grid gap-0.5">
          {r.errors.map((e) => <li key={e.row}><span className="font-mono">Row {e.row}</span> <span className="text-muted">{e.reason}</span></li>)}
          {r.error_count > r.errors.length && <li className="text-muted">…and {r.error_count - r.errors.length} more</li>}
        </ul>
      )}
    </div>
  );
}
