"use client";
// What opens beside the agent chat: an email draft, a LinkedIn message, or the resume editor.
// Wide screens: a document beside the conversation. Phones: a sheet over the page.
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

// Motion tokens (globals.css: --ease-out-soft; 300-500 ms for layout moves).
export const EASE = [0.2, 0.8, 0.2, 1] as const;
const WIDE = "(min-width: 64rem)";
const subscribeWide = (cb: () => void) => { const m = matchMedia(WIDE); m.addEventListener("change", cb); return () => m.removeEventListener("change", cb); };
export const useWide = () => useSyncExternalStore(subscribeWide, () => matchMedia(WIDE).matches, () => true);

export function SidePanel({ labelledBy, onClose, children }: { labelledBy: string; onClose: () => void; children: ReactNode }) {
  const wide = useWide();
  const still = useReducedMotion();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);
  // Wide: slides in from the right edge and back out, like a document opening beside the chat.
  // Phones: rises as a sheet and drops away. A plain fade when motion is reduced.
  const motionProps = {
    initial: still ? { opacity: 0 } : wide ? { opacity: 0, x: 32 } : { opacity: 0, y: 40 },
    animate: { opacity: 1, x: 0, y: 0 },
    exit: still ? { opacity: 0 } : wide ? { opacity: 0, x: 32 } : { opacity: 0, y: 40 },
    transition: { duration: still ? 0.12 : 0.3, ease: EASE },
  };
  const panel = (
    // The wide panel stops above the app's command bar (about 6rem at the bottom of the column).
    <motion.aside {...motionProps} aria-labelledby={labelledBy}
      className={wide ? "sticky top-[4.5rem] flex max-h-[calc(100svh-6rem)] flex-col self-start rounded-lg border border-card-line bg-card p-5"
        : "fixed inset-0 z-50 flex flex-col bg-card p-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-[max(1.25rem,env(safe-area-inset-bottom))]"}>
      {children}
    </motion.aside>
  );
  return wide ? panel : createPortal(panel, document.body);
}
