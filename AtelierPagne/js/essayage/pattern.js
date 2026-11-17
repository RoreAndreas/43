// Motif « wax » original, généré en canvas et raccordable (tuile répétable).
// Sert au décor 3D (podium, pagnes exposés) et à l'interface (frises).
import * as THREE from 'three';

export const PALETTES = [
  ['#1f2a44', '#e0a33a', '#c4572e', '#f6efe0'],
  ['#1d4a3a', '#f0c24b', '#d9482b', '#f8f1e2'],
  ['#b5482a', '#1f2a44', '#f0c24b', '#f6efe0'],
  ['#16586a', '#f2b134', '#e05d3a', '#fbf3e3'],
  ['#4a2a5a', '#e8a23a', '#2f8f83', '#f7eedf'],
  ['#d99a2b', '#1f2a44', '#b8402a', '#fff6e5'],
];

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

/** Dessine une tuile de motif. Tout motif qui déborde est redessiné de l'autre côté. */
export function waxTile(palette = PALETTES[0], size = 256, seed = 7) {
  const [c0, c1, c2, c3] = palette;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const x = c.getContext('2d');
  const S = size / 256;
  const wrap = (draw) => {
    for (const dx of [-size, 0, size]) for (const dy of [-size, 0, size]) { x.save(); x.translate(dx, dy); draw(); x.restore(); }
  };
  x.fillStyle = c0; x.fillRect(0, 0, size, size);

  const medallion = (cx, cy, r) => {
    x.fillStyle = c1; x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.fill();
    x.strokeStyle = c2; x.lineWidth = r * 0.16; x.beginPath(); x.arc(cx, cy, r * 0.72, 0, Math.PI * 2); x.stroke();
    x.fillStyle = c3; x.beginPath(); x.arc(cx, cy, r * 0.44, 0, Math.PI * 2); x.fill();
    x.fillStyle = c0; x.beginPath(); x.arc(cx, cy, r * 0.17, 0, Math.PI * 2); x.fill();
    // petits points en couronne
    x.fillStyle = c3;
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      x.beginPath(); x.arc(cx + Math.cos(a) * r * 1.18, cy + Math.sin(a) * r * 1.18, r * 0.06, 0, Math.PI * 2); x.fill();
    }
  };
  const leaf = (cx, cy, ang, len) => {
    x.save(); x.translate(cx, cy); x.rotate(ang);
    x.fillStyle = c3;
    x.beginPath(); x.moveTo(0, 0);
    x.quadraticCurveTo(len * 0.5, -len * 0.32, len, 0);
    x.quadraticCurveTo(len * 0.5, len * 0.32, 0, 0); x.fill();
    x.strokeStyle = c2; x.lineWidth = 2 * S;
    x.beginPath(); x.moveTo(len * 0.12, 0); x.lineTo(len * 0.88, 0); x.stroke();
    x.restore();
  };

  wrap(() => {
    medallion(128 * S, 128 * S, 56 * S);
    for (const [px, py] of [[0, 0], [256, 0], [0, 256], [256, 256]]) medallion(px * S, py * S, 34 * S);
    for (let i = 0; i < 4; i++) {
      const a = Math.PI / 4 + (i * Math.PI) / 2;
      leaf(128 * S + Math.cos(a) * 74 * S, 128 * S + Math.sin(a) * 74 * S, a, 40 * S);
    }
    x.fillStyle = c2;
    for (const [px, py] of [[128, 0], [0, 128], [256, 128], [128, 256]]) {
      x.beginPath(); x.arc(px * S, py * S, 13 * S, 0, Math.PI * 2); x.fill();
      x.fillStyle = c3; x.beginPath(); x.arc(px * S, py * S, 5 * S, 0, Math.PI * 2); x.fill(); x.fillStyle = c2;
    }
  });
  // Craquelures légères, signature visuelle du wax.
  const r = rng(seed);
  x.globalAlpha = 0.22; x.strokeStyle = c0; x.lineWidth = 1.2 * S;
  for (let i = 0; i < 26; i++) {
    let px = r() * size, py = r() * size;
    const pts = [[px, py]];
    for (let k = 0; k < 6; k++) { px += (r() - 0.5) * 34 * S; py += (r() - 0.5) * 34 * S; pts.push([px, py]); }
    wrap(() => { x.beginPath(); pts.forEach(([a, b], k) => (k ? x.lineTo(a, b) : x.moveTo(a, b))); x.stroke(); });
  }
  x.globalAlpha = 1;
  return c;
}

export function waxTexture(palette, repeat = [1, 1], size = 256) {
  const t = new THREE.CanvasTexture(waxTile(palette, size));
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = 8;
  return t;
}
