// Robe importée (Blender → assets/garments/<nom>.bin, voir tools/convert_garment.py).
//
// Principe (celui des jeux vidéo et des cabines virtuelles) :
// 1. Ajustement : la robe garde la coupe et le volume dessinés dans Blender.
//    Elle est seulement mise à l'échelle du mannequin (hauteur, tour), puis
//    corrigée localement là où le corps la traverserait.
// 2. Le haut (bustier, bandeau) reprend les poids du point de peau le plus
//    proche : il suit chaque mouvement du torse et des bras.
// 3. La jupe est portée par des « chaînes » d'os réparties tout autour, à
//    ressort : elle se balance, s'évase quand le mannequin tourne, s'écarte des
//    jambes et des mains, se pose sur les cuisses en position assise. Les deux
//    bords de la fente sont portés par des chaînes différentes : elle s'ouvre.
// Tout le maillage est déformé par la carte graphique ; le processeur ne calcule
// qu'une centaine de points : fluide sur téléphone, aucun tremblement.
// L'ajustement est mémorisé par robe, silhouette et mesures.
import * as THREE from 'three';

const DATA = {};

export async function loadDresses(names, base = 'assets/garments/') {
  await Promise.all(names.map(async (name) => {
    const [meta, bin] = await Promise.all([
      fetch(`${base}${name}.json`).then((r) => r.json()),
      fetch(`${base}${name}.bin`).then((r) => r.arrayBuffer()),
    ]);
    let o = 0;
    const uniq = new Float32Array(bin, o, meta.particles * 3); o += meta.particles * 12;
    const rv = new Uint32Array(bin, o, meta.renderVertices); o += meta.renderVertices * 4;
    const uv = new Float32Array(bin, o, meta.renderVertices * 2); o += meta.renderVertices * 8;
    const tris = new Uint32Array(bin, o, meta.triangles * 3);
    DATA[name] = { meta, uniq, rv, uv, tris };
  }));
}

export const hasDress = (name) => !!DATA[name];

const ss = THREE.MathUtils.smoothstep;
const NA = 64; // résolution angulaire des tables de rayons
const K = 16; // chaînes autour de la jupe
const L = 6; // segments par chaîne

/** Enveloppe convexe 2D, centre, périmètre et rayon par angle (table de NA valeurs). */
function section(points) {
  if (points.length < 6) return null;
  const p = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const q of p) { while (lo.length >= 2 && cr(lo.at(-2), lo.at(-1), q) <= 0) lo.pop(); lo.push(q); }
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cr(up.at(-2), up.at(-1), q) <= 0) up.pop(); up.push(q); }
  const hull = lo.slice(0, -1).concat(up.slice(0, -1));
  let xmin = Infinity, xmax = -Infinity, zmin = Infinity, zmax = -Infinity, per = 0;
  for (let i = 0; i < hull.length; i++) {
    const [x, z] = hull[i], [x2, z2] = hull[(i + 1) % hull.length];
    xmin = Math.min(xmin, x); xmax = Math.max(xmax, x); zmin = Math.min(zmin, z); zmax = Math.max(zmax, z);
    per += Math.hypot(x2 - x, z2 - z);
  }
  const c = [(xmin + xmax) / 2, (zmin + zmax) / 2];
  const radii = new Float32Array(NA);
  for (let k = 0; k < NA; k++) {
    const th = (k / NA) * Math.PI * 2, dx = Math.sin(th), dz = Math.cos(th);
    let best = 0;
    for (let i = 0; i < hull.length; i++) {
      const a = hull[i], b = hull[(i + 1) % hull.length];
      const ex = b[0] - a[0], ez = b[1] - a[1];
      const den = dx * ez - dz * ex;
      if (Math.abs(den) < 1e-9) continue;
      const t = ((a[0] - c[0]) * ez - (a[1] - c[1]) * ex) / den;
      const u = ((a[0] - c[0]) * dz - (a[1] - c[1]) * dx) / den;
      if (t > 0 && u >= -1e-6 && u <= 1 + 1e-6) best = Math.max(best, t);
    }
    radii[k] = best;
  }
  return { c, radii, per };
}
const radiusAt = (sec, dx, dz) => {
  let a = Math.atan2(dx, dz) / (Math.PI * 2);
  if (a < 0) a += 1;
  const f = a * NA, k = f | 0, w = f - k;
  return sec.radii[k % NA] * (1 - w) + sec.radii[(k + 1) % NA] * w;
};

// ---------- Grille spatiale (clés numériques) ----------
const CELL = 0.03;
const ck = (ix, iy, iz) => ((ix + 1024) * 2048 + (iy + 1024)) * 2048 + (iz + 1024);
function makeGrid(pos, count, keep) {
  const g = new Map();
  for (let i = 0; i < count; i++) {
    if (!keep(i)) continue;
    const k = ck(Math.floor(pos[i * 3] / CELL), Math.floor(pos[i * 3 + 1] / CELL), Math.floor(pos[i * 3 + 2] / CELL));
    let l = g.get(k);
    if (!l) g.set(k, (l = []));
    l.push(i);
  }
  return g;
}
function nearestIn(grid, pos, x, y, z) {
  const cx = Math.floor(x / CELL), cy = Math.floor(y / CELL), cz = Math.floor(z / CELL);
  for (let r = 1; r < 8; r++) {
    let best = -1, bd = Infinity;
    for (let a = -r; a <= r; a++) for (let b = -r; b <= r; b++) for (let c = -r; c <= r; c++) {
      const l = grid.get(ck(cx + a, cy + b, cz + c));
      if (!l) continue;
      for (const i of l) {
        const dx = pos[i * 3] - x, dy = pos[i * 3 + 1] - y, dz = pos[i * 3 + 2] - z;
        const d = dx * dx + dy * dy + dz * dz;
        if (d < bd) { bd = d; best = i; }
      }
    }
    if (best >= 0) return best;
  }
  return 0;
}

// ---------- Ajustement (résultat mis en cache) ----------
const FITS = new Map();

