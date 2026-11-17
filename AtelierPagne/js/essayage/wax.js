// Pagnes wax : six motifs originaux dessinés par le code (tuiles raccordables),
// et import d'une photo du pagne de la cliente.
import * as THREE from 'three';

const S = 512; // taille de la tuile en pixels

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

/** Dessine `draw` neuf fois décalé d'une tuile : les motifs qui débordent se raccordent. */
const wrapDraw = (x, draw) => {
  for (const dx of [-S, 0, S]) for (const dy of [-S, 0, S]) { x.save(); x.translate(dx, dy); draw(); x.restore(); }
};
const circle = (x, cx, cy, r, fill) => { x.fillStyle = fill; x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.fill(); };
const ring = (x, cx, cy, r, w, stroke) => { x.strokeStyle = stroke; x.lineWidth = w; x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.stroke(); };

/** Craquelures fines, signature visuelle de l'impression wax. */
function crackle(x, color, seed, alpha = 0.18) {
  const r = rng(seed);
  x.globalAlpha = alpha; x.strokeStyle = color; x.lineWidth = 1.4;
  for (let i = 0; i < 40; i++) {
    let px = r() * S, py = r() * S;
    const pts = [[px, py]];
    for (let k = 0; k < 7; k++) { px += (r() - 0.5) * 60; py += (r() - 0.5) * 60; pts.push([px, py]); }
    wrapDraw(x, () => { x.beginPath(); pts.forEach(([a, b], k) => (k ? x.lineTo(a, b) : x.moveTo(a, b))); x.stroke(); });
  }
  x.globalAlpha = 1;
}

