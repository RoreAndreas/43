// Outils géométriques du mannequin : « loft » (surface tendue entre des
// sections elliptiques successives) et calcul du tour mesuré au mètre ruban.
import * as THREE from 'three';

const KEYS = ['y', 'rx', 'zf', 'zb', 'cx', 'cz', 'b'];

function norm(r) {
  return { y: r.y, rx: r.rx, zf: r.zf ?? r.rx, zb: r.zb ?? r.zf ?? r.rx, cx: r.cx ?? 0, cz: r.cz ?? 0, b: r.b ?? 0 };
}

function catmull(p0, p1, p2, p3, t) {
  const t2 = t * t, t3 = t2 * t;
  return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
}

/** Densifie la liste de sections par interpolation Catmull-Rom (galbe lisse). */
export function subdivide(rings, sub = 4) {
  const R = rings.map(norm);
  const out = [];
  for (let i = 0; i < R.length - 1; i++) {
    const p0 = R[Math.max(0, i - 1)], p1 = R[i], p2 = R[i + 1], p3 = R[Math.min(R.length - 1, i + 2)];
    for (let s = 0; s < sub; s++) {
      const t = s / sub, r = {};
      for (const k of KEYS) r[k] = catmull(p0[k], p1[k], p2[k], p3[k], t);
      r.rx = Math.max(r.rx, 0.0005); r.zf = Math.max(r.zf, 0.0005); r.zb = Math.max(r.zb, 0.0005);
      out.push(r);
    }
  }
  out.push({ ...R[R.length - 1] });
  return out;
}

/**
 * Points d'une section. Le volume avant (z > 0) et arrière (z < 0) ont des
 * rayons distincts ; `b` ajoute deux galbes avant (poitrine) écartés de `bx`.
 */
export function sectionPoints(r, seg, opts = {}) {
  const pts = [];
  const bx = (opts.bustX ?? 0.085) * (r.rx / 0.158);
  const bw = opts.bustW ?? 0.055;
  for (let j = 0; j < seg; j++) {
    const th = (j / seg) * Math.PI * 2;
    const c = Math.cos(th), s = Math.sin(th);
    const x = r.rx * c;
    let z = (s >= 0 ? r.zf : r.zb) * s;
    if (r.b > 0 && s > 0) {
      const g = Math.exp(-(((x - bx) / bw) ** 2)) + Math.exp(-(((x + bx) / bw) ** 2));
      z += r.b * g * Math.pow(s, 0.8);
    }
    pts.push([r.cx + x, r.cz + z]);
  }
  return pts;
}

/**
 * Construit la surface. `scale(y)` renvoie un facteur radial (mesures du client),
 * `yOffset` place l'origine du maillage sur l'articulation qui le porte.
 */
export function loftGeometry(rings, { seg = 48, sub = 4, scale = null, yOffset = 0, bust = {} } = {}) {
  const R = subdivide(rings, sub).map((r) => {
    if (!scale) return r;
    const k = scale(r.y);
    return { ...r, rx: r.rx * k, zf: r.zf * k, zb: r.zb * k, b: r.b * k };
  });
  const pos = [];
  const idx = [];
  R.forEach((r) => {
    for (const [x, z] of sectionPoints(r, seg, bust)) pos.push(x, r.y - yOffset, z);
  });
  const n = R.length;
  const first = R[0], last = R[n - 1];
  const up = last.y > first.y;
  for (let i = 0; i < n - 1; i++) {
    for (let j = 0; j < seg; j++) {
      const a = i * seg + j, b = i * seg + ((j + 1) % seg);
      const c = (i + 1) * seg + j, d = (i + 1) * seg + ((j + 1) % seg);
      if (up) idx.push(a, c, b, b, c, d);
      else idx.push(a, b, c, b, d, c);
    }
  }
  // Pôles : referment proprement les extrémités.
  const p0 = pos.length / 3;
  pos.push(first.cx, first.y - yOffset - Math.sign(last.y - first.y) * 0.002, first.cz);
  const p1 = pos.length / 3;
  pos.push(last.cx, last.y - yOffset + Math.sign(last.y - first.y) * 0.002, last.cz);
  for (let j = 0; j < seg; j++) {
    const a = j, b = (j + 1) % seg;
    const c = (n - 1) * seg + j, d = (n - 1) * seg + ((j + 1) % seg);
    if (up) { idx.push(p0, a, b); idx.push(p1, d, c); }
    else { idx.push(p0, b, a); idx.push(p1, c, d); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  g.userData.rings = R;
  g.userData.yOffset = yOffset;
  g.userData.bust = bust;
  return g;
}

/** Section interpolée à une hauteur donnée (repère absolu du maillage). */
export function ringAt(geometry, y) {
  const R = geometry.userData.rings;
  const asc = R[R.length - 1].y > R[0].y;
  for (let i = 0; i < R.length - 1; i++) {
    const a = R[i], b = R[i + 1];
    const lo = asc ? a.y : b.y, hi = asc ? b.y : a.y;
    if (y >= lo && y <= hi) {
      const t = (y - a.y) / (b.y - a.y || 1);
      const r = {};
      for (const k of KEYS) r[k] = a[k] + (b[k] - a[k]) * t;
      return r;
    }
  }
  return null;
}

function cross(o, a, b) { return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); }

/** Enveloppe convexe : c'est le trajet réel d'un mètre ruban autour du corps. */
export function convexHull(points) {
  const p = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const lower = [], upper = [];
  for (const q of p) { while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), q) <= 0) lower.pop(); lower.push(q); }
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), q) <= 0) upper.pop(); upper.push(q); }
  upper.pop(); lower.pop();
  return lower.concat(upper);
}

export function perimeter(poly) {
  let L = 0;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length];
    L += Math.hypot(b[0] - a[0], b[1] - a[1]);
  }
  return L;
}

/** Tour de mesure à la hauteur y : contour (x,z) et longueur en mètres. */
export function tapeAt(geometry, y, seg = 96) {
  const r = ringAt(geometry, y);
  if (!r) return null;
  const hull = convexHull(sectionPoints(r, seg, geometry.userData.bust));
  return { hull, length: perimeter(hull), y };
}