function fitDress(body, name) {
  const key = `${name}|${body.sex}|${JSON.stringify(body.cm || {})}`;
  if (FITS.has(key)) return FITS.get(key);
  const D = DATA[name];
  const J = body.restJ, lm = body.lm;
  const n = D.meta.particles;
  const P0 = D.uniq, tris = D.tris, rv = D.rv;
  const BIN = 0.01;

  // Voisinage du tissu.
  const nbr = Array.from({ length: n }, () => []);
  const seen = new Set();
  for (let t = 0; t < tris.length; t += 3) {
    const v = [rv[tris[t]], rv[tris[t + 1]], rv[tris[t + 2]]];
    for (let e = 0; e < 3; e++) {
      const a = v[e], b = v[(e + 1) % 3];
      if (a === b) continue;
      const k = a < b ? a * n + b : b * n + a;
      if (seen.has(k)) continue;
      seen.add(k);
      nbr[a].push(b); nbr[b].push(a);
    }
  }

  // ---------- 1. Mise à l'échelle (la coupe d'origine est conservée) ----------
  const sliceOf = (arr, count, keep = () => true) => {
    const m = new Map();
    for (let i = 0; i < count; i++) {
      if (!keep(i)) continue;
      const k = Math.round(arr[i * 3 + 1] / BIN);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push([arr[i * 3], arr[i * 3 + 2]]);
    }
    return m;
  };
  let top = -Infinity, hem = Infinity;
  for (let i = 0; i < n; i++) { top = Math.max(top, P0[i * 3 + 1]); hem = Math.min(hem, P0[i * 3 + 1]); }
  const dS = sliceOf(P0, n);
  const dSec = (y) => section(dS.get(Math.round(y / BIN)) || []);
  // taille et haut du bustier du modèle (saut de largeur : le bandeau commence)
  let dWaist = hem, best = Infinity;
  for (let y = hem + (top - hem) * 0.7; y < hem + (top - hem) * 0.92; y += BIN) { const s = dSec(y); if (s && s.per < best) { best = s.per; dWaist = y; } }
  let dBodice = top;
  for (let y = dWaist + 0.04; y < top; y += BIN) { const a = dSec(y), b = dSec(y + 0.02); if (a && b && b.per > a.per * 1.22) { dBodice = y; break; } }
  // vertical : une seule échelle, ourlet au ras du sol, bustier sous le bandeau
  const bandY = lm.bust + 0.032;
  const HEM = 0.022; // ourlet à 2 cm du sol : il ne se coince pas sous les pieds
  const sy = (bandY - HEM) / (dBodice - hem);
  const mapY = (y) => HEM + (y - hem) * sy;

  // horizontal : une seule échelle, donnée par le tour du corps entre hanches et poitrine
  const rp = body.restPos;
  const geo = body.body.geometry;
  const SI = geo.attributes.skinIndex.array, SW = geo.attributes.skinWeight.array;
  const bi = body.bi;
  const nb = rp.length / 3;
  const wOf = (i, ids) => { let w = 0; for (let c = 0; c < 4; c++) if (ids.includes(SI[i * 4 + c])) w += SW[i * 4 + c] / 255; return w; };
  const exclude = [bi.Head, bi.LeftHand, bi.RightHand, bi.LeftForeArm, bi.RightForeArm];
  const armIds = [bi.LeftArm, bi.RightArm];
  const torsoKeep = (i) => wOf(i, exclude) < 0.3 && wOf(i, armIds) < 0.3;
  const bandKeep = (i) => wOf(i, exclude) < 0.3;
  const bS = sliceOf(rp, nb, torsoKeep);
  const bSec = (y) => section(bS.get(Math.round(y / BIN)) || []);
  const ratios = [];
  let bzSum = 0, dzSum = 0, cnt = 0;
  for (let y = lm.hip; y <= lm.bust; y += BIN) {
    const b = bSec(y);
    const d = dSec(hem + (y - HEM) / sy); // hauteur correspondante dans la robe d'origine
    if (!b || !d) continue;
    ratios.push((b.per + 2 * Math.PI * 0.008) / d.per);
    bzSum += b.c[1]; dzSum += d.c[1]; cnt++;
  }
  const sorted = ratios.map((r) => r).sort((a, b) => a - b);
  const sx = THREE.MathUtils.clamp(sorted[Math.floor(sorted.length / 2)] ?? 1, 0.7, 1.6);
  const bz = cnt ? bzSum / cnt : 0, dz = cnt ? dzSum / cnt : 0;
  // Là où le corps est plus large que la robe (hanches galbées…), la robe est
  // élargie en douceur sur toute la hauteur concernée, sans jamais rétrécir.
  const need = new Map();
  for (let y = J.LeftUpLeg.y - 0.08; y <= lm.bust + 0.02; y += BIN) {
    const b = bSec(y), d = dSec(hem + (y - HEM) / sy);
    if (b && d) need.set(Math.round(y / BIN), Math.max(sx, (b.per + 2 * Math.PI * 0.01) / d.per));
  }
  const kLo = Math.round((J.LeftUpLeg.y - 0.08) / BIN), kHi = Math.round((lm.bust + 0.02) / BIN);
  const scaleAt = (y) => {
    const k = THREE.MathUtils.clamp(Math.round(y / BIN), kLo, kHi);
    let acc = 0, w = 0;
    for (let d = -15; d <= 15; d++) {
      const v = need.get(THREE.MathUtils.clamp(k + d, kLo, kHi));
      if (v === undefined) continue;
      const ww = 16 - Math.abs(d);
      acc += v * ww; w += ww;
    }
    return w ? Math.max(sx, acc / w) : sx;
  };
  const P = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const y = mapY(P0[i * 3 + 1]);
    const k = scaleAt(y);
    P[i * 3] = P0[i * 3] * k;
    P[i * 3 + 1] = y;
    P[i * 3 + 2] = bz + (P0[i * 3 + 2] - dz) * k;
  }

  // ---------- 1 bis. Sous la taille, la jupe suit le corps ----------
  // Chaque tranche de jupe est recentrée sur la tranche du corps (cambrure,
  // fesses), puis élargie juste assez pour contenir le corps et les deux jambes,
  // aisance comprise. Décalage et élargissement sont lissés sur la hauteur :
  // la jupe garde son tombé, sans bosse ni marche.
  {
    const pS = new Map();
    for (let i = 0; i < n; i++) {
      const k = Math.round(P[i * 3 + 1] / BIN);
      if (!pS.has(k)) pS.set(k, []);
      pS.get(k).push(i);
    }
    const kWaist = Math.round(lm.waist / BIN);
    const ks = [...pS.keys()].filter((k) => k <= kWaist + 4).sort((a, b) => a - b);
    const smoothMap = (m, win) => {
      const out = new Map();
      for (const k of ks) {
        let acc = 0, w = 0;
        for (let d = -win; d <= win; d++) { const v = m.get(k + d); if (v !== undefined) { const ww = win + 1 - Math.abs(d); acc += v * ww; w += ww; } }
        out.set(k, w ? acc / w : (m.get(k) ?? 0));
      }
      return out;
    };
    // a) décalage : centre du corps − centre de la jupe (sans le haut du buste)
    const sx2 = new Map(), sz2 = new Map();
    let lastX = 0, lastZ = 0;
    for (const k of ks) {
      const sk = section(pS.get(k).map((i) => [P[i * 3], P[i * 3 + 2]]));
      const bs = bSec(k * BIN);
      if (sk && bs) { lastX = bs.c[0] - sk.c[0]; lastZ = bs.c[1] - sk.c[1]; }
      sx2.set(k, lastX); sz2.set(k, lastZ);
    }
    const shX = smoothMap(sx2, 8), shZ = smoothMap(sz2, 8);
    for (const k of ks) {
      const fade = 1 - ss(k * BIN, lm.waist - 0.02, lm.waist + 0.04); // rien au-dessus de la taille
      for (const i of pS.get(k)) { P[i * 3] += shX.get(k) * fade; P[i * 3 + 2] += shZ.get(k) * fade; }
    }
    // b) là où le corps dépasse (dans une direction donnée), la jupe est poussée
    //    vers l'extérieur dans cette direction seulement ; la poussée est lissée
    //    autour de la jupe (±25°) et sur la hauteur (±7 cm).
    const def = new Map(), centers = new Map();
    for (const k of ks) {
      if (k * BIN > lm.hip + 0.04) continue;
      const sk = section(pS.get(k).map((i) => [P[i * 3], P[i * 3 + 2]]));
      const pts = bS.get(k);
      if (!sk || !pts) continue;
      centers.set(k, sk.c);
      const dk = new Float32Array(NA);
      for (const [x, z] of pts) {
        const dx = x - sk.c[0], dz = z - sk.c[1], d = Math.hypot(dx, dz);
        if (d < 1e-6) continue;
        let a2 = Math.atan2(dx / d, dz / d) / (Math.PI * 2);
        if (a2 < 0) a2 += 1;
        const j = Math.round(a2 * NA) % NA;
        dk[j] = Math.max(dk[j], d + 0.012 - radiusAt(sk, dx / d, dz / d));
      }
      // autour de la jupe : dilatation puis moyenne
      const dil = new Float32Array(NA), sm = new Float32Array(NA);
      for (let j = 0; j < NA; j++) { let m = 0; for (let q = -2; q <= 2; q++) m = Math.max(m, dk[(j + q + NA) % NA]); dil[j] = m; }
      for (let j = 0; j < NA; j++) { let acc = 0; for (let q = -4; q <= 4; q++) acc += dil[(j + q + NA) % NA]; sm[j] = acc / 9; }
      def.set(k, sm);
    }
    // sur la hauteur : dilatation puis moyenne
    const defH = new Map();
    for (const k of def.keys()) {
      const out = new Float32Array(NA);
      for (let j = 0; j < NA; j++) {
        let acc = 0, w = 0;
        for (let d = -7; d <= 7; d++) {
          let m = 0;
          for (let e = -3; e <= 3; e++) { const v = def.get(k + d + e); if (v) m = Math.max(m, v[j]); }
          acc += m; w++;
        }
        out[j] = acc / w;
      }
      defH.set(k, out);
    }
    for (const [k, dk] of defH) {
      const c = centers.get(k);
      const fade = 1 - ss(k * BIN, lm.hip - 0.02, lm.hip + 0.04);
      for (const i of pS.get(k)) {
        const dx = P[i * 3] - c[0], dz = P[i * 3 + 2] - c[1], d = Math.hypot(dx, dz);
        if (d < 1e-6) continue;
        let a2 = Math.atan2(dx / d, dz / d) / (Math.PI * 2);
        if (a2 < 0) a2 += 1;
        const fj = a2 * NA, j0 = Math.floor(fj) % NA, w = fj - Math.floor(fj);
        const push = (dk[j0] * (1 - w) + dk[(j0 + 1) % NA] * w) * fade;
        if (push <= 0) continue;
        P[i * 3] += (dx / d) * push; P[i * 3 + 2] += (dz / d) * push;
      }
    }
  }

  // ---------- 2. Correction locale : jamais dans le corps ----------
  const gridTorso = makeGrid(rp, nb, torsoKeep), gridBand = makeGrid(rp, nb, bandKeep);
  const gridFor = (y) => (y > bandY - 0.005 ? gridBand : gridTorso);
  const BN = new Float32Array(geo.attributes.normal.array);
  {
    const bidx = geo.index.array;
    for (let it = 0; it < 2; it++) {
      const acc = new Float32Array(BN);
      for (let t = 0; t < bidx.length; t += 3) {
        for (let e = 0; e < 3; e++) {
          const a = bidx[t + e], b = bidx[t + (e + 1) % 3];
          for (let c = 0; c < 3; c++) { acc[a * 3 + c] += BN[b * 3 + c]; acc[b * 3 + c] += BN[a * 3 + c]; }
        }
      }
      for (let i = 0; i < nb; i++) {
        const l = Math.hypot(acc[i * 3], acc[i * 3 + 1], acc[i * 3 + 2]) || 1;
        BN[i * 3] = acc[i * 3] / l; BN[i * 3 + 1] = acc[i * 3 + 1] / l; BN[i * 3 + 2] = acc[i * 3 + 2] / l;
      }
    }
  }
  for (let pass = 0; pass < 3; pass++) {
    const off = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
      const j = nearestIn(gridFor(y), rp, x, y, z);
      const nx = BN[j * 3], ny = BN[j * 3 + 1], nz = BN[j * 3 + 2];
      const sd = (x - rp[j * 3]) * nx + (y - rp[j * 3 + 1]) * ny + (z - rp[j * 3 + 2]) * nz;
      const want = y > bandY ? (wOf(j, armIds) > 0.5 ? 0.007 : 0.012) : 0.008;
      if (sd < want) { const k = want - sd; off[i * 3] = nx * k; off[i * 3 + 1] = ny * k * 0.3; off[i * 3 + 2] = nz * k; }
    }
    // la correction se fond dans le tissu voisin (pas de bosse locale)
    for (let it = 0; it < 6; it++) {
      const o2 = new Float32Array(off);
      for (let i = 0; i < n; i++) {
        const nb2 = nbr[i];
        if (!nb2.length) continue;
        for (let c = 0; c < 3; c++) {
          let m = 0;
          for (const j of nb2) m += off[j * 3 + c];
          m /= nb2.length;
          o2[i * 3 + c] = Math.abs(m) > Math.abs(off[i * 3 + c]) ? m : off[i * 3 + c];
        }
      }
      off.set(o2);
    }
    for (let i = 0; i < n * 3; i++) P[i] += off[i];
  }

  // ---------- 3. Chaînes de la jupe ----------
  const yRoot = lm.hip;
  const hipSec = section(sliceOf(P, n).get(Math.round(yRoot / BIN)) || []);
  const cx = hipSec ? hipSec.c[0] : 0, cz = hipSec ? hipSec.c[1] : bz;
  const ang = (x, z) => Math.atan2(x - cx, z - cz);
  // fente : bords libres de la jupe nettement au-dessus de l'ourlet
  const chains = boundaryChains(tris, rv, n);
  let slit = null;
  {
    let ax = 0, az = 0, topY = -Infinity, c = 0;
    for (const ch of chains) for (const p of ch) {
      const y = P[p * 3 + 1];
      if (y > 0.12 && y < yRoot - 0.02) { const a = ang(P[p * 3], P[p * 3 + 2]); ax += Math.sin(a); az += Math.cos(a); topY = Math.max(topY, y); c++; }
    }
    if (c > 6) slit = { theta: Math.atan2(ax, az), top: topY };
  }
  const theta0 = slit ? slit.theta : Math.PI; // la découpe angulaire passe par la fente (ou le dos)
  const uOf = (a) => { let u = (a - theta0) / (Math.PI * 2); u -= Math.floor(u); return u; };
  const segLen = (yRoot - HEM) / L;
  // repos des articulations : centre des points de la jupe du secteur, à chaque hauteur
  const restJ = new Float32Array(K * (L + 1) * 3);
  for (let j = 0; j < K; j++) {
    const uj = (j + 0.5) / K;
    for (let k = 0; k <= L; k++) {
      const yk = yRoot - k * segLen;
      let sxk = 0, szk = 0, m = 0;
      for (let i = 0; i < n; i++) {
        if (Math.abs(P[i * 3 + 1] - yk) > segLen * 0.35) continue;
        let du = uOf(ang(P[i * 3], P[i * 3 + 2])) - uj;
        du -= Math.round(du);
        if (Math.abs(du) > 0.5 / K) continue;
        sxk += P[i * 3]; szk += P[i * 3 + 2]; m++;
      }
      const o = (j * (L + 1) + k) * 3;
      if (m) { restJ[o] = sxk / m; restJ[o + 2] = szk / m; }
      else if (k) { restJ[o] = restJ[o - 3]; restJ[o + 2] = restJ[o - 1]; }
      restJ[o + 1] = yk;
    }
  }

  // ---------- 4. Poids ----------
  const NBB = body.body.skeleton.bones.length;
  const NBT = NBB + K * L;
  const Wd = new Float32Array(n * NBT);
  const chainBone = (j, k) => NBB + j * L + Math.min(k, L - 1);
  const wrap = (j) => ((j % K) + K) % K;
  for (let i = 0; i < n; i++) {
    const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
    // part « chaînes » : 0 au-dessus des hanches, 1 en dessous
    const c = ss(yRoot - y, -0.03, 0.06);
    if (c < 1) {
      const jn = nearestIn(gridFor(y), rp, x, y, z);
      for (let q = 0; q < 4; q++) Wd[i * NBT + SI[jn * 4 + q]] += (SW[jn * 4 + q] / 255) * (1 - c);
    }
    if (c > 0) {
      const kf = Math.max(0, (yRoot - y) / segLen);
      const k0 = Math.min(L - 1, Math.floor(kf)), t = Math.min(1, kf - k0);
      const f = uOf(ang(x, z)) * K - 0.5;
      const j0 = Math.floor(f), w = f - j0, j1 = j0 + 1;
      // sous le haut de la fente, la jupe est « ouverte » : pas d'interpolation à travers
      const open = slit ? ss(slit.top + 0.02 - y, 0, 0.04) : 0;
      const pairs = [];
      if (j0 < 0 || j1 >= K) {
        const edge = j0 < 0 ? 0 : K - 1;
        pairs.push([edge, open], [wrap(j0), (1 - open) * (1 - w)], [wrap(j1), (1 - open) * w]);
      } else pairs.push([j0, 1 - w], [j1, w]);
      for (const [j, wj] of pairs) {
        if (wj <= 0) continue;
        Wd[i * NBT + chainBone(j, k0)] += c * wj * (k0 === L - 1 ? 1 : 1 - t);
        if (k0 < L - 1) Wd[i * NBT + chainBone(j, k0 + 1)] += c * wj * t;
      }
    }
  }
  // le bandeau se déforme en douceur avec les bras
  for (let it = 0; it < 5; it++) {
    const Wn = new Float32Array(Wd);
    for (let i = 0; i < n; i++) {
      if (P[i * 3 + 1] <= bandY + 0.008) continue;
      const nb2 = nbr[i];
      if (!nb2.length) continue;
      for (let b = 0; b < NBB; b++) {
        let acc = 0;
        for (const j of nb2) acc += Wd[j * NBT + b];
        Wn[i * NBT + b] = Wd[i * NBT + b] * 0.4 + (acc / nb2.length) * 0.6;
      }
    }
    Wd.set(Wn);
  }
  const si = new Uint16Array(n * 4), sw = new Float32Array(n * 4);
  const row = [];
  for (let i = 0; i < n; i++) {
    row.length = 0;
    for (let b = 0; b < NBT; b++) { const w = Wd[i * NBT + b]; if (w > 1e-4) row.push([b, w]); }
    row.sort((a, b) => b[1] - a[1]);
    const top4 = row.slice(0, 4);
    const sum = top4.reduce((s2, e) => s2 + e[1], 0) || 1;
    top4.forEach(([b, w], q) => { si[i * 4 + q] = b; sw[i * 4 + q] = w / sum; });
  }

  // ---------- Tables (bras, collisions) ----------
  const dressTab = new Map();
  for (const [k, pts] of sliceOf(P, n)) { const s = section(pts); if (s) dressTab.set(k, s); }
  const legR = (side, yy) => {
    const c = J[`${side}UpLeg`];
    let m = 0;
    for (let i = 0; i < nb; i++) {
      const px = rp[i * 3];
      if (Math.sign(px) !== (side === 'Left' ? 1 : -1) || Math.abs(rp[i * 3 + 1] - yy) > 0.01 || wOf(i, exclude) > 0.3 || wOf(i, armIds) > 0.3) continue;
      m = Math.max(m, Math.hypot(px - c.x, rp[i * 3 + 2] - c.z));
    }
    return m || 0.05;
  };
  const legRadii = ['Left', 'Right'].map((side) => ({
    side,
    thigh: [Math.max(legR(side, J[`${side}UpLeg`].y - 0.12), legR(side, J[`${side}UpLeg`].y - 0.2)), legR(side, J[`${side}Leg`].y + 0.04)],
    calf: [legR(side, J[`${side}Leg`].y - 0.08), legR(side, J[`${side}Foot`].y + 0.08)],
  }));

  const fit = { P, si, sw, restJ, slit, cx, cz, yRoot, dressTab, legRadii, chains, BIN };
  FITS.set(key, fit);
  if (FITS.size > 12) FITS.delete(FITS.keys().next().value);
  return fit;
}

