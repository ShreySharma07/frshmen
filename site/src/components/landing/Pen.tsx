"use client";

// The hero's pointer is a highlighter (critique 2026-10-23, the micro layer): over the wall the
// cursor becomes a marigold chisel nib and leaves a stroke that fades in under a second,
// multiplied into the paper like real ink. Over controls the normal pointer comes back. Only with
// a mouse or trackpad, and never with reduced motion.
import { useEffect, useRef, useSyncExternalStore } from "react";
import { color } from "@/design/tokens";

const FADE_MS = 700;
const INK = color.landingLight.mark;
const query = () => matchMedia("(pointer: fine) and (prefers-reduced-motion: no-preference)");
const subscribe = (cb: () => void) => { const m = query(); m.addEventListener("change", cb); return () => m.removeEventListener("change", cb); };

export function Pen({ area }: { area: React.RefObject<HTMLElement | null> }) {
  const on = useSyncExternalStore(subscribe, () => query().matches, () => false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const nib = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = area.current, cv = canvas.current, tip = nib.current;
    if (!on || !el || !cv || !tip) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    el.classList.add("hl-pen");
    const trail: { x: number; y: number; t: number }[] = [];
    let frame = 0;

    const fit = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      cv.width = el.clientWidth * dpr;
      cv.height = el.clientHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    fit();
    const resized = new ResizeObserver(fit);
    resized.observe(el);

    const draw = () => {
      const now = performance.now();
      while (trail.length && now - trail[0].t > FADE_MS) trail.shift();
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.lineCap = "butt";
      ctx.lineJoin = "round";
      ctx.strokeStyle = INK;
      for (let i = 1; i < trail.length; i++) {
        const a = trail[i - 1], b = trail[i];
        ctx.globalAlpha = 0.85 * (1 - (now - b.t) / FADE_MS);
        ctx.lineWidth = 16;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      frame = trail.length ? requestAnimationFrame(draw) : 0;
    };

    const move = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" && e.pointerType !== "pen") return;
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      const overControl = e.target instanceof Element && e.target.closest("a, button, input, label, [role=radio]");
      tip.style.transform = `translate(${x}px, ${y}px)`;
      tip.style.opacity = overControl ? "0" : "1";
      if (!overControl) trail.push({ x, y, t: performance.now() });
      if (!frame && trail.length) frame = requestAnimationFrame(draw);
    };
    const leave = () => { tip.style.opacity = "0"; };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(frame);
      resized.disconnect();
      el.classList.remove("hl-pen");
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
    };
  }, [on, area]);

  if (!on) return null;
  return (
    <>
      <canvas ref={canvas} aria-hidden className="pointer-events-none absolute inset-0 z-20 size-full mix-blend-multiply" />
      {/* The nib: a chisel tip, held at an angle, its writing corner on the pointer's hotspot. */}
      <div ref={nib} aria-hidden className="pointer-events-none absolute top-0 left-0 z-30 opacity-0 transition-opacity duration-quick">
        <i className="block h-[22px] w-[11px] -translate-x-[3px] -translate-y-[19px] rotate-[32deg] rounded-[2px_2px_3px_3px] bg-lp-accent shadow-[0_1px_0_rgb(0_0_0/0.25)]" />
      </div>
    </>
  );
}
