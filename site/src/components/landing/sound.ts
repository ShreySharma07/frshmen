// Opt-in sound for the landing page (critique 2026-10-23, the micro layer). Off until the reader
// turns it on in the top bar; the choice is remembered. Every sound is synthesised with WebAudio
// (no files to download) and short, and each one marks a moment the page is explaining:
//   tick   you chose your years           swipe  the highlighter re-reads the wall
//   stamp  a verdict lands                chime  the note to a referrer is sent
type Kind = "tick" | "swipe" | "stamp" | "chime";

const KEY = "kario:sound";
let on = false;
let ctx: AudioContext | null = null;
const listeners = new Set<() => void>();

try { on = localStorage.getItem(KEY) === "1"; } catch {}

export const soundOn = () => on;
export const soundOnServer = () => false;
export function subscribeSound(cb: () => void) {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

export function setSound(next: boolean) {
  on = next;
  try { localStorage.setItem(KEY, next ? "1" : "0"); } catch {}
  if (next) { audio(); play("tick"); }
  listeners.forEach((cb) => cb());
}

// Created on first use, which is always after a click (browsers only allow sound after a gesture).
function audio() {
  if (!ctx) {
    const A = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!A) return null;
    ctx = new A();
  }
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

export function play(kind: Kind) {
  if (!on || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const a = audio();
  if (!a || a.state !== "running") return;
  const t = a.currentTime;
  const out = a.createGain();
  out.gain.value = 0.5;
  out.connect(a.destination);
  if (kind === "tick") tone(a, out, t, 1800, 1800, 0.05, 0.045);
  if (kind === "chime") { tone(a, out, t, 880, 880, 0.05, 0.6); tone(a, out, t + 0.07, 1320, 1320, 0.035, 0.7); }
  if (kind === "stamp") { tone(a, out, t, 150, 55, 0.3, 0.16); noise(a, out, t, 0.06, 0.08, "lowpass", 900, 900); }
  if (kind === "swipe") noise(a, out, t, 0.035, 0.38, "bandpass", 1700, 2600);
}

function tone(a: AudioContext, out: AudioNode, t: number, from: number, to: number, peak: number, length: number) {
  const o = a.createOscillator(), g = a.createGain();
  o.frequency.setValueAtTime(from, t);
  o.frequency.exponentialRampToValueAtTime(to, t + length);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(peak, t + 0.004);
  g.gain.exponentialRampToValueAtTime(0.0001, t + length);
  o.connect(g).connect(out);
  o.start(t);
  o.stop(t + length + 0.02);
}

// Filtered noise: a felt tip dragged across paper, or the body of a stamp.
function noise(a: AudioContext, out: AudioNode, t: number, peak: number, length: number, type: BiquadFilterType, from: number, to: number) {
  const buf = a.createBuffer(1, Math.ceil(a.sampleRate * length), a.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const src = a.createBufferSource(), f = a.createBiquadFilter(), g = a.createGain();
  src.buffer = buf;
  f.type = type;
  f.Q.value = 0.9;
  f.frequency.setValueAtTime(from, t);
  f.frequency.linearRampToValueAtTime(to, t + length);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(peak, t + length * 0.25);
  g.gain.linearRampToValueAtTime(0, t + length);
  src.connect(f).connect(g).connect(out);
  src.start(t);
}
