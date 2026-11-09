/**
 * Neural brain / particle-network hero.
 * Geometry is centered at origin; camera fits the bounding sphere on every resize.
 */
import * as THREE from "./three.module.min.js";

function hash(n) {
  const x = Math.sin(n * 127.1) * 43758.5453;
  return x - Math.floor(x);
}

function noise3(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const w = zf * zf * (3 - 2 * zf);
  const n000 = hash(xi + yi * 57 + zi * 113);
  const n100 = hash(xi + 1 + yi * 57 + zi * 113);
  const n010 = hash(xi + (yi + 1) * 57 + zi * 113);
  const n110 = hash(xi + 1 + (yi + 1) * 57 + zi * 113);
  const n001 = hash(xi + yi * 57 + (zi + 1) * 113);
  const n101 = hash(xi + 1 + yi * 57 + (zi + 1) * 113);
  const n011 = hash(xi + (yi + 1) * 57 + (zi + 1) * 113);
  const n111 = hash(xi + 1 + (yi + 1) * 57 + (zi + 1) * 113);
  const x00 = n000 * (1 - u) + n100 * u;
  const x10 = n010 * (1 - u) + n110 * u;
  const x01 = n001 * (1 - u) + n101 * u;
  const x11 = n011 * (1 - u) + n111 * u;
  const y0 = x00 * (1 - v) + x10 * v;
  const y1 = x01 * (1 - v) + x11 * v;
  return y0 * (1 - w) + y1 * w;
}

/** Approximate brain surface sample (left/right hemispheres + stem bias). */
function sampleBrainPoint(i) {
  const side = i % 2 === 0 ? -1 : 1;
  const u = hash(i * 3.1);
  const v = hash(i * 7.7);
  const theta = u * Math.PI;
  const phi = v * Math.PI * 2;
  let x = Math.sin(theta) * Math.cos(phi) * 0.78;
  let y = Math.cos(theta) * 0.62;
  let z = Math.sin(theta) * Math.sin(phi) * 0.95;
  x = Math.abs(x) * side + side * 0.22;
  const n = noise3(x * 3.2, y * 3.2, z * 3.2);
  const n2 = noise3(x * 7.1 + 2, y * 7.1, z * 7.1);
  const bump = 1 + n * 0.16 + n2 * 0.07;
  x *= bump; y *= bump; z *= bump;
  y += 0.08 * Math.sin(phi * 2) * Math.abs(x);
  z *= 1.05;
  if (hash(i * 13.3) > 0.92) {
    x *= 0.35; y -= 0.55; z *= 0.45; y -= hash(i) * 0.2;
  }
  return new THREE.Vector3(x, y, z);
}

function centerPoints(points) {
  const box = new THREE.Box3();
  for (const p of points) box.expandByPoint(p);
  const center = new THREE.Vector3();
  box.getCenter(center);
  for (const p of points) p.sub(center);
  const sphere = new THREE.Sphere();
  box.makeEmpty();
  for (const p of points) box.expandByPoint(p);
  box.getBoundingSphere(sphere);
  return sphere;
}

