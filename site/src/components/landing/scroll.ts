// One smooth-scroll instance for the landing page, so controls (the How it works pills) scroll with
// it instead of fighting it. Falls back to the browser's own scrolling when Lenis is off.
import type Lenis from "lenis";

let lenis: Lenis | null = null;
export const setLenis = (l: Lenis | null) => { lenis = l; };

/** Scrolls so the element's middle sits in the middle of the screen. */
export function scrollToMiddle(el: HTMLElement) {
  const offset = el.offsetHeight / 2 - window.innerHeight / 2;
  if (lenis) lenis.scrollTo(el, { offset, duration: 1.1 });
  else window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY + offset, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

/** Scrolls to an absolute page offset (a point inside a pinned scene). */
export function scrollToY(y: number) {
  if (lenis) lenis.scrollTo(y, { duration: 1.1 });
  else window.scrollTo({ top: y, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}
