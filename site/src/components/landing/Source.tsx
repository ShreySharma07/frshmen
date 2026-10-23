"use client";

// Every quoted line can say where it came from (critique 2026-10-23, the micro layer): the quote
// is a link to the posting, and on hover or keyboard focus a small card names the company, the
// role and the board it was read from. The card is drawn at the top of the page (fixed, in a
// portal) so the windows and scenes that clip their content can't cut it off.
import { ArrowUpRight } from "lucide-react";
import { useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function Source({ company, title, href, children, className = "" }: {
  company: string;
  title: string;
  href?: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  const anchor = useRef<HTMLAnchorElement>(null);
  const [at, setAt] = useState<{ x: number; y: number; below: boolean } | null>(null);
  if (!href) return <>{children}</>;

  const show = () => {
    const r = anchor.current?.getBoundingClientRect();
    if (!r) return;
    const below = r.top < 140; // no room above: open underneath
    setAt({ x: Math.min(Math.max(r.left, 16), window.innerWidth - 336), y: below ? r.bottom + 8 : r.top - 8, below });
  };
  const hide = () => setAt(null);
  const host = new URL(href).host.replace(/^www\./, "");

  return (
    <>
      <a
        ref={anchor}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-describedby={at ? id : undefined}
        onPointerEnter={show}
        onPointerLeave={hide}
        onFocus={show}
        onBlur={hide}
        className={`source-link ${className}`}
      >
        {children}
      </a>
      {at && createPortal(
        <span
          id={id}
          role="tooltip"
          className="source-card lp-light pointer-events-none fixed z-[60] grid w-[20rem] gap-1 rounded-xl border border-lp-line bg-lp-raised p-3.5 text-left text-lp-ink shadow-lg"
          style={{ left: at.x, top: at.y, translate: at.below ? "0 0" : "0 -100%" }}
        >
          <span className="text-[13px] text-lp-muted">Quoted from the posting</span>
          <span className="text-[15px] leading-snug font-medium">{title}</span>
          <span className="flex items-center justify-between gap-3 text-[13px]">
            <span>{company}</span>
            <span className="flex items-center gap-1 font-mono text-[12px] text-lp-muted">{host}<ArrowUpRight aria-hidden className="size-3.5" strokeWidth={2} /></span>
          </span>
        </span>,
        document.body,
      )}
    </>
  );
}