const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _q = new THREE.Quaternion();
const _s = new THREE.Vector3(), _m = new THREE.Matrix4(), _qi = new THREE.Quaternion();

export class DressCloth {
  constructor(body, name, material, scene) {
    const D = DATA[name];
    this.body = body;
    const fit = fitDress(body, name);
    Object.assign(this, fit);
    const { P } = fit;
    const n = D.meta.particles;
    const tris = D.tris, rv = D.rv, uv = D.uv;
    this.tris = tris; this.rv = rv; // (export des tombés : tools/bake)
    this.hipsRest = body.restJ.Hips.clone();
    this.legFreedom = 0.85;
    this.bi = body.bi;

    // Os du corps au repos (racine à l'origine) → matrices inverses.
    const bones = body.body.skeleton.bones;
    this.bodyBones = bones;
    const saved = bones.map((b) => b.quaternion.clone());
    const savedRoot = [body.root.position.clone(), body.root.quaternion.clone(), body.root.scale.clone()];
    body.root.position.set(0, 0, 0); body.root.quaternion.identity(); body.root.scale.set(1, 1, 1);
    bones.forEach((b) => b.quaternion.copy(body.rest[b.name]));
    body.root.updateMatrixWorld(true);
    this.restInv = bones.map((b) => b.matrixWorld.clone().invert());
    this.hipsRestQinv = bones[this.bi.Hips].getWorldQuaternion(new THREE.Quaternion()).invert();
    bones.forEach((b, i) => b.quaternion.copy(saved[i]));
    body.root.position.copy(savedRoot[0]); body.root.quaternion.copy(savedRoot[1]); body.root.scale.copy(savedRoot[2]);
    body.root.updateMatrixWorld(true);

    // Os des chaînes : hors de la scène, leur matrice est écrite à chaque image.
    this.chainBones = [];
    const chainInv = [];
    for (let j = 0; j < K; j++) for (let k = 0; k < L; k++) {
      const b = new THREE.Bone();
      b.matrixAutoUpdate = false;
      b.matrixWorldAutoUpdate = false;
      this.chainBones.push(b);
      const o = (j * (L + 1) + k) * 3;
      chainInv.push(new THREE.Matrix4().makeTranslation(-this.restJ[o], -this.restJ[o + 1], -this.restJ[o + 2]));
    }
    this.skeleton = new THREE.Skeleton([...bones, ...this.chainBones], [...this.restInv.map((m) => m.clone()), ...chainInv]);

    // Normales de repos par point (pas de lignes d'ombre aux coutures du patron).
    const restN = new Float32Array(n * 3);
    for (let t = 0; t < tris.length; t += 3) {
      const a = rv[tris[t]] * 3, b = rv[tris[t + 1]] * 3, c = rv[tris[t + 2]] * 3;
      const ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2];
      const vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      for (const v of [a, b, c]) { restN[v] += nx; restN[v + 1] += ny; restN[v + 2] += nz; }
    }
    for (let i = 0; i < n; i++) {
      const l = Math.hypot(restN[i * 3], restN[i * 3 + 1], restN[i * 3 + 2]) || 1;
      restN[i * 3] /= l; restN[i * 3 + 1] /= l; restN[i * 3 + 2] /= l;
    }

