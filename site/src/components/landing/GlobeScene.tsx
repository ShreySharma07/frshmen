"use client";

// The landing globe in WebGL (React Three Fiber + hand-written shaders), replacing cobe so it can do
// more than spin: 11.5k land dots on a dark body with a marigold rim of light, a light for every
// place with open jobs (sized by its count, pulsing), and arcs from hubs abroad landing on India.
// GlobeStory drives it from the scroll through `view`:
//   focus 0 → 1  turns from a slow spin to face India
//   arcs  0 → 1  draws the arcs
//   dive  0 → 1  zooms into India, the rest of the world falls away
//   morph 0 → 1  the Indian city lights fly into the table beside the globe and become its bullets
// The canvas covers the whole sticky screen; the globe sits wherever [data-globe-anchor] is (so
// CSS and GSAP still place it), and the lights read their table slots from [data-city-slot].
// Everything moves per frame from refs, never React state.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef, type RefObject } from "react";
import * as THREE from "three";
import { color } from "@/design/tokens";
import { landPoints } from "./land";
import type { Place } from "./places";

export interface GlobeView {
  focus: number;
  arcs: number;
  dive: number;
  morph: number;
  drag: number; // degrees the reader has turned it by hand
}

const D = color.landingDark;
const INDIA = { lat: 21, lng: 78 };
const DIVE_ZOOM = 2.4;
const rad = THREE.MathUtils.degToRad;

/** A point on the unit sphere; longitude 0 faces the camera when the globe isn't turned. */
function toVec(lat: number, lng: number, r = 1) {
  const a = rad(lat), b = rad(lng);
  return new THREE.Vector3(Math.cos(a) * Math.sin(b) * r, Math.sin(a) * r, Math.cos(a) * Math.cos(b) * r);
}
const rgb = (hex: string) => new THREE.Color(hex);