export function mountBrainHero(container, opts = {}) {
  if (!container) return () => {};
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const mobile = Math.min(window.innerWidth, window.innerHeight) < 720;
  const COUNT = opts.count || (mobile ? 900 : 2800);
  const LINKS = opts.links || (mobile ? 1 : 2);

  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
  if (!gl || reduced) return null;

  const scene = new THREE.Scene();
  const FOV = 42;
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.05, 100);
  camera.position.set(0, 0, 3);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, alpha: true, powerPreference: "high-performance",
  });
  renderer.setClearColor(0x000000, 0);
  // Canvas must fill container with no CSS transform/offset
  Object.assign(canvas.style, {
    position: "absolute",
    inset: "0",
    width: "100%",
    height: "100%",
    display: "block",
    margin: "0",
    padding: "0",
    border: "0",
    transform: "none",
    left: "0",
    top: "0",
  });
  container.appendChild(canvas);

  const target = [];
  for (let i = 0; i < COUNT; i++) target.push(sampleBrainPoint(i));
  // Center geometry at origin and measure bounding sphere
  const boundSphere = centerPoints(target);
  const baseRadius = Math.max(boundSphere.radius, 0.8);

  const positions = new Float32Array(COUNT * 3);
  const phases = new Float32Array(COUNT);
  for (let i = 0; i < COUNT; i++) {
    const r = baseRadius * 1.6 * (0.35 + hash(i * 9.1));
    const th = hash(i * 2.2) * Math.PI * 2;
    const ph = hash(i * 4.4) * Math.PI;
    positions[i * 3] = r * Math.sin(ph) * Math.cos(th);
    positions[i * 3 + 1] = r * Math.cos(ph);
    positions[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    phases[i] = hash(i * 5.5) * Math.PI * 2;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    size: mobile ? 0.028 : 0.022,
    color: 0x5ce1ff,
    transparent: true,
    opacity: 0.95,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
  });
  const points = new THREE.Points(geo, mat);

  // synapses from centered targets
  const linePos = [];
  const cell = 0.22;
  const buckets = new Map();
  function key(x, y, z) {
    return `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
  }
  for (let i = 0; i < COUNT; i++) {
    const p = target[i];
    const k = key(p.x, p.y, p.z);
    if (!buckets.has(k)) buckets.set(k, []);
    buckets.get(k).push(i);
  }
  for (let i = 0; i < COUNT; i++) {
    const p = target[i];
    const candidates = [];
    const cx = Math.floor(p.x / cell), cy = Math.floor(p.y / cell), cz = Math.floor(p.z / cell);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
      const arr = buckets.get(`${cx + dx},${cy + dy},${cz + dz}`);
      if (!arr) continue;
      for (const j of arr) {
        if (j <= i) continue;
        const q = target[j];
        const d = p.distanceTo(q);
        if (d < 0.28) candidates.push([d, j]);
      }
    }
    candidates.sort((a, b) => a[0] - b[0]);
    for (let n = 0; n < Math.min(LINKS, candidates.length); n++) {
      const j = candidates[n][1];
      linePos.push(p.x, p.y, p.z, target[j].x, target[j].y, target[j].z);
    }
  }
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(linePos, 3));
  const lineMat = new THREE.LineBasicMaterial({
    color: 0xa78bfa,
    transparent: true,
    opacity: 0.22,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const lines = new THREE.LineSegments(lineGeo, lineMat);

  const pulseCount = mobile ? 24 : 64;
  const pulseGeo = new THREE.BufferGeometry();
  const pulsePos = new Float32Array(pulseCount * 3);
  pulseGeo.setAttribute("position", new THREE.BufferAttribute(pulsePos, 3));
  const pulseMat = new THREE.PointsMaterial({
    size: mobile ? 0.06 : 0.05,
    color: 0x5ef0c0,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const pulses = new THREE.Points(pulseGeo, pulseMat);
  const edgeCount = Math.max(1, linePos.length / 6);
  const pulseEdges = Array.from({ length: pulseCount }, (_, i) => Math.floor(hash(i * 11.1) * edgeCount));

  // Rotate around origin only — never translate the group
  const group = new THREE.Group();
  group.position.set(0, 0, 0);
  group.add(points); group.add(lines); group.add(pulses);
  scene.add(group);

  let mouseX = 0, mouseY = 0, t0 = performance.now(), assembled = 0;
  const onMove = (e) => {
    const r = container.getBoundingClientRect();
    if (!r.width || !r.height) return;
    mouseX = ((e.clientX - r.left) / r.width) * 2 - 1;
    mouseY = ((e.clientY - r.top) / r.height) * 2 - 1;
  };
  window.addEventListener("pointermove", onMove, { passive: true });

  function fitCamera(w, h) {
    const aspect = Math.max(0.5, w / Math.max(1, h));
    camera.aspect = aspect;
    // Vertical FOV is fixed; for narrow (portrait) aspect, effective horizontal FOV is smaller —
    // fit using the limiting axis so the full sphere stays inside with margin.
    const vFov = THREE.MathUtils.degToRad(FOV);
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * aspect);
    const limiting = Math.min(vFov, hFov);
    const margin = 1.25;
    const dist = (baseRadius * margin) / Math.sin(limiting / 2);
    camera.position.set(0, 0, dist);
    camera.near = Math.max(0.05, dist / 100);
    camera.far = dist * 20;
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }

  function resize() {
    const w = Math.max(1, container.clientWidth || 1);
    const h = Math.max(1, container.clientHeight || 1);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(w, h, false);
    fitCamera(w, h);
  }
  resize();
  const ro = new ResizeObserver(() => resize());
  ro.observe(container);

  let shock = 0;
  const baseTargets = target.map((p) => p.clone());
  function triggerShockwave() {
    shock = 1;
    for (let i = 0; i < COUNT; i++) {
      const dir = baseTargets[i].clone();
      if (dir.lengthSq() < 1e-6) dir.set(0, 1, 0);
      else dir.normalize();
      // scatter from centered base, then lerp back to baseTargets
      target[i].copy(baseTargets[i]).addScaledVector(dir, 0.55 + hash(i * 1.7) * 0.35);
    }
  }
  let highlightSide = 0;
  function highlightRegion(name) {
    const map = {
      api: -1, gpu: 1, tools: 1, trial: -1, app: 1, github: 0, hot: 0,
      "damoxing-mianfei-api": -1, "mianfei-gpu-yunfuwu": 1, "ai-kaifa-gongju": 1,
      "ai-huiyuan-shiyong": -1, "keji-app-xianmian": 1, "github-hot": 0, "hot-topics": 0,
    };
    highlightSide = map[name] || 0;
  }
  container.addEventListener("click", () => triggerShockwave());
  window.__brainAPI = { triggerShockwave, highlightRegion, destroy: null };

  let raf = 0;
  function frame(now) {
    const t = (now - t0) / 1000;
    assembled = Math.min(1, t / 2.2);
    const ease = 1 - Math.pow(1 - assembled, 3);
    if (shock > 0) {
      shock = Math.max(0, shock - 0.016);
      for (let i = 0; i < COUNT; i++) {
        target[i].lerp(baseTargets[i], 0.08);
      }
      if (shock === 0) {
        for (let i = 0; i < COUNT; i++) target[i].copy(baseTargets[i]);
      }
    }
    const pos = geo.attributes.position.array;
    for (let i = 0; i < COUNT; i++) {
      let tx = target[i].x, ty = target[i].y, tz = target[i].z;
      if (highlightSide && Math.sign(baseTargets[i].x) === highlightSide) {
        ty += Math.sin(t * 6 + phases[i]) * 0.03;
        tx *= 1.03;
      }
      const sx = pos[i * 3], sy = pos[i * 3 + 1], sz = pos[i * 3 + 2];
      pos[i * 3] = sx + (tx - sx) * (0.08 + 0.12 * ease);
      pos[i * 3 + 1] = sy + (ty - sy) * (0.08 + 0.12 * ease);
      pos[i * 3 + 2] = sz + (tz - sz) * (0.08 + 0.12 * ease);
      if (assembled >= 1 && shock === 0) {
        const wiggle = Math.sin(t * 2 + phases[i]) * 0.004;
        pos[i * 3] += wiggle;
        pos[i * 3 + 1] += wiggle * 0.6;
      }
    }
    geo.attributes.position.needsUpdate = true;

    const pp = pulseGeo.attributes.position.array;
    for (let i = 0; i < pulseCount; i++) {
      const e = pulseEdges[i];
      const a = e * 6;
      if (a + 5 >= linePos.length) continue;
      const u = (t * 0.35 + hash(i * 3.3)) % 1;
      pp[i * 3] = linePos[a] + (linePos[a + 3] - linePos[a]) * u;
      pp[i * 3 + 1] = linePos[a + 1] + (linePos[a + 4] - linePos[a + 1]) * u;
      pp[i * 3 + 2] = linePos[a + 2] + (linePos[a + 5] - linePos[a + 2]) * u;
    }
    pulseGeo.attributes.position.needsUpdate = true;

    // Parallax rotation around origin only (no position drift)
    group.position.set(0, 0, 0);
    group.rotation.y = t * 0.18 + mouseX * 0.45;
    group.rotation.x = mouseY * 0.25 + Math.sin(t * 0.4) * 0.05;
    group.rotation.z = mouseX * 0.08;
    mat.opacity = 0.55 + 0.4 * Math.sin(t * 1.3) * 0.15 + 0.35;
    lineMat.opacity = 0.14 + 0.1 * (0.5 + 0.5 * Math.sin(t * 2));

    renderer.render(scene, camera);
    raf = requestAnimationFrame(frame);
  }
  raf = requestAnimationFrame(frame);

  const destroy = function destroy() {
    cancelAnimationFrame(raf);
    window.removeEventListener("pointermove", onMove);
    ro.disconnect();
    geo.dispose(); lineGeo.dispose(); pulseGeo.dispose();
    mat.dispose(); lineMat.dispose(); pulseMat.dispose();
    renderer.dispose();
    if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
    if (window.__brainAPI) window.__brainAPI = null;
  };
  window.__brainAPI.destroy = destroy;
  return destroy;
}