const DESIGNS = {
  medaillons: { label: 'Médaillons', colors: ['#1d2b55', '#f0b429', '#d64527', '#f7efe0'], draw(x, [a, b, c, d]) {
    x.fillStyle = a; x.fillRect(0, 0, S, S);
    const med = (cx, cy, r) => {
      circle(x, cx, cy, r, b); ring(x, cx, cy, r * 0.72, r * 0.16, c); circle(x, cx, cy, r * 0.44, d); circle(x, cx, cy, r * 0.17, a);
      for (let i = 0; i < 14; i++) { const t = (i / 14) * Math.PI * 2; circle(x, cx + Math.cos(t) * r * 1.2, cy + Math.sin(t) * r * 1.2, r * 0.06, d); }
    };
    wrapDraw(x, () => {
      med(256, 256, 112);
      for (const [px, py] of [[0, 0], [512, 0], [0, 512], [512, 512]]) med(px, py, 70);
      for (const [px, py] of [[256, 0], [0, 256], [512, 256], [256, 512]]) { circle(x, px, py, 26, c); circle(x, px, py, 10, d); }
    });
  } },
  eventails: { label: 'Éventails', colors: ['#0f5b4e', '#f2c14e', '#e2611f', '#fbf3e3'], draw(x, [a, b, c, d]) {
    x.fillStyle = a; x.fillRect(0, 0, S, S);
    const fan = (cx, cy, r) => {
      for (let k = 4; k >= 1; k--) {
        x.fillStyle = [b, c, d, b][k - 1];
        x.beginPath(); x.moveTo(cx, cy); x.arc(cx, cy, (r * k) / 4, Math.PI, 2 * Math.PI); x.closePath(); x.fill();
      }
      x.strokeStyle = a; x.lineWidth = 4;
      for (let i = 1; i < 8; i++) { const t = Math.PI + (i / 8) * Math.PI; x.beginPath(); x.moveTo(cx, cy); x.lineTo(cx + Math.cos(t) * r, cy + Math.sin(t) * r); x.stroke(); }
    };
    wrapDraw(x, () => {
      for (let row = 0; row < 4; row++) for (let col = 0; col < 3; col++) {
        const off = row % 2 ? 85 : 0;
        fan(col * 170 + off + 85, row * 128 + 128, 82);
      }
    });
  } },
  feuillage: { label: 'Feuillage', colors: ['#f4e9d6', '#1f6b3a', '#c2381f', '#21305e'], draw(x, [a, b, c, d]) {
    x.fillStyle = a; x.fillRect(0, 0, S, S);
    const leaf = (cx, cy, ang, len, col) => {
      x.save(); x.translate(cx, cy); x.rotate(ang);
      x.fillStyle = col; x.beginPath(); x.moveTo(0, 0);
      x.quadraticCurveTo(len * 0.5, -len * 0.36, len, 0); x.quadraticCurveTo(len * 0.5, len * 0.36, 0, 0); x.fill();
      x.strokeStyle = a; x.lineWidth = 3; x.beginPath(); x.moveTo(len * 0.08, 0); x.lineTo(len * 0.92, 0); x.stroke();
      for (let i = 1; i < 6; i++) { const t = (i / 6) * len; x.beginPath(); x.moveTo(t, 0); x.lineTo(t + 14, -len * 0.12); x.moveTo(t, 0); x.lineTo(t + 14, len * 0.12); x.stroke(); }
      x.restore();
    };
    const r = rng(5);
    wrapDraw(x, () => {
      for (let i = 0; i < 9; i++) {
        const cx = (i % 3) * 170 + 60 + (Math.floor(i / 3) % 2) * 60, cy = Math.floor(i / 3) * 170 + 70;
        leaf(cx, cy, -0.6 + (i % 2) * 1.6, 150, i % 3 === 0 ? c : b);
        circle(x, cx + 110, cy + 60, 16, d); circle(x, cx + 110, cy + 60, 7, a);
      }
    });
    void r;
  } },
  cauris: { label: 'Cauris', colors: ['#7a1f3d', '#f6d27a', '#fdf6ea', '#2b2a6b'], draw(x, [a, b, c, d]) {
    x.fillStyle = a; x.fillRect(0, 0, S, S);
    const shell = (cx, cy, ang) => {
      x.save(); x.translate(cx, cy); x.rotate(ang);
      x.fillStyle = c; x.beginPath(); x.ellipse(0, 0, 34, 52, 0, 0, Math.PI * 2); x.fill();
      x.fillStyle = b; x.beginPath(); x.ellipse(0, 0, 9, 40, 0, 0, Math.PI * 2); x.fill();
      x.strokeStyle = d; x.lineWidth = 3;
      for (let i = -3; i <= 3; i++) { x.beginPath(); x.moveTo(-8, i * 10); x.lineTo(8, i * 10); x.stroke(); }
      x.restore();
    };
    wrapDraw(x, () => {
      for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
        const cx = col * 128 + (row % 2) * 64 + 32, cy = row * 128 + 64;
        shell(cx, cy, (row + col) % 2 ? 0.5 : -0.5);
      }
      x.strokeStyle = b; x.lineWidth = 6;
      for (let row = 0; row <= 4; row++) { x.beginPath(); x.moveTo(0, row * 128); x.lineTo(S, row * 128); x.stroke(); }
    });
  } },
  soleils: { label: 'Soleils', colors: ['#e8701a', '#1b2240', '#f9d548', '#f8f0e0'], draw(x, [a, b, c, d]) {
    x.fillStyle = a; x.fillRect(0, 0, S, S);
    const sun = (cx, cy, r) => {
      x.fillStyle = b;
      for (let i = 0; i < 16; i++) {
        const t = (i / 16) * Math.PI * 2;
        x.beginPath(); x.moveTo(cx + Math.cos(t - 0.12) * r * 0.62, cy + Math.sin(t - 0.12) * r * 0.62);
        x.lineTo(cx + Math.cos(t) * r, cy + Math.sin(t) * r); x.lineTo(cx + Math.cos(t + 0.12) * r * 0.62, cy + Math.sin(t + 0.12) * r * 0.62); x.fill();
      }
      circle(x, cx, cy, r * 0.62, c); ring(x, cx, cy, r * 0.46, r * 0.08, b); circle(x, cx, cy, r * 0.28, d); circle(x, cx, cy, r * 0.12, b);
    };
    wrapDraw(x, () => {
      sun(128, 128, 110); sun(384, 384, 110);
      for (const [px, py] of [[384, 128], [128, 384]]) { circle(x, px, py, 46, d); ring(x, px, py, 30, 10, b); }
    });
  } },
  losanges: { label: 'Losanges', colors: ['#14233f', '#d9a441', '#b8321f', '#efe6d4'], draw(x, [a, b, c, d]) {
    x.fillStyle = a; x.fillRect(0, 0, S, S);
    const dia = (cx, cy, w, h, col) => { x.fillStyle = col; x.beginPath(); x.moveTo(cx, cy - h); x.lineTo(cx + w, cy); x.lineTo(cx, cy + h); x.lineTo(cx - w, cy); x.closePath(); x.fill(); };
    wrapDraw(x, () => {
      for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
        const cx = col * 128 + (row % 2) * 64 + 32, cy = row * 128 + 64;
        dia(cx, cy, 60, 64, b); dia(cx, cy, 40, 44, c); dia(cx, cy, 20, 24, d);
        circle(x, cx + 64, cy, 7, d);
      }
    });
  } },
};

export const WAX = Object.entries(DESIGNS).map(([id, d]) => ({ id, label: d.label, colors: d.colors }));

const cache = {};
/** Canvas du motif (sert aussi d'aperçu dans l'interface). */
export function waxCanvas(id) {
  if (cache[id]) return cache[id];
  const d = DESIGNS[id];
  const c = document.createElement('canvas');
  c.width = c.height = S;
  const x = c.getContext('2d');
  d.draw(x, d.colors);
  crackle(x, d.colors[0], id.length * 7 + 3);
  cache[id] = c;
  return c;
}

export function waxTexture(id) {
  return configure(new THREE.CanvasTexture(waxCanvas(id)));
}

/** Texture depuis la photo d'un morceau de pagne (répétée en miroir pour masquer les raccords). */
export async function photoTexture(file) {
  const bmp = await createImageBitmap(file);
  const side = Math.min(bmp.width, bmp.height, 1024);
  const c = document.createElement('canvas');
  c.width = c.height = side;
  const sx = (bmp.width - Math.min(bmp.width, bmp.height)) / 2, sy = (bmp.height - Math.min(bmp.width, bmp.height)) / 2;
  c.getContext('2d').drawImage(bmp, sx, sy, Math.min(bmp.width, bmp.height), Math.min(bmp.width, bmp.height), 0, 0, side, side);
  const t = configure(new THREE.CanvasTexture(c));
  t.wrapS = t.wrapT = THREE.MirroredRepeatWrapping;
  return { texture: t, preview: c };
}

function configure(t) {
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  t.generateMipmaps = true;
  return t;
}