    // ---------- Maillage de la robe (une pièce, déformée par la carte graphique) ----------
    const m = rv.length;
    const pos = new Float32Array(m * 3), nrm = new Float32Array(m * 3), skI = new Uint16Array(m * 4), skW = new Float32Array(m * 4);
    for (let r = 0; r < m; r++) {
      const p = rv[r];
      pos.set([P[p * 3], P[p * 3 + 1], P[p * 3 + 2]], r * 3);
      nrm.set([restN[p * 3], restN[p * 3 + 1], restN[p * 3 + 2]], r * 3);
      for (let q = 0; q < 4; q++) { skI[r * 4 + q] = this.si[p * 4 + q]; skW[r * 4 + q] = this.sw[p * 4 + q]; }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
    g.setAttribute('fabricUv', new THREE.BufferAttribute(new Float32Array(uv), 2));
    g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(uv), 2)); // grain du tissage
    g.setAttribute('skinIndex', new THREE.BufferAttribute(skI, 4));
    g.setAttribute('skinWeight', new THREE.BufferAttribute(skW, 4));
    g.setIndex(new THREE.BufferAttribute(new Uint32Array(tris), 1));
    this.mesh = new THREE.SkinnedMesh(g, material);
    this.mesh.castShadow = this.mesh.receiveShadow = true;
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
    this.mesh.bind(this.skeleton, new THREE.Matrix4());

    // ---------- Ourlet roulé (bas et bords de la fente) ----------
    const puv = new Float32Array(n * 2);
    for (let r = 0; r < m; r++) { puv[rv[r] * 2] = uv[r * 2]; puv[rv[r] * 2 + 1] = uv[r * 2 + 1]; }
    const hemChains = this.chains.filter((ch) => ch.some((p) => P[p * 3 + 1] < this.yRoot - 0.05));
    if (hemChains.length) {
      const tube = new EdgeTube(hemChains, puv, 0.0035);
      tube.write(P, restN);
      const tg = tube.geometry;
      const tI = new Uint16Array(tube.count * 4), tW = new Float32Array(tube.count * 4);
      tube.forEachVertex((v, p) => { for (let q = 0; q < 4; q++) { tI[v * 4 + q] = this.si[p * 4 + q]; tW[v * 4 + q] = this.sw[p * 4 + q]; } });
      tg.setAttribute('skinIndex', new THREE.BufferAttribute(tI, 4));
      tg.setAttribute('skinWeight', new THREE.BufferAttribute(tW, 4));
      this.hem = new THREE.SkinnedMesh(tg, material);
      this.hem.castShadow = true;
      this.hem.frustumCulled = false;
      scene.add(this.hem);
      this.hem.bind(this.skeleton, new THREE.Matrix4());
    }

    // ---------- Chaînes : points simulés ----------
    const NJ = K * (L + 1);
    this.cp = new Float32Array(NJ * 3); // positions
    this.cq = new Float32Array(NJ * 3); // positions précédentes
    this.ct = new Float32Array(NJ * 3); // cibles
    this.segRest = new Float32Array(K * L);
    for (let j = 0; j < K; j++) for (let k = 0; k < L; k++) {
      const a = (j * (L + 1) + k) * 3, b = a + 3;
      this.segRest[j * L + k] = Math.hypot(this.restJ[b] - this.restJ[a], this.restJ[b + 1] - this.restJ[a + 1], this.restJ[b + 2] - this.restJ[a + 2]);
    }
    // le devant de la jupe suit les cuisses (assise, marche) ; le dos et les côtés, le bassin
    this.front = new Float32Array(NJ);
    this.side = new Float32Array(NJ); // 1 = jambe gauche, 0 = droite
    for (let j = 0; j < K; j++) for (let k = 0; k <= L; k++) {
      const o = j * (L + 1) + k;
      const x = this.restJ[o * 3], z = this.restJ[o * 3 + 2];
      const a = Math.atan2(x - this.cx, z - this.cz);
      this.front[o] = THREE.MathUtils.clamp(Math.cos(a) * 1.4, 0, 1) * ss(k / L, 0, 0.18) * 0.95;
      this.side[o] = ss(x, -0.05, 0.05);
    }
    this.caps = new Float64Array(8 * 14);
    // Dégagement au repos entre chaque point et chaque jambe : la collision ne
    // repousse jamais la jupe dans sa forme dessinée, seulement quand une jambe
    // s'en approche (marche, assise).
    this.clear = new Float32Array(NJ * 8).fill(Infinity);
    {
      const RJ = body.restJ;
      const segs = { 0: ['LeftUpLeg', 'LeftLeg'], 1: ['LeftLeg', 'LeftFoot'], 4: ['RightUpLeg', 'RightLeg'], 5: ['RightLeg', 'RightFoot'] };
      for (let i = 0; i < NJ; i++) {
        const p = new THREE.Vector3(this.restJ[i * 3], this.restJ[i * 3 + 1], this.restJ[i * 3 + 2]);
        for (const [c, [a, b]] of Object.entries(segs)) {
          const d = new THREE.Line3(RJ[a], RJ[b]).closestPointToPoint(p, true, new THREE.Vector3()).distanceTo(p);
          this.clear[i * 8 + +c] = Math.max(0.01, d - 0.004);
        }
      }
    }
    this.hipsQ = new THREE.Quaternion();
    this.reset();
  }

  /** Cibles des chaînes : jupe au repos portée par le bassin (et les cuisses devant). */
  computeTargets(env = {}) {
    const B = this.bodyBones, bi = this.bi, inv = this.restInv;
    const M = (b) => _m.multiplyMatrices(B[b].matrixWorld, inv[b]).elements.slice();
    const H = M(bi.Hips);
    const legs = [[M(bi.LeftUpLeg), M(bi.LeftLeg)], [M(bi.RightUpLeg), M(bi.RightLeg)]];
    const kneeY = this.body.restJ.LeftLeg.y;
    const R = this.restJ, T = this.ct;
    const s = this.body.root.scale.x;
    const spin = env.spin || 0;
    const ax = H[0] * this.cx + H[8] * this.cz + H[12], az = H[2] * this.cx + H[10] * this.cz + H[14];
    const acc = [0, 0, 0];
    const apply = (e, x, y, z, w) => {
      acc[0] += w * (e[0] * x + e[4] * y + e[8] * z + e[12]);
      acc[1] += w * (e[1] * x + e[5] * y + e[9] * z + e[13]);
      acc[2] += w * (e[2] * x + e[6] * y + e[10] * z + e[14]);
    };
    for (let j = 0; j < K; j++) for (let k = 0; k <= L; k++) {
      const o = j * (L + 1) + k;
      const x = R[o * 3], y = R[o * 3 + 1], z = R[o * 3 + 2];
      const f = this.front[o], wl = this.side[o];
      acc[0] = acc[1] = acc[2] = 0;
      apply(H, x, y, z, 1 - f);
      if (f > 0) {
        const li = y > kneeY ? 0 : 1;
        apply(legs[0][li], x, y, z, f * wl);
        apply(legs[1][li], x, y, z, f * (1 - wl));
      }
      if (spin && k) {
        // la jupe s'évase quand le mannequin tourne
        const dx = acc[0] - ax, dz = acc[2] - az, d = Math.hypot(dx, dz) || 1;
        const out = Math.min(0.16, 0.13 * spin * spin * (0.4 + 0.6 * (k / L)) * (k / L) * s);
        acc[0] += (dx / d) * out; acc[2] += (dz / d) * out; acc[1] += out * 0.35;
      }
      if (env.box) outOfBox(env.box, acc, 0.035 * s);
      // la longueur qui touche le sol s'étale autour (comme une robe longue assise)
      const fy = (env.floorY ?? 0) + 0.01 * s;
      if (k && acc[1] < fy) {
        const ex = fy - acc[1], dx = acc[0] - ax, dz = acc[2] - az, d = Math.hypot(dx, dz) || 1;
        acc[1] = fy; acc[0] += (dx / d) * ex * 0.6; acc[2] += (dz / d) * ex * 0.6;
      }
      T[o * 3] = acc[0]; T[o * 3 + 1] = acc[1]; T[o * 3 + 2] = acc[2];
    }
    B[bi.Hips].getWorldQuaternion(this.hipsQ).multiply(this.hipsRestQinv);
  }

  /** Segments de collision (jambes, avant-bras, mains), 14 nombres par segment. */
  colliders() {
    const b = this.body.bones;
    const s = this.body.root.scale.x;
    const C = this.caps;
    const A = new THREE.Vector3(), Bv = new THREE.Vector3(), q = new THREE.Quaternion();
    let k = 0;
    const put = (ra, rb) => {
      const r = Math.max(ra, rb) + 0.03 * s;
      C.set([A.x, A.y, A.z, Bv.x, Bv.y, Bv.z, ra, rb,
        Math.min(A.x, Bv.x) - r, Math.max(A.x, Bv.x) + r, Math.min(A.y, Bv.y) - r, Math.max(A.y, Bv.y) + r, Math.min(A.z, Bv.z) - r, Math.max(A.z, Bv.z) + r], k * 14);
      k++;
    };
    const pad = 0.012 * s; // le tissu reste à distance de la peau
    for (const lr of this.legRadii) {
      b[`${lr.side}UpLeg`].getWorldPosition(A); b[`${lr.side}Leg`].getWorldPosition(Bv); put(lr.thigh[0] * s + pad, lr.thigh[1] * s + pad);
      b[`${lr.side}Leg`].getWorldPosition(A); b[`${lr.side}Foot`].getWorldPosition(Bv); put(lr.calf[0] * s + pad, lr.calf[1] * s + pad);
      b[`${lr.side}ForeArm`].getWorldPosition(A); b[`${lr.side}Hand`].getWorldPosition(Bv); put(0.034 * s + pad, 0.026 * s + pad);
      b[`${lr.side}Hand`].getWorldPosition(A);
      Bv.set(0, -0.17 * s, 0).applyQuaternion(b[`${lr.side}Hand`].getWorldQuaternion(q)).add(A); put(0.028 * s + pad, 0.016 * s + pad);
    }
    this.nCaps = k;
  }

  reset() {
    this.body.root.updateMatrixWorld(true);
    this.computeTargets();
    this.cp.set(this.ct);
    this.cq.set(this.ct);
    this.colliders();
    this.acc = 0;
    for (let i = 0; i < 20; i++) this.step(1 / 60, { settle: true });
    this.writeBones();
  }

  step(dt, env = {}) {
    const { cp, cq, ct, front } = this;
    const s = this.body.root.scale.x;
    // pas de gravité ajoutée : la forme dessinée est déjà le tombé du tissu ;
    // l'inertie et les ressorts font bouger la jupe autour de cette forme
    const damp = env.settle ? 0.5 : 0.94;
    const seated = env.seated ? 2.5 : 1;
    for (let j = 0; j < K; j++) for (let k = 0; k <= L; k++) {
      const i = j * (L + 1) + k, o = i * 3;
      if (k === 0) { cp[o] = cq[o] = ct[o]; cp[o + 1] = cq[o + 1] = ct[o + 1]; cp[o + 2] = cq[o + 2] = ct[o + 2]; continue; }
      // ressort vers la forme dessinée : ferme près des hanches, souple vers l'ourlet
      const kk = Math.min(0.9, (0.32 - 0.22 * Math.pow(k / L, 0.7)) * (front[i] > 0 ? seated : 1));
      for (let c = 0; c < 3; c++) {
        const p = cp[o + c];
        let nx = p + (p - cq[o + c]) * damp;
        nx += (ct[o + c] - nx) * kk;
        cq[o + c] = p; cp[o + c] = nx;
      }
    }
    const C = this.caps, nC = this.nCaps, box = this.box, floorY = (this.floorY ?? 0) + 0.006 * s, clear = this.clear;
    for (let it = 0; it < 4; it++) {
      // longueur des segments
      for (let j = 0; j < K; j++) for (let k = 1; k <= L; k++) {
        const a = (j * (L + 1) + k - 1) * 3, b = a + 3;
        const rest = this.segRest[j * L + k - 1] * s;
        const dx = cp[b] - cp[a], dy = cp[b + 1] - cp[a + 1], dz = cp[b + 2] - cp[a + 2];
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-9;
        const f = ((d - rest) / d) * (k === 1 ? 1 : 0.5);
        if (k > 1) { cp[a] += dx * f; cp[a + 1] += dy * f; cp[a + 2] += dz * f; }
        cp[b] -= dx * f; cp[b + 1] -= dy * f; cp[b + 2] -= dz * f;
      }
      // collisions : jambes, mains, socle, sol
      for (let j = 0; j < K; j++) for (let k = 1; k <= L; k++) {
        const ji = j * (L + 1) + k, o = ji * 3;
        let px = cp[o], py = cp[o + 1], pz = cp[o + 2];
        for (let c = 0; c < nC; c++) {
          const q = c * 14;
          if (px < C[q + 8] || px > C[q + 9] || py < C[q + 10] || py > C[q + 11] || pz < C[q + 12] || pz > C[q + 13]) continue;
          const ax = C[q], ay = C[q + 1], az = C[q + 2];
          const ex = C[q + 3] - ax, ey = C[q + 4] - ay, ez = C[q + 5] - az;
          const len2 = ex * ex + ey * ey + ez * ez || 1e-9;
          let t = ((px - ax) * ex + (py - ay) * ey + (pz - az) * ez) / len2;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const qx = ax + ex * t, qy = ay + ey * t, qz = az + ez * t;
          const r = Math.min(C[q + 6] + (C[q + 7] - C[q + 6]) * t, clear[ji * 8 + c] * s);
          const ox = px - qx, oy = py - qy, oz = pz - qz;
          const d = ox * ox + oy * oy + oz * oz;
          if (d < r * r && d > 1e-12) { const f = r / Math.sqrt(d); px = qx + ox * f; py = qy + oy * f; pz = qz + oz * f; }
        }
        if (box) { _p[0] = px; _p[1] = py; _p[2] = pz; outOfBox(box, _p, 0.03 * s); px = _p[0]; py = _p[1]; pz = _p[2]; }
        if (py < floorY) py = floorY;
        cp[o] = px; cp[o + 1] = py; cp[o + 2] = pz;
      }
    }
  }

  /** Matrices des os des chaînes : position du point, rotation qui suit le segment. */
  writeBones() {
    const s = this.body.root.scale.x;
    const hq = this.hipsQ;
    _s.set(s, s, s);
    for (let j = 0; j < K; j++) for (let k = 0; k < L; k++) {
      const o = (j * (L + 1) + k) * 3;
      _v.set(this.restJ[o + 3] - this.restJ[o], this.restJ[o + 4] - this.restJ[o + 1], this.restJ[o + 5] - this.restJ[o + 2]).applyQuaternion(hq).normalize();
      _v2.set(this.cp[o + 3] - this.cp[o], this.cp[o + 4] - this.cp[o + 1], this.cp[o + 5] - this.cp[o + 2]).normalize();
      _q.setFromUnitVectors(_v, _v2).multiply(hq);
      _v.set(this.cp[o], this.cp[o + 1], this.cp[o + 2]);
      this.chainBones[j * L + k].matrixWorld.compose(_v, _q, _s);
    }
  }

  update(dt, env) {
    this.floorY = env.floorY;
    this.box = env.box;
    this.computeTargets(env);
    this.colliders();
    const h = 1 / 60;
    this.acc = Math.min(this.acc + dt, h * 4);
    while (this.acc >= h) { this.step(h, env); this.acc -= h; }
    this.writeBones();
  }

  /** Profondeur (m) d'un point (repère du bassin, non mis à l'échelle) dans la robe ; < 0 dehors. */
  penetration(lx, ly, lz) {
    const hr = this.hipsRest;
    const sec = this.dressTab.get(Math.round((ly + hr.y) / this.BIN));
    if (!sec) return -1;
    const dx = lx + hr.x - sec.c[0], dz = lz + hr.z - sec.c[1];
    const r = Math.hypot(dx, dz);
    return radiusAt(sec, dx / (r || 1), dz / (r || 1)) - r;
  }

  halfWidthAt(y) {
    const sec = this.dressTab.get(Math.round(y / this.BIN));
    if (!sec) return 0;
    let w = 0;
    for (let k = 0; k < NA; k++) w = Math.max(w, Math.abs(sec.c[0] + sec.radii[k] * Math.sin((k / NA) * Math.PI * 2)));
    return w;
  }

  dispose() {
    for (const m of [this.mesh, this.hem]) { if (!m) continue; m.parent?.remove(m); m.geometry.dispose(); }
    this.mesh.material.dispose();
    this.skeleton.dispose();
  }
}

