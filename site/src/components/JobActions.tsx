"use client";
// Under a job's Apply button: Save it to the tracker, and ask Gemini how well it fits the saved
// resume (5 a day, docs/decisions.md 2026-11-04). Both need sign-in; neither loads supabase-js
// unless a token has to be refreshed.
import { Bookmark, BookmarkCheck } from "lucide-react";
import dynamic from "next/dynamic";
import { IntentLink } from "./IntentLink";
import { useEffect, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { readSession, subscribeSession } from "@/lib/session";
import { checkFit, fitQuota, saveJob, stageOf, STAGES, type Stage, type Verdict } from "@/lib/tracker";

// The tailored resume (and pdf-lib with it) loads only when someone opens it.
const TailorDialog = dynamic(() => import("./TailorDialog").then((m) => m.TailorDialog), { ssr: false });

const NOTICE_KEY = "aventra:gemini-notice"; // set once the person has read the privacy note
const btn = "inline-flex h-10 items-center gap-1.5 rounded-md border border-line px-3.5 text-meta font-medium transition-colors duration-quick hover:bg-surface disabled:opacity-60";

/** `panels` is where the fit check's note and verdict go: below the sticky action bar, so a tall
 *  verdict scrolls with the posting instead of covering it. */
export function JobActions({ jobId, title, company, fitCheck, panels }: {
  jobId: string; title: string; company: string; fitCheck: boolean; panels?: HTMLElement | null;
}) {
  const session = useSyncExternalStore(subscribeSession, readSession, () => null);
  if (!session) {
    return (
      <p className="text-meta text-muted">
        <IntentLink href="/login" className="font-medium text-accent-text underline underline-offset-2">Sign in</IntentLink> to save this job{fitCheck ? " and check your fit" : ""}.
      </p>
    );
  }
  return (
    <>
      <SaveButton userId={session.userId} jobId={jobId} />
      {fitCheck && <FitCheck jobId={jobId} title={title} company={company} panels={panels} />}
    </>
  );
}

function SaveButton({ userId, jobId }: { userId: string; jobId: string }) {
  const [stage, setStage] = useState<Stage | null | "loading">("loading");
  const [problem, setProblem] = useState<"no-profile" | "error" | null>(null);
  useEffect(() => { stageOf(jobId).then(setStage).catch(() => setStage(null)); }, [jobId]);

  async function save() {
    setProblem(null);
    try {
      const r = await saveJob(userId, jobId);
      if (r === "no-profile") setProblem("no-profile"); else setStage("saved");
    } catch { setProblem("error"); }
  }
  const label = STAGES.find((s) => s.v === stage)?.label;
  return (
    <>
      {stage && stage !== "loading" ? (
        <IntentLink href="/profile" className={btn}><BookmarkCheck aria-hidden className="size-4 text-accent-text" />{label} · tracker</IntentLink>
      ) : (
        <button type="button" onClick={save} disabled={stage === "loading"} className={btn}><Bookmark aria-hidden className="size-4" />Save</button>
      )}
      {problem === "no-profile" && <span className="text-meta text-muted">Save your <IntentLink href="/profile/edit" className="font-medium text-accent-text underline">profile</IntentLink> first.</span>}
      {problem === "error" && <span role="alert" className="text-meta text-muted">Couldn&apos;t save. Try again.</span>}
    </>
  );
}

type Fit =
  | { kind: "idle" } | { kind: "notice" } | { kind: "checking" }
  | { kind: "done"; verdict: Verdict } | { kind: "error"; message: React.ReactNode };

function FitCheck({ jobId, title, company, panels }: { jobId: string; title: string; company: string; panels?: HTMLElement | null }) {
  const [left, setLeft] = useState<number | null>(null);
  const [tailorLeft, setTailorLeft] = useState<number | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [state, setState] = useState<Fit>({ kind: "idle" });
  useEffect(() => { fitQuota().then((q) => { setLeft(q.remaining); setTailorLeft(q.tailor?.remaining ?? null); }).catch(() => {}); }, []);

  async function run() {
    try { localStorage.setItem(NOTICE_KEY, "1"); } catch {}
    setState({ kind: "checking" });
    try {
      const v = await checkFit(jobId);
      setLeft(v.remaining);
      setState({ kind: "done", verdict: v });
    } catch (e) {
      const err = e as Error & { status?: number; freesAt?: string };
      const message = err.status === 409 ? <>Add your resume to your <IntentLink href="/profile/edit" className="font-medium text-accent-text underline">profile</IntentLink> first.</>
        : err.status === 429 ? <>All 5 checks used. The next one frees up at {err.freesAt ? new Date(err.freesAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "a later time"}.</>
        : err.status === 401 ? <><IntentLink href="/login" className="font-medium text-accent-text underline">Sign in</IntentLink> again to check your fit.</>
        : `Couldn't check right now (${err.message}).`;
      if (err.status === 429) setLeft(0);
      setState({ kind: "error", message });
    }
  }
  function start() {
    let seen = false;
    try { seen = Boolean(localStorage.getItem(NOTICE_KEY)); } catch {}
    if (seen) run(); else setState({ kind: "notice" });
  }

  return (
    <>
      <button type="button" onClick={start} disabled={state.kind === "checking" || left === 0} className={btn}>
        {state.kind === "checking" ? "Checking with Gemini…" : "Check my fit"}
        {left !== null && state.kind !== "checking" && <span className="font-mono font-normal text-muted">· {left} left today</span>}
      </button>
      {below(panels, <>
      {state.kind === "notice" && (
        <div role="dialog" aria-label="Before your first fit check" className="rounded-lg border border-line bg-surface p-4 text-body">
          <p>Gemini will compare this posting with the resume text saved on your profile.</p>
          <p className="mt-1.5 text-muted">On Gemini&apos;s free tier, Google may use what it&apos;s sent to improve its products. You get 5 checks a day.</p>
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={run} className="h-9 rounded-md bg-accent px-3.5 text-meta font-medium text-on-accent hover:bg-accent-hover">Continue</button>
            <button type="button" onClick={() => setState({ kind: "idle" })} className="h-9 rounded-md px-3 text-meta font-medium text-muted hover:bg-canvas hover:text-ink">Not now</button>
          </div>
        </div>
      )}
      {state.kind === "error" && <p role="alert" className="text-meta text-muted">{state.message}</p>}
      {state.kind === "done" && (
        <VerdictCard v={state.verdict}>
          {/* The next step after a verdict: the resume, reworded toward this job (2 a day). */}
          <button type="button" onClick={() => setTailoring(true)} disabled={tailorLeft === 0} className={btn}>
            Tailor my resume for this job
            {tailorLeft !== null && <span className="font-mono font-normal text-muted">· {tailorLeft} left today</span>}
          </button>
        </VerdictCard>
      )}
      </>)}
      {tailoring && <TailorDialog jobId={jobId} title={title} company={company} onClose={() => setTailoring(false)} onMade={setTailorLeft} />}
    </>
  );
}

/** Renders into the panel slot under the action bar when there is one, else in place. */
function below(slot: HTMLElement | null | undefined, node: React.ReactNode) {
  return slot ? createPortal(node, slot) : node;
}

const TONE = { strong: "Strong fit", partial: "Partial fit", weak: "Weak fit" } as const;

function VerdictCard({ v, children }: { v: Verdict; children?: React.ReactNode }) {
  return (
    <div role="status" className="rounded-lg border border-line p-4 text-body">
      <p className="flex items-baseline gap-2">
        <span className="font-medium">{TONE[v.fit]}</span>
        {v.score !== null && <span className="font-mono text-meta text-muted">{v.score}/100</span>}
      </p>
      {v.experience && <p className="mt-1.5 text-muted">{v.experience}</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <List title="You show" items={v.matched} />
        <List title="Not on your resume" items={v.missing} />
      </div>
      {v.advice && <p className="mt-3">{v.advice}</p>}
      {children && <div className="mt-4">{children}</div>}
      <p className="mt-3 text-caption text-muted">From Gemini, using only this posting and your saved resume. Check it against the posting.</p>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-meta text-muted">{title}</p>
      {items.length ? (
        <ul className="mt-1 list-disc space-y-0.5 pl-4 marker:text-faint">{items.map((x) => <li key={x}>{x}</li>)}</ul>
      ) : <p className="mt-1 text-muted">Nothing listed.</p>}
    </div>
  );
}
