"use client";
// Light/dark switch. The theme is set before first paint by the script in layout.tsx (no white
// flash); this only flips it and remembers the choice. Without a saved choice the site follows
// the device setting, including when it changes.
import { Moon, Sun } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

type Theme = "light" | "dark";
const KEY = "kario.theme";
const EVENT = "kario:theme";

const read = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");
function subscribe(onChange: () => void) {
  addEventListener(EVENT, onChange);
  return () => removeEventListener(EVENT, onChange);
}
function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  dispatchEvent(new Event(EVENT));
}
function saved(): Theme | null {
  try { const t = localStorage.getItem(KEY); return t === "light" || t === "dark" ? t : null; } catch { return null; }
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, read, () => null); // null while printed at build time

  // Follow the device while the person hasn't chosen.
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => { if (!saved()) apply(mq.matches ? "dark" : "light"); };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button type="button" aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}
      onClick={() => { apply(next); try { localStorage.setItem(KEY, next); } catch { /* still switches for this visit */ } }}
      className="grid size-9 shrink-0 place-items-center rounded-md border border-line text-muted transition-colors duration-quick hover:bg-surface hover:text-ink">
      {/* Before the theme is known, keep the slot so the header doesn't shift. */}
      {theme === null ? null : theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}