const _p = [0, 0, 0];
/**
 * Socle de la pose assise : un point sous le dessus du socle est repoussé
 * horizontalement, depuis le centre du socle, jusqu'à son bord : la jupe
 * retombe autour du socle au lieu de le traverser.
 */
function outOfBox(box, p, pad) {
  const x0 = box.x0 - pad, x1 = box.x1 + pad, z0 = box.z0 - pad, z1 = box.z1 + pad;
  if (p[1] > box.top + pad || p[0] <= x0 || p[0] >= x1 || p[2] <= z0 || p[2] >= z1) return;
  const cx = (box.x0 + box.x1) / 2, cz = (box.z0 + box.z1) / 2;
  let dx = p[0] - cx, dz = p[2] - cz;
  if (Math.abs(dx) < 1e-6 && Math.abs(dz) < 1e-6) dz = -1;
  // sortie par le côté que coupe le rayon issu du centre
  const tx = dx > 0 ? (x1 - cx) / dx : dx < 0 ? (x0 - cx) / dx : Infinity;
  const tz = dz > 0 ? (z1 - cz) / dz : dz < 0 ? (z0 - cz) / dz : Infinity;
  const t = Math.min(tx, tz);
  // juste sous le dessus : on préfère poser le tissu sur le socle
  if (box.top + pad - p[1] < 0.03) { p[1] = box.top + pad; return; }
  p[0] = cx + dx * t; p[2] = cz + dz * t;
}