export default function GlobeScene({ cities, abroad, view, root, still, active, onReady }: {
  cities: Place[];
  abroad: Place[];
  view: RefObject<GlobeView>;
  root: RefObject<HTMLElement | null>;
  still: boolean; // reduced motion: no spin, no pulse, draw only when something changes
  active: boolean; // on screen
  onReady: () => void;
}) {
  return (
    <Canvas
      dpr={[1, 2]}
      frameloop={still ? "demand" : active ? "always" : "never"}
      // Orthographic, one world unit per CSS pixel: the dive grows the globe without the fish-eye a
      // perspective camera gives a sphere this close, and DOM rects map straight onto the scene.
      orthographic
      camera={{ position: [0, 0, 4000], zoom: 1, near: 1, far: 8000 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onCreated={onReady}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      aria-hidden
    >
      <Earth cities={cities} abroad={abroad} view={view} root={root} still={still} />
    </Canvas>
  );
}

const DOT_VERT = /* glsl */ `
  uniform float uSize;
  varying float vFace;
  void main() {
    vFace = normalize(normalMatrix * position).z; // 1 facing us, 0 at the edge of the disc
    gl_PointSize = uSize;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const DOT_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vFace;
  void main() {
    if (vFace < 0.0) discard;
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    // Dots dim toward the limb, as light falls off a sphere.
    gl_FragColor = vec4(uColor, uOpacity * smoothstep(0.5, 0.3, d) * (0.22 + 0.78 * smoothstep(0.0, 0.6, vFace)));
    #include <colorspace_fragment>
  }`;

// The body: dark, with a warm rim where the atmosphere would catch the light.
const BODY_VERT = /* glsl */ `
  varying float vFace;
  void main() {
    vFace = normalize(normalMatrix * normal).z;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const BODY_FRAG = /* glsl */ `
  uniform vec3 uBody;
  uniform vec3 uRim;
  uniform float uOpacity;
  varying float vFace;
  void main() {
    float rim = pow(1.0 - max(vFace, 0.0), 3.5);
    gl_FragColor = vec4(mix(uBody, uRim, rim * 0.4), uOpacity);
    #include <colorspace_fragment>
  }`;
// The halo outside the disc, drawn on the inside of a slightly larger sphere.
const HALO_FRAG = /* glsl */ `
  uniform vec3 uRim;
  uniform float uOpacity;
  varying float vFace;
  void main() {
    // On the inside of the shell, -vFace runs from ~0.48 at the limb to 0 at the shell's edge.
    float glow = pow(smoothstep(0.0, 0.48, -vFace), 2.2);
    gl_FragColor = vec4(uRim, glow * uOpacity);
    #include <colorspace_fragment>
  }`;

const MARK_VERT = /* glsl */ `
  attribute float aSize;
  attribute float aAlpha;
  attribute float aSeed;
  uniform float uDpr;
  varying float vAlpha;
  varying float vSeed;
  void main() {
    vAlpha = aAlpha;
    vSeed = aSeed;
    gl_PointSize = aSize * uDpr;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const MARK_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uPulse;
  varying float vAlpha;
  varying float vSeed;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0; // 0 at the centre, 1 at the edge of the sprite
    float core = smoothstep(0.4, 0.32, d);
    float ring = fract(uTime * 0.4 + vSeed);
    float pulse = smoothstep(0.07, 0.0, abs(d - ring)) * (1.0 - ring) * 0.7 * uPulse;
    float glow = exp(-d * 5.0) * 0.45 * uPulse;
    float a = (core + pulse + glow) * vAlpha;
    if (a < 0.01) discard;
    gl_FragColor = vec4(uColor, a);
    #include <colorspace_fragment>
  }`;

const ARC_VERT = /* glsl */ `
  varying float vT;
  varying float vFace;
  void main() {
    vT = uv.x;
    vFace = normalize(normalMatrix * position).z; // where on the globe this part of the arc sits
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const ARC_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uDraw;
  uniform float uTime;
  uniform float uSeed;
  uniform float uOpacity;
  varying float vT;
  varying float vFace;
  void main() {
    if (vT > uDraw) discard;
    // A glint travels each arc toward India: an opening abroad that would take you there.
    float head = fract(uTime * 0.22 + uSeed);
    float glint = smoothstep(0.1, 0.0, abs(vT - head));
    // Arcs fade as they go over the horizon instead of looping above the far side.
    gl_FragColor = vec4(uColor, uOpacity * (0.3 + 0.7 * glint) * smoothstep(-0.1, 0.25, vFace));
    #include <colorspace_fragment>
  }`;

interface Light { place: Place; local: THREE.Vector3; size: number; india: boolean }

function Earth({ cities, abroad, view, root, still }: {
  cities: Place[];
  abroad: Place[];
  view: RefObject<GlobeView>;
  root: RefObject<HTMLElement | null>;
  still: boolean;
}) {
  const { camera, size, viewport, gl } = useThree();
  const globe = useRef<THREE.Group>(null); // placed and scaled onto the anchor
  const spin = useRef<THREE.Group>(null); // turned to the facing longitude
  const clock = useRef(0);
  // Per-frame writes go through the objects' refs (the React compiler won't have memoised values mutated).
  const landRef = useRef<THREE.Points>(null);
  const bodyRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const marksRef = useRef<THREE.Points>(null);
  const arcRefs = useRef<(THREE.Mesh | null)[]>([]);

  const land = useMemo(() => {
    const pts = landPoints();
    const arr = new Float32Array(pts.length * 3);
    pts.forEach(([lat, lng], i) => toVec(lat, lng).toArray(arr, i * 3));
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    return g;
  }, []);

  const dots = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: DOT_VERT, fragmentShader: DOT_FRAG, transparent: true, depthWrite: false,
    uniforms: { uSize: { value: 2 }, uColor: { value: rgb(D.ink) }, uOpacity: { value: 0.62 } },
  }), []);
  const body = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: BODY_VERT, fragmentShader: BODY_FRAG, transparent: true,
    uniforms: { uBody: { value: rgb(D.surface) }, uRim: { value: rgb(D.accent) }, uOpacity: { value: 1 } },
  }), []);
  const halo = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: BODY_VERT, fragmentShader: HALO_FRAG, transparent: true, depthWrite: false,
    side: THREE.BackSide, blending: THREE.AdditiveBlending,
    uniforms: { uRim: { value: rgb(D.accent) }, uOpacity: { value: 0.2 } },
  }), []);

  // Lights: Indian cities by their own count, hubs abroad by their country's. Area follows the count.
  const lights = useMemo<Light[]>(() => {
    const all = [...cities.map((p) => ({ p, india: true })), ...abroad.map((p) => ({ p, india: false }))];
    const max = Math.max(...all.map(({ p }) => p.n), 1);
    return all.map(({ p, india }) => ({ place: p, local: toVec(p.lat, p.lng, 1.005), size: 12 + 30 * Math.sqrt(p.n / max), india }));
  }, [cities, abroad]);

  const marks = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(lights.length * 3), 3));
    g.setAttribute("aSize", new THREE.BufferAttribute(new Float32Array(lights.length), 1));
    g.setAttribute("aAlpha", new THREE.BufferAttribute(new Float32Array(lights.length), 1));
    g.setAttribute("aSeed", new THREE.BufferAttribute(Float32Array.from(lights, (_, i) => (i * 0.618) % 1), 1));
    return g;
  }, [lights]);
  const markMat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: MARK_VERT, fragmentShader: MARK_FRAG, transparent: true, depthTest: false, depthWrite: false,
    uniforms: { uColor: { value: rgb(D.accent) }, uTime: { value: 0 }, uPulse: { value: 1 }, uDpr: { value: 1 } },
  }), []);

  // Arcs from each hub abroad to Bengaluru, India's biggest count, higher the farther they travel.
  const arcs = useMemo(() => {
    const to = cities.find((c) => c.id === "blr") ?? cities[0];
    if (!to) return [];
    const b = toVec(to.lat, to.lng);
    return abroad.map((p, i) => {
      const a = toVec(p.lat, p.lng);
      const angle = a.angleTo(b);
      const pts = Array.from({ length: 33 }, (_, k) => {
        const t = k / 32;
        const v = a.clone().lerp(b, t).normalize(); // close enough to a great circle at this size
        return v.multiplyScalar(1.004 + (0.03 + 0.14 * (angle / Math.PI)) * Math.sin(Math.PI * t));
      });
      const geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 64, 0.0032, 6, false);
      const material = new THREE.ShaderMaterial({
        vertexShader: ARC_VERT, fragmentShader: ARC_FRAG, transparent: true, depthWrite: false,
        uniforms: { uColor: { value: rgb(D.accentText) }, uDraw: { value: 0 }, uTime: { value: 0 }, uSeed: { value: (i * 0.37) % 1 }, uOpacity: { value: 0.85 } },
      });
      return { geometry, material, delay: (i / Math.max(abroad.length, 1)) * 0.35 };
    });
  }, [cities, abroad]);

  const tmp = useMemo(() => ({ v: new THREE.Vector3(), c: new THREE.Vector3(), n: new THREE.Vector3(), cam: new THREE.Vector3(), d: new THREE.Vector3(), t: new THREE.Vector3() }), []);

  useFrame((_, dt) => {
    const v = view.current, g = globe.current, s = spin.current, el = root.current;
    const lp = landRef.current, bm = bodyRef.current, hm = haloRef.current, mp = marksRef.current;
    if (!v || !g || !s || !el || !lp || !bm || !hm || !mp) return;
    const uni = (o: THREE.Mesh | THREE.Points) => (o.material as THREE.ShaderMaterial).uniforms;
    if (!still) clock.current += dt;
    const canvas = gl.domElement.getBoundingClientRect();
    const unit = viewport.height / size.height; // world units per CSS pixel, at z = 0
    const toWorldX = (px: number) => (px - canvas.left - size.width / 2) * unit;
    const toWorldY = (py: number) => -(py - canvas.top - size.height / 2) * unit;

    // Sit on the anchor (CSS and GSAP place and scale it), then grow into India for the dive.
    const anchor = el.querySelector<HTMLElement>("[data-globe-anchor]")?.getBoundingClientRect();
    if (!anchor) return;
    const ease = (x: number) => x * x * (3 - 2 * x);
    const dive = ease(v.dive);
    // Phones zoom less: the table sits right under the globe, and India must stay on screen.
    const radiusPx = (anchor.width / 2) * THREE.MathUtils.lerp(1, size.width < 1024 ? 1.6 : DIVE_ZOOM, dive);
    g.position.set(toWorldX(anchor.left + anchor.width / 2), toWorldY(anchor.top + anchor.height / 2), 0);
    g.scale.setScalar(radiusPx * unit);

    // A slow spin from just east of India, turned by hand if the reader drags, eased to face India.
    const free = INDIA.lng + 40 - clock.current * 6 - v.drag;
    const toIndia = ((((INDIA.lng - free) % 360) + 540) % 360) - 180; // the short way round
    const facing = free + toIndia * v.focus;
    s.rotation.set(rad(THREE.MathUtils.lerp(14, INDIA.lat, v.focus)), -rad(facing), 0);
    g.updateMatrixWorld(true);

    const dpr = gl.getPixelRatio();
    uni(lp).uSize.value = Math.max(1.6, radiusPx * 0.0072) * dpr;
    uni(lp).uOpacity.value = 0.62 * (1 - 0.6 * dive);
    uni(hm).uOpacity.value = 0.2 * (1 - dive);
    uni(bm).uOpacity.value = 1 - 0.35 * dive;
    const mu = uni(mp);
    mu.uTime.value = clock.current;
    mu.uDpr.value = dpr;
    mu.uPulse.value = 1 - v.morph;
    arcs.forEach((a, i) => {
      const m = arcRefs.current[i];
      if (!m) return;
      const u = uni(m);
      u.uDraw.value = THREE.MathUtils.clamp((v.arcs - a.delay) / 0.65, 0, 1) * 1.001;
      u.uTime.value = clock.current;
      u.uOpacity.value = 0.85 * (1 - dive);
    });

    // Each light: on the globe, faded on the far side; Indian cities then fly to their table slot.
    const pos = mp.geometry.attributes.position as THREE.BufferAttribute;
    const sz = mp.geometry.attributes.aSize as THREE.BufferAttribute;
    const al = mp.geometry.attributes.aAlpha as THREE.BufferAttribute;
    const morph = ease(v.morph);
    tmp.c.setFromMatrixPosition(g.matrixWorld);
    camera.getWorldPosition(tmp.cam);
    lights.forEach((l, i) => {
      tmp.v.copy(l.local).applyMatrix4(s.matrixWorld);
      tmp.n.copy(tmp.v).sub(tmp.c).normalize();
      const face = THREE.MathUtils.smoothstep(tmp.n.dot(tmp.d.copy(tmp.cam).sub(tmp.v).normalize()), -0.05, 0.25);
      let alpha = face * (l.india ? 1 : 1 - dive);
      let px = l.size * THREE.MathUtils.lerp(1, 1.5, dive);
      const slot = l.india && morph > 0 ? el.querySelector<HTMLElement>(`[data-city-slot="${l.place.id}"]`)?.getBoundingClientRect() : undefined;
      if (slot) {
        tmp.v.lerp(tmp.t.set(toWorldX(slot.left + slot.width / 2), toWorldY(slot.top + slot.height / 2), 0), morph);
        px = THREE.MathUtils.lerp(px, slot.width * 2.6, morph);
        alpha = THREE.MathUtils.lerp(alpha, 1, morph);
      } else if (l.india) {
        alpha *= 1 - morph; // cities without a row bow out
      }
      pos.setXYZ(i, tmp.v.x, tmp.v.y, tmp.v.z);
      sz.setX(i, px);
      al.setX(i, alpha);

      // The few labelled places carry a label that rides with them while they face us.
      const label = el.querySelector<HTMLElement>(`[data-globe-label="${l.place.id}"]`);
      if (label) {
        const p = tmp.d.copy(tmp.v).project(camera);
        const x = ((p.x + 1) / 2) * size.width, y = ((1 - p.y) / 2) * size.height;
        label.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, calc(-100% - ${(px / 2).toFixed(1)}px))`;
        label.style.opacity = String(face * (1 - Math.min(1, dive * 3)));
      }
    });
    pos.needsUpdate = sz.needsUpdate = al.needsUpdate = true;
  });

  // Drawn in a fixed order (transparent objects at one centre would otherwise sort at random):
  // halo, body, land, arcs, then the lights on top of everything.
  return (
    <>
    <group ref={globe}>
      <mesh ref={haloRef} material={halo} scale={1.14} renderOrder={0}><sphereGeometry args={[1, 64, 48]} /></mesh>
      <group ref={spin}>
        <mesh ref={bodyRef} material={body} renderOrder={1}><sphereGeometry args={[0.995, 96, 64]} /></mesh>
        <points ref={landRef} geometry={land} material={dots} renderOrder={2} />
        {arcs.map((a, i) => <mesh key={i} ref={(m) => { arcRefs.current[i] = m; }} geometry={a.geometry} material={a.material} renderOrder={3} />)}
      </group>
    </group>
    {/* The lights live in world space (outside the globe's transform) so they can leave it. */}
    <points ref={marksRef} geometry={marks} material={markMat} frustumCulled={false} renderOrder={4} />
    </>
  );
}
