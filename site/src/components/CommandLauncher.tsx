"use client";
// Opens the command palette on Cmd+K / Ctrl+K from any page, and shows a small hint button on wide
// screens. The palette itself loads only when first opened.
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

const CommandPalette = dynamic(() => import("./CommandPalette").then((m) => m.CommandPalette), { ssr: false });

export function CommandLauncher() {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-label="Open the command palette"
        className="hidden h-9 shrink-0 items-center rounded-md border border-line px-2 font-mono text-caption text-muted transition-colors duration-quick hover:bg-surface hover:text-ink lg:inline-flex">
        ⌘K
      </button>
      {open && <CommandPalette onClose={close} />}
    </>
  );
}