/** Bords libres du tissu (en points) : boucles fermées et chaînes ouvertes. */
function boundaryChains(tris, rv, n) {
  const key = (a, b) => (a < b ? a * n + b : b * n + a);
  const cnt = new Map();
  for (let t = 0; t < tris.length; t += 3) {
    const v = [rv[tris[t]], rv[tris[t + 1]], rv[tris[t + 2]]];
    for (let e = 0; e < 3; e++) {
      const a = v[e], b = v[(e + 1) % 3];
      if (a !== b) cnt.set(key(a, b), (cnt.get(key(a, b)) || 0) + 1);
    }
  }
  const adj = new Map();
  for (const [k, c] of cnt) {
    if (c !== 1) continue;
    const a = Math.floor(k / n), b = k % n;
    if (!adj.has(a)) adj.set(a, []);
    if (!adj.has(b)) adj.set(b, []);
    adj.get(a).push(b); adj.get(b).push(a);
  }
  const used = new Set(), chains = [];
  const walk = (start) => {
    const ch = [start];
    let cur = start;
    for (;;) {
      const nx = adj.get(cur).find((x) => !used.has(key(cur, x)));
      if (nx === undefined) break;
      used.add(key(cur, nx));
      if (nx === start) { ch.closed = true; break; }
      ch.push(nx);
      cur = nx;
    }
    if (ch.length >= 3) chains.push(ch);
  };
  for (const [v, l] of adj) if (l.length === 1 && !used.has(key(v, l[0]))) walk(v);
  for (const [v, l] of adj) if (l.some((x) => !used.has(key(v, x)))) walk(v);
  return chains;
}

