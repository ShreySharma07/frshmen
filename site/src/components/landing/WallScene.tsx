"use client";

// The Highlighter's WebGL layer (React Three Fiber + troika SDF text): columns of real deciding
// lines. `drive.sweep` (0 → 1, played on load and when the reader changes their years) runs a
// highlighter down the wall: lines that take the reader get marked and lift toward them, lines that
// ask for more get struck through and sink. `drive.collapse` (from the scroll) clears the wall to
// the one line the card below is about. Everything moves per frame from refs, never React state.
import { Text } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef, type RefObject } from "react";
import * as THREE from "three";
import { color } from "@/design/tokens";
import type { EvidenceLine } from "@/lib/api";
import { clip, fit, rows, type Fit } from "./wall";

export interface WallDrive {
  sweep: number;
  collapse: number;
  pointerX: number;
  pointerY: number;
}

const INK = color.landingLight.ink;
const MUTED = color.landingLight.muted;
const MARK = color.landingLight.mark;
const STRIKE = color.landingLight.del;
const FONT = "/fonts/GeistMono-Regular.ttf";

export default function WallScene({ lines, years, hero, drive, onReady }: {
  lines: EvidenceLine[];
  years: number;
  hero: EvidenceLine | null;
  drive: RefObject<WallDrive>;
  onReady: () => void;
}) {
  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 0, 10], fov: 30 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onCreated={onReady}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      aria-hidden
    >
      <Wall lines={lines} years={years} hero={hero} drive={drive} />
    </Canvas>
  );
}

interface Item { line: EvidenceLine; x: number; y: number; t: number; fit: Fit; text: string }

function Wall({ lines, years, hero, drive }: { lines: EvidenceLine[]; years: number; hero: EvidenceLine | null; drive: RefObject<WallDrive> }) {
  const { viewport, size } = useThree();
  const group = useRef<THREE.Group>(null);

  // Lay the wall out in world units so the text is ~13px on screen at any size.
  const layout = useMemo(() => {
    const unit = viewport.width / size.width; // world units per CSS pixel
    const fontSize = 13 * unit;
    const rowH = fontSize * 2.15;
    const cols = size.width >= 1100 ? 3 : size.width >= 700 ? 2 : 1;
    const margin = 40 * unit;
    const colW = (viewport.width - margin * 2) / cols;
    const chars = Math.max(24, Math.floor((colW - 24 * unit) / (fontSize * 0.6)));
    const perCol = Math.ceil((viewport.height * 1.1) / rowH);
    const top = (perCol * rowH) / 2;
    const picked = rows(lines, cols * perCol);
    const items: Item[] = picked.map((line, i) => {
      const c = Math.floor(i / perCol), r = i % perCol;
      return { line, x: -viewport.width / 2 + margin + c * colW, y: top - r * rowH, t: r / perCol, fit: fit(line, years), text: clip(line.text, chars) };
    });
    // The line the card is about: the copy of the hero line nearest the middle of the wall.
    let heroIndex = -1, best = Infinity;
    items.forEach((it, i) => {
      if (hero && it.line === hero) {
        const d = Math.hypot(it.x + colW / 2, it.y);
        if (d < best) { best = d; heroIndex = i; }
      }
    });
    return { items, fontSize, rowH, heroIndex };
  }, [viewport.width, viewport.height, size.width, lines, years, hero]);

  const texts = useRef<(THREE.Mesh & { fillOpacity: number } | null)[]>([]);
  const marks = useRef<(THREE.Mesh | null)[]>([]);
  const strikes = useRef<(THREE.Mesh | null)[]>([]);
  const widths = useRef<number[]>([]);

  useFrame((_, dt) => {
    const d = drive.current;
    if (!d) return;
    const g = group.current;
    if (g) {
      // A slow tilt toward the pointer gives the wall depth without moving the reading line.
      g.rotation.y = THREE.MathUtils.damp(g.rotation.y, d.pointerX * 0.06, 4, dt);
      g.rotation.x = THREE.MathUtils.damp(g.rotation.x, -0.05 + d.pointerY * 0.04, 4, dt);
    }
    const { items, rowH, fontSize, heroIndex } = layout;
    for (let i = 0; i < items.length; i++) {
      const it = items[i], text = texts.current[i], mark = marks.current[i], strike = strikes.current[i];
      if (!text || !mark || !strike) continue;
      const w = widths.current[i] ?? 0;
      // How far the highlighter has passed this row: rows lower on the wall are reached later.
      const local = THREE.MathUtils.clamp((d.sweep * 1.35 - it.t) / 0.35, 0, 1);
      const isHero = i === heroIndex;
      let op = 1, z = 0, dy = 0, m = 0, s = 0;
      if (it.fit === "fits") { m = local; z = local * 0.35; }
      else if (it.fit === "over") { s = local; op = 1 - 0.62 * local; dy = -local * rowH * 0.15; z = -local * 0.3; }
      else { op = 1 - 0.45 * local; }
      // The scroll clears the wall to the hero line, which comes forward to meet the card.
      const c = d.collapse;
      let x = it.x, y = it.y + dy;
      if (isHero) {
        x = THREE.MathUtils.lerp(it.x, -w / 2, c);
        y = THREE.MathUtils.lerp(y, rowH * 1.2, c);
        z = THREE.MathUtils.lerp(z, 1.6, c);
        m = Math.max(m, c);
      } else {
        op *= 1 - c;
      }
      text.position.set(x, y, z);
      text.fillOpacity = op;
      mark.visible = m > 0.001 && w > 0;
      mark.scale.set(Math.max(1e-4, w * m + fontSize * 0.6 * m), rowH * 0.74, 1);
      mark.position.set(x - fontSize * 0.3 + (w * m + fontSize * 0.6 * m) / 2, y, z - 0.01);
      (mark.material as THREE.MeshBasicMaterial).opacity = isHero ? 1 : op;
      strike.visible = s > 0.001 && w > 0;
      strike.scale.set(Math.max(1e-4, w * s), fontSize * 0.09, 1);
      strike.position.set(x + (w * s) / 2, y, z + 0.005);
      (strike.material as THREE.MeshBasicMaterial).opacity = op;
    }
  });

  const plane = useMemo(() => new THREE.PlaneGeometry(1, 1), []);
  return (
    <group ref={group}>
      {layout.items.map((it, i) => (
        <group key={i}>
          <mesh ref={(m) => { marks.current[i] = m; }} geometry={plane} visible={false}>
            <meshBasicMaterial color={MARK} transparent depthWrite={false} />
          </mesh>
          <Text
            ref={(t: THREE.Mesh & { fillOpacity: number } | null) => { texts.current[i] = t; }}
            font={FONT}
            fontSize={layout.fontSize}
            anchorX="left"
            anchorY="middle"
            whiteSpace="nowrap"
            color={it.fit === "unclear" ? MUTED : INK}
            position={[it.x, it.y, 0]}
            onSync={(troika) => {
              const b = troika.textRenderInfo?.blockBounds;
              if (b) widths.current[i] = b[2] - b[0];
            }}
          >
            {it.text}
          </Text>
          <mesh ref={(m) => { strikes.current[i] = m; }} geometry={plane} visible={false}>
            <meshBasicMaterial color={STRIKE} transparent depthWrite={false} />
          </mesh>
        </group>
      ))}
    </group>
  );
}
