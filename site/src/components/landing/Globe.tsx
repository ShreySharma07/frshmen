"use client";

// The dotted earth (cobe, ~5 KB of WebGL). It spins on its own, can be dragged, and turns to face
// India as `view.focus` goes from 0 to 1 (GlobeStory drives that from the scroll). Markers are the
// places with live jobs, sized by count. Without WebGL, or with Save-Data on, a still picture
// stands in.
import createGlobe from "cobe";
import { useEffect, useRef, useSyncExternalStore, type RefObject } from "react";
import { color } from "@/design/tokens";
import type { Place } from "./places";

export interface GlobeView {
  focus: number; // 0 = free spin, 1 = facing India
}

const INDIA = { lat: 21, lng: 78 };
const rgb = (hex: string): [number, number, number] => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number];
// cobe's angles for a place to face the viewer (from cobe's docs).
const facing = (lat: number, lng: number) => [Math.PI - ((lng * Math.PI) / 180 - Math.PI / 2), (lat * Math.PI) / 180];

let stillCache: boolean | undefined;
function stillWanted() {
  if (stillCache === undefined) {
    const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
    const probe = document.createElement("canvas");
    stillCache = Boolean(saveData) || !(probe.getContext("webgl2") || probe.getContext("webgl"));
  }
  return stillCache;
}
const noChange = () => () => {};

export function Globe({ places, view, className = "" }: { places: Place[]; view: RefObject<GlobeView>; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  // A still picture instead of WebGL: no WebGL, or the reader's data saver is on. Read once.
  const still = useSyncExternalStore(noChange, stillWanted, () => false);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const max = Math.max(...places.map((p) => p.n), 1);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const size = () => el.offsetWidth * dpr;
    let [phi] = facing(INDIA.lat, INDIA.lng + 40); // start just east of India so it spins into view
    const [indiaPhi, indiaTheta] = facing(INDIA.lat, INDIA.lng);
    let drag: number | null = null;
    let dragged = 0;
    let visible = true;
    let frame = 0;

    const globe = createGlobe(el, {
      devicePixelRatio: dpr,
      width: size(),
      height: size(),
      phi,
      theta: 0.25,
      dark: 1,
      diffuse: 1.15,
      mapSamples: 16000,
      mapBrightness: 5.5,
      mapBaseBrightness: 0.04,
      baseColor: rgb(color.night.raised).map((v) => Math.min(1, v * 2.2)) as [number, number, number],
      markerColor: rgb(color.night.accent),
      glowColor: rgb(color.night.surface).map((v) => v * 1.6) as [number, number, number],
      markers: places.map((p) => ({ location: [p.lat, p.lng], size: 0.025 + 0.07 * Math.sqrt(p.n / max), id: p.id })),
      markerElevation: 0.01,
    });

    const tick = () => {
      const f = view.current?.focus ?? 0;
      if (drag === null && !reduce) phi += 0.0022 * (1 - f);
      // Ease the free spin toward India by the nearest way round.
      const target = indiaPhi + Math.round((phi - indiaPhi) / (2 * Math.PI)) * 2 * Math.PI;
      globe.update({ phi: phi + (target - phi) * f + dragged, theta: 0.25 + (indiaTheta - 0.25) * f });
      if (visible) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    const seen = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      cancelAnimationFrame(frame);
      if (visible) frame = requestAnimationFrame(tick);
    });
    seen.observe(el);
    const resized = new ResizeObserver(() => globe.update({ width: size(), height: size() }));
    resized.observe(el);

    const down = (e: PointerEvent) => { drag = e.clientX - dragged * 160; el.setPointerCapture(e.pointerId); };
    const move = (e: PointerEvent) => { if (drag !== null) dragged = (e.clientX - drag) / 160; };
    const up = () => { if (drag !== null) { phi += dragged; dragged = 0; drag = null; } };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.style.opacity = "1";

    return () => {
      cancelAnimationFrame(frame);
      seen.disconnect();
      resized.disconnect();
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      globe.destroy();
    };
  }, [places, view]);

  if (still) {
    // Captured from the live globe, facing India with markers lit (2026-10-23 counts).
    // eslint-disable-next-line @next/next/no-img-element -- static export, no image optimiser
    return <img src="/landing/globe.webp" alt="The earth as dots, with lit markers on Indian cities and hubs abroad that have open jobs" className={`aspect-square w-full ${className}`} />;
  }
  return (
    <canvas
      ref={canvas}
      aria-label="A dotted globe with lit markers where Kario has open jobs. Drag to turn it."
      className={`aspect-square w-full cursor-grab touch-pan-y opacity-0 transition-opacity duration-landing ease-out-expo active:cursor-grabbing ${className}`}
    />
  );
}