/** Boudin le long de bords de tissu (6 côtés), dans le même tissu que la robe. */
class EdgeTube {
  constructor(chains, puv, radius) {
    this.chains = chains;
    this.radius = radius;
    this.S = 6;
    const S = this.S;
    let count = 0;
    const idx = [];
    this.starts = chains.map((ch) => {
      const base = count;
      const n = ch.length, segs = ch.closed ? n : n - 1;
      for (let k = 0; k < segs; k++) {
        const k2 = (k + 1) % n;
        for (let r = 0; r < S; r++) {
          const a0 = base + k * S + r, a1 = base + k * S + ((r + 1) % S), b0 = base + k2 * S + r, b1 = base + k2 * S + ((r + 1) % S);
          idx.push(a0, b0, a1, a1, b0, b1);
        }
      }
      count += n * S;
      return base;
    });
    this.count = count;
    const g = new THREE.BufferGeometry();
    const uvs = new Float32Array(count * 2);
    this.forEachVertex((v, p) => { uvs[v * 2] = puv[p * 2]; uvs[v * 2 + 1] = puv[p * 2 + 1]; });
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    g.setAttribute('fabricUv', new THREE.BufferAttribute(uvs, 2));
    g.setAttribute('uv', new THREE.BufferAttribute(uvs.slice(), 2));
    g.setIndex(idx);
    this.geometry = g;
  }

  forEachVertex(fn) {
    this.chains.forEach((ch, c) => ch.forEach((p, k) => { for (let r = 0; r < this.S; r++) fn(this.starts[c] + k * this.S + r, p); }));
  }

  write(P, N) {
    const S = this.S, r = this.radius;
    const pos = this.geometry.attributes.position.array, nrm = this.geometry.attributes.normal.array;
    this.chains.forEach((ch, c) => {
      const n = ch.length;
      for (let k = 0; k < n; k++) {
        const p = ch[k] * 3;
        const a = ch[ch.closed ? (k - 1 + n) % n : Math.max(0, k - 1)] * 3;
        const b = ch[ch.closed ? (k + 1) % n : Math.min(n - 1, k + 1)] * 3;
        let tx = P[b] - P[a], ty = P[b + 1] - P[a + 1], tz = P[b + 2] - P[a + 2];
        const tl = Math.hypot(tx, ty, tz) || 1; tx /= tl; ty /= tl; tz /= tl;
        const sx = N[p], sy = N[p + 1], sz = N[p + 2];
        let bx = ty * sz - tz * sy, by = tz * sx - tx * sz, bz = tx * sy - ty * sx;
        const bl = Math.hypot(bx, by, bz) || 1; bx /= bl; by /= bl; bz /= bl;
        const nx = by * tz - bz * ty, ny = bz * tx - bx * tz, nz = bx * ty - by * tx;
        for (let q = 0; q < S; q++) {
          const an = (q / S) * Math.PI * 2, cs = Math.cos(an), sn = Math.sin(an);
          const ox = nx * cs + bx * sn, oy = ny * cs + by * sn, oz = nz * cs + bz * sn;
          const v = (this.starts[c] + k * S + q) * 3;
          pos[v] = P[p] + ox * r; pos[v + 1] = P[p + 1] + oy * r; pos[v + 2] = P[p + 2] + oz * r;
          nrm[v] = ox; nrm[v + 1] = oy; nrm[v + 2] = oz;
        }
      }
    });
  }
}

// ---------- Tombés pré-calculés (tools/bake) ----------
// Pour chaque robe, taille et pose, la forme du tissu a été simulée dans Blender.
// Elle s'affiche telle quelle : vrais plis, tissu posé sur les cuisses, traîne au sol.
const BAKES = {}; // robe → { index: Set, cache: Map }
const BAKE_BASE = 'assets/garments/bakes/';

export async function loadBakeIndex(name) {
  try {
    const list = await fetch(`${BAKE_BASE}${name}/index.json`).then((r) => (r.ok ? r.json() : []));
    BAKES[name] = { index: new Set(list), cache: new Map() };
  } catch {
    BAKES[name] = { index: new Set(), cache: new Map() };
  }
}

export const hasBake = (name, size, pose) => !!BAKES[name]?.index.has(`${size}-${pose}`);

/** Charge (une fois) un tombé : positions du tissu (repère du mannequin) et pose exacte du corps. */
export function loadBake(name, size, pose) {
  const B = BAKES[name], key = `${size}-${pose}`;
  if (!B.cache.has(key)) {
    B.cache.set(key, Promise.all([
      fetch(`${BAKE_BASE}${name}/${key}.json`).then((r) => r.json()),
      fetch(`${BAKE_BASE}${name}/${key}.bin`).then((r) => r.arrayBuffer()),
    ]).then(([meta, bin]) => {
      const q = new Int16Array(bin), pos = new Float32Array(q.length);
      for (let i = 0; i < q.length; i++) pos[i] = q[i] / meta.quant;
      return { meta, pos };
    }));
  }
  return B.cache.get(key);
}

/** Robe figée dans un tombé pré-calculé, accrochée au mannequin. */
export class BakedDress {
  constructor(name, material, root) {
    const D = DATA[name];
    this.D = D;
    const { rv, uv, tris } = D;
    const n = D.meta.particles, m = rv.length;
    this.n = n;
    this.N = new Float32Array(n * 3);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(m * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(m * 3), 3));
    g.setAttribute('fabricUv', new THREE.BufferAttribute(new Float32Array(uv), 2));
    g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(uv), 2));
    g.setIndex(new THREE.BufferAttribute(new Uint32Array(tris), 1));
    this.mesh = new THREE.Mesh(g, material);
    this.mesh.castShadow = this.mesh.receiveShadow = true;
    this.mesh.frustumCulled = false;
    root.add(this.mesh);
    // ourlet roulé : bords du bas et de la fente
    let top = -Infinity;
    for (let i = 0; i < n; i++) top = Math.max(top, D.uniq[i * 3 + 1]);
    const chains = (D.chains ||= boundaryChains(tris, rv, n)).filter((ch) => ch.some((p) => D.uniq[p * 3 + 1] < top * 0.5));
    if (chains.length) {
      const puv = new Float32Array(n * 2);
      for (let r = 0; r < m; r++) { puv[rv[r] * 2] = uv[r * 2]; puv[rv[r] * 2 + 1] = uv[r * 2 + 1]; }
      this.hem = new EdgeTube(chains, puv, 0.0035);
      this.hemMesh = new THREE.Mesh(this.hem.geometry, material);
      this.hemMesh.castShadow = true;
      this.hemMesh.frustumCulled = false;
      root.add(this.hemMesh);
    }
    this.mesh.visible = false;
    if (this.hemMesh) this.hemMesh.visible = false;
  }

  /** Affiche un tombé (positions des points du tissu, repère du mannequin). */
  show(P) {
    const { rv, tris } = this.D, N = this.N, n = this.n;
    N.fill(0);
    for (let t = 0; t < tris.length; t += 3) {
      const a = rv[tris[t]] * 3, b = rv[tris[t + 1]] * 3, c = rv[tris[t + 2]] * 3;
      const ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2];
      const vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      N[a] += nx; N[a + 1] += ny; N[a + 2] += nz; N[b] += nx; N[b + 1] += ny; N[b + 2] += nz; N[c] += nx; N[c + 1] += ny; N[c + 2] += nz;
    }
    for (let i = 0; i < n; i++) {
      const l = Math.hypot(N[i * 3], N[i * 3 + 1], N[i * 3 + 2]) || 1;
      N[i * 3] /= l; N[i * 3 + 1] /= l; N[i * 3 + 2] /= l;
    }
    const pos = this.mesh.geometry.attributes.position.array, nrm = this.mesh.geometry.attributes.normal.array;
    for (let r = 0; r < rv.length; r++) {
      const s = rv[r] * 3;
      pos[r * 3] = P[s]; pos[r * 3 + 1] = P[s + 1]; pos[r * 3 + 2] = P[s + 2];
      nrm[r * 3] = N[s]; nrm[r * 3 + 1] = N[s + 1]; nrm[r * 3 + 2] = N[s + 2];
    }
    this.mesh.geometry.attributes.position.needsUpdate = true;
    this.mesh.geometry.attributes.normal.needsUpdate = true;
    this.mesh.visible = true;
    if (this.hem) {
      this.hem.write(P, N);
      this.hem.geometry.attributes.position.needsUpdate = true;
      this.hem.geometry.attributes.normal.needsUpdate = true;
      this.hemMesh.visible = true;
    }
  }

  hide() { this.mesh.visible = false; if (this.hemMesh) this.hemMesh.visible = false; }

  dispose() {
    for (const m of [this.mesh, this.hemMesh]) { if (!m) continue; m.parent?.remove(m); m.geometry.dispose(); }
  }
}
