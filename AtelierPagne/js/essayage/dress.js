// Robe importée (Blender → assets/garments/<nom>.bin, voir tools/convert_garment.py),
// ajustée au mannequin et animée :
// 1. Ajustement : les hauteurs clés (ourlet, taille, haut du bustier) sont
//    recalées sur le corps, puis chaque tranche est mise à la largeur du corps
//    (+ aisance) ; aucun point ne reste à l'intérieur du corps.
// 2. Rig : chaque sommet reprend les poids du point du corps le plus proche ;
//    sous les hanches, la jupe ne suit plus que le bassin (elle ne se coupe pas
//    entre les jambes).
// 3. Rendu : le bustier, tenu par le squelette, est déformé par la carte
//    graphique ; seule la jupe est simulée (particules : gravité, inertie,
//    collisions jambes / mains / bassin / socle / sol), avec les plis du modèle.
// L'ajustement est mémorisé par robe, silhouette et mesures : changer de pose
// ou revenir à une tenue ne recalcule rien.
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

/** Enveloppe convexe 2D, centre, et rayon par angle (table de NA valeurs). */
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

// ---------- Grille spatiale (clés numériques : rapide) ----------
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

// ---------- Ajustement d'une robe sur un corps (résultat mis en cache) ----------
const FITS = new Map();
const fitKey = (body, name) => `${name}|${body.sex}|${JSON.stringify(body.cm || {})}`;

function fitDress(body, name) {
  const key = fitKey(body, name);
  if (FITS.has(key)) return FITS.get(key);
  const D = DATA[name];
  const J = body.restJ, lm = body.lm;
  const n = D.meta.particles;
  const P0 = D.uniq;
  const tris = D.tris, rv = D.rv;

  // ---------- 1. Ajustement vertical ----------
  const BIN = 0.01;
  const binsOf = (arr, count, keep = () => true) => {
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
  const dBins = binsOf(P0, n);
  const perAt = (y) => { const s = section(dBins.get(Math.round(y / BIN)) || []); return s ? s.per : Infinity; };
  // taille du modèle : tranche la plus fine entre 70 % et 92 % de la hauteur
  let dWaist = hem, best = Infinity;
  for (let y = hem + (top - hem) * 0.7; y < hem + (top - hem) * 0.92; y += BIN) { const p = perAt(y); if (p < best) { best = p; dWaist = y; } }
  // haut du bustier : saut de largeur (les manches / bandeau commencent)
  let dBodice = top;
  for (let y = dWaist + 0.04; y < top; y += BIN) { if (perAt(y + 0.02) > perAt(y) * 1.22) { dBodice = y; break; } }
  const yMap = [
    [hem, 0.006], [dWaist, lm.waist], [dBodice, lm.bust + 0.032], [top, lm.bust + 0.032 + (top - dBodice) * 1.05],
  ];
  const mapY = (y) => {
    for (let i = 0; i < yMap.length - 1; i++) {
      const [a, A] = yMap[i], [b, B] = yMap[i + 1];
      if (y <= b || i === yMap.length - 2) return A + ((y - a) / (b - a)) * (B - A);
    }
    return y;
  };

  // ---------- 2. Ajustement horizontal ----------
  const rp = body.restPos;
  const geo = body.body.geometry;
  const SI = geo.attributes.skinIndex.array, SW = geo.attributes.skinWeight.array;
  const bi = body.bi;
  const nb = rp.length / 3;
  const wOf = (i, ids) => { let w = 0; for (let c = 0; c < 4; c++) if (ids.includes(SI[i * 4 + c])) w += SW[i * 4 + c] / 255; return w; };
  const exclude = [bi.Head, bi.LeftHand, bi.RightHand, bi.LeftForeArm, bi.RightForeArm];
  const armIds = [bi.LeftArm, bi.RightArm];
  const bandY = lm.bust + 0.032; // au-dessus : bandeau qui passe sur le haut des bras
  const torsoKeep = (i) => wOf(i, exclude) < 0.3 && wOf(i, armIds) < 0.3;
  const bandKeep = (i) => wOf(i, exclude) < 0.3;
  const tBins = binsOf(rp, nb, torsoKeep), aBins = binsOf(rp, nb, bandKeep);
  const secCache = new Map();
  const bodySec = (y, withArms = y > bandY) => {
    const k = Math.round(y / BIN), c = `${k}:${withArms}`;
    if (!secCache.has(c)) secCache.set(c, section((withArms ? aBins : tBins).get(k) || []));
    return secCache.get(c);
  };
  const crotch = J.LeftUpLeg.y - 0.07;
  const hipBodyY = lm.hip;
  const P = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) P[i * 3 + 1] = mapY(P0[i * 3 + 1]);
  const mBins = new Map();
  for (let i = 0; i < n; i++) {
    const k = Math.round(P[i * 3 + 1] / BIN);
    if (!mBins.has(k)) mBins.set(k, []);
    mBins.get(k).push(i);
  }
  const EASE = 0.008;
  const keys = [...mBins.keys()].sort((a, b) => a - b);
  const raw = new Map();
  for (const k of keys) {
    const y = k * BIN;
    const ds = section(mBins.get(k).map((i) => [P0[i * 3], P0[i * 3 + 2]]));
    const bs = bodySec(Math.max(y, hipBodyY));
    if (!ds || !bs) continue;
    raw.set(k, { s: THREE.MathUtils.clamp((bs.per + 2 * Math.PI * EASE) / ds.per, 0.8, 1.5), dc: ds.c, bz: bs.c[1] });
  }
  const hipK = Math.round(hipBodyY / BIN);
  const smooth = (k, f, win = 5) => {
    let acc = 0, w = 0;
    for (let d = -win; d <= win; d++) { const r = raw.get(k + d); if (r) { const ww = win + 1 - Math.abs(d); acc += f(r) * ww; w += ww; } }
    return w ? acc / w : null;
  };
  const sHip = Math.max(1, smooth(hipK, (r) => r.s) ?? 1);
  const bzHip = smooth(hipK, (r) => r.bz) ?? 0;
  for (const k of keys) {
    if (!raw.has(k)) continue;
    const y = k * BIN;
    // sous les hanches, la jupe garde l'ampleur du modèle (mise à l'échelle des hanches)
    const sv = y < hipBodyY ? sHip : smooth(k, (r) => r.s);
    const dcx = smooth(k, (r) => r.dc[0], 8), dcz = smooth(k, (r) => r.dc[1], 8);
    const bz = y < hipBodyY ? bzHip : smooth(k, (r) => r.bz, 8);
    for (const i of mBins.get(k)) {
      P[i * 3] = (P0[i * 3] - dcx) * sv;
      P[i * 3 + 2] = bz + (P0[i * 3 + 2] - dcz) * sv;
    }
  }
  // première passe grossière : hors de l'enveloppe du corps, tranche par tranche
  for (let i = 0; i < n; i++) {
    const y = P[i * 3 + 1];
    if (y < crotch) continue;
    const bs = bodySec(y);
    if (!bs) continue;
    const dx = P[i * 3] - bs.c[0], dz = P[i * 3 + 2] - bs.c[1];
    const r = Math.sqrt(dx * dx + dz * dz) || 1e-6;
    const R = radiusAt(bs, dx / r, dz / r) + (y > bandY ? 0.016 : 0.012);
    if (r < R) { P[i * 3] = bs.c[0] + (dx / r) * R; P[i * 3 + 2] = bs.c[1] + (dz / r) * R; }
  }

  // ---------- Voisinage du tissu et bords ----------
  const nbr = Array.from({ length: n }, () => []);
  const edgeCount = new Map();
  for (let t = 0; t < tris.length; t += 3) {
    const v = [rv[tris[t]], rv[tris[t + 1]], rv[tris[t + 2]]];
    for (let e = 0; e < 3; e++) {
      const a = v[e], b = v[(e + 1) % 3];
      if (a === b) continue;
      const k = a < b ? a * n + b : b * n + a;
      const c = edgeCount.get(k) || 0;
      edgeCount.set(k, c + 1);
      if (!c) { nbr[a].push(b); nbr[b].push(a); }
    }
  }
  const border = new Uint8Array(n);
  for (const [k, c] of edgeCount) if (c === 1) { border[Math.floor(k / n)] = 1; border[k % n] = 1; }

  // ---------- 3. Relaxation : on lisse le tissu puis on le repousse hors du corps ----------
  // (comme un tissu qu'on défroisse sur le mannequin) : plus de dents de scie.
  const gridTorso = makeGrid(rp, nb, torsoKeep), gridBand = makeGrid(rp, nb, bandKeep);
  const gridFor = (y) => (y > bandY - 0.005 ? gridBand : gridTorso);
  // normales de la peau, lissées sur leurs voisines (moins sensibles au maillage)
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
  const fitW = new Float32Array(n);
  for (let i = 0; i < n; i++) fitW[i] = border[i] ? 0 : ss(P[i * 3 + 1], crotch - 0.06, crotch + 0.04);
  const pushOut = () => {
    for (let i = 0; i < n; i++) {
      const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
      if (y < crotch - 0.03) continue;
      const j = nearestIn(gridFor(y), rp, x, y, z);
      const nx = BN[j * 3], ny = BN[j * 3 + 1], nz = BN[j * 3 + 2];
      const sd = (x - rp[j * 3]) * nx + (y - rp[j * 3 + 1]) * ny + (z - rp[j * 3 + 2]) * nz;
      const want = y > bandY ? 0.016 : 0.012;
      if (sd < want) { const k = want - sd; P[i * 3] += nx * k; P[i * 3 + 1] += ny * k * 0.3; P[i * 3 + 2] += nz * k; }
    }
  };
  const lap = (f) => {
    const Q = P.slice();
    for (let i = 0; i < n; i++) {
      const w = fitW[i] * f, nb2 = nbr[i];
      if (!w || !nb2.length) continue;
      for (let c = 0; c < 3; c++) {
        let m = 0;
        for (const j of nb2) m += Q[j * 3 + c];
        P[i * 3 + c] = Q[i * 3 + c] + w * (m / nb2.length - Q[i * 3 + c]);
      }
    }
  };
  pushOut();
  for (let it = 0; it < 6; it++) { lap(0.5); lap(-0.53); pushOut(); }

  // ---------- 4. Poids : point de peau le plus proche ----------
  const NB = body.body.skeleton.bones.length;
  let Wd = new Float32Array(n * NB);
  for (let i = 0; i < n; i++) {
    const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
    const j = nearestIn(gridFor(y), rp, x, y, z);
    const t = ss(hipBodyY - y, 0.02, 0.16); // sous les hanches : le bassin seul
    for (let c = 0; c < 4; c++) Wd[i * NB + SI[j * 4 + c]] += (SW[j * 4 + c] / 255) * (1 - t);
    // le devant de la jupe accompagne les jambes (assise, marche) ; le dos et les côtés suivent le bassin
    const front = THREE.MathUtils.clamp((z - bzHip) / 0.1 + 0.15, 0, 1) * ss(hipBodyY - y, 0.06, 0.3) * 0.85;
    const wl = ss(x, -0.05, 0.05);
    const below = y < J.LeftLeg.y;
    Wd[i * NB + bi.Hips] += t * (1 - front);
    Wd[i * NB + (below ? bi.LeftLeg : bi.LeftUpLeg)] += t * front * wl;
    Wd[i * NB + (below ? bi.RightLeg : bi.RightUpLeg)] += t * front * (1 - wl);
  }
  // lissage limité au bandeau : le bustier reste accroché au torse
  for (let it = 0; it < 10; it++) {
    const Wn = new Float32Array(Wd);
    for (let i = 0; i < n; i++) {
      if (P[i * 3 + 1] <= bandY + 0.008) continue;
      const nb2 = nbr[i];
      if (!nb2.length) continue;
      for (let b = 0; b < NB; b++) {
        let acc = 0;
        for (const j of nb2) acc += Wd[j * NB + b];
        Wn[i * NB + b] = Wd[i * NB + b] * 0.4 + (acc / nb2.length) * 0.6;
      }
    }
    Wd = Wn;
  }
  const si = new Uint8Array(n * 4), sw = new Float32Array(n * 4), stiff = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const y = P[i * 3 + 1];
    const row = Array.from({ length: NB }, (_, b) => [b, Wd[i * NB + b]]).sort((a, b2) => b2[1] - a[1]).slice(0, 4);
    const sum = row.reduce((s2, e) => s2 + e[1], 0) || 1;
    row.forEach(([b, w], c) => { si[i * 4 + c] = b; sw[i * 4 + c] = w / sum; });
    // liberté du tissu : ajustée jusqu'aux hanches, libre dessous
    const free = ss(lm.hip - 0.02 - y, 0, 0.2);
    const drop = THREE.MathUtils.clamp((lm.hip - y) / Math.max(0.3, lm.hip - 0.006), 0, 1);
    stiff[i] = free < 1e-3 ? 1 : (1 - free) + free * (0.09 * (1 - drop) ** 2 + 0.01);
  }

  // ---------- 5. Liens du tissu (étirement + flexion), masses inverses précalculées ----------
  const opp = new Map();
  for (let t = 0; t < tris.length; t += 3) {
    const v = [rv[tris[t]], rv[tris[t + 1]], rv[tris[t + 2]]];
    for (let e = 0; e < 3; e++) {
      const a = v[e], b = v[(e + 1) % 3], c = v[(e + 2) % 3];
      if (a === b) continue;
      const k = a < b ? a * n + b : b * n + a;
      if (!opp.has(k)) opp.set(k, []);
      opp.get(k).push(c);
    }
  }
  const links = [];
  const dist = (a, b) => Math.hypot(P[a * 3] - P[b * 3], P[a * 3 + 1] - P[b * 3 + 1], P[a * 3 + 2] - P[b * 3 + 2]);
  const add = (a, b, type) => {
    const wa = stiff[a] >= 1 ? 0 : 1, wb = stiff[b] >= 1 ? 0 : 1;
    if (!wa && !wb) return;
    links.push(a * 3, b * 3, dist(a, b), type, wa / (wa + wb), wb / (wa + wb));
  };
  for (const [k, o] of opp) {
    const a = Math.floor(k / n), b = k % n;
    add(a, b, 0);
    if (o.length === 2 && o[0] !== o[1]) add(o[0], o[1], 1);
  }

  // ---------- Tables (collisions, largeur de la robe, bras) ----------
  const bodyY0 = Math.round(crotch / BIN);
  const bodyTab = [];
  for (let k = bodyY0; k <= Math.round((lm.waist + 0.05) / BIN); k++) bodyTab.push(bodySec(k * BIN));
  const dressTab = new Map();
  const fBins = new Map();
  for (let i = 0; i < n; i++) {
    const k = Math.round(P[i * 3 + 1] / BIN);
    if (!fBins.has(k)) fBins.set(k, []);
    fBins.get(k).push([P[i * 3], P[i * 3 + 2]]);
  }
  for (const [k, pts] of fBins) { const sct = section(pts); if (sct) dressTab.set(k, sct); }
  const nearPelvis = new Uint8Array(n);
  for (let i = 0; i < n; i++) { const y = P[i * 3 + 1]; nearPelvis[i] = y > crotch - 0.05 && y < lm.waist + 0.06 ? 1 : 0; }
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
    thigh: [Math.max(legR(side, J[`${side}UpLeg`].y - 0.12), legR(side, J[`${side}UpLeg`].y - 0.2)) * 1.04, legR(side, J[`${side}Leg`].y + 0.04) * 1.08],
    calf: [legR(side, J[`${side}Leg`].y - 0.08) * 1.06, legR(side, J[`${side}Foot`].y + 0.08) * 1.05],
  }));

  const fit = {
    P, si, sw, stiff, links: new Float32Array(links), bodyTab, bodyY0, dressTab, nearPelvis, legRadii, BIN,
  };
  FITS.set(key, fit);
  if (FITS.size > 12) FITS.delete(FITS.keys().next().value);
  return fit;
}

export class DressCloth {
  constructor(body, name, material, scene) {
    const D = DATA[name];
    this.body = body;
    const fit = fitDress(body, name);
    Object.assign(this, fit);
    const { P, stiff } = fit;
    const n = D.meta.particles;
    this.n = n;
    this.rest = P;
    this.hipsRest = body.restJ.Hips.clone();

    // Matrices de repos des os : skinning de la jupe (processeur) et du bustier (carte graphique).
    const bones = body.body.skeleton.bones;
    this.bones = bones;
    const saved = bones.map((b) => b.quaternion.clone());
    const savedRoot = [body.root.position.clone(), body.root.quaternion.clone(), body.root.scale.clone()];
    body.root.position.set(0, 0, 0); body.root.quaternion.identity(); body.root.scale.set(1, 1, 1);
    bones.forEach((b) => b.quaternion.copy(body.rest[b.name]));
    body.root.updateMatrixWorld(true);
    this.restInv = bones.map((b) => b.matrixWorld.clone().invert());
    bones.forEach((b, i) => b.quaternion.copy(saved[i]));
    body.root.position.copy(savedRoot[0]); body.root.quaternion.copy(savedRoot[1]); body.root.scale.copy(savedRoot[2]);
    body.root.updateMatrixWorld(true);
    this.skinM = bones.map(() => new THREE.Matrix4());

    // Normales de repos, par particule (pas de lignes d'ombre aux coutures du patron).
    const tris = D.tris, rv = D.rv;
    const restN = new Float32Array(n * 3);
    accumulateNormals(P, tris, rv, restN, 0, tris.length);
    normalizeAll(restN, n);
    this.restN = restN;

    // Partage : triangles du bustier (tous les sommets tenus) / de la jupe (simulée).
    const bod = [], sk = [];
    for (let t = 0; t < tris.length; t += 3) {
      const held = stiff[rv[tris[t]]] >= 1 && stiff[rv[tris[t + 1]]] >= 1 && stiff[rv[tris[t + 2]]] >= 1;
      (held ? bod : sk).push(tris[t], tris[t + 1], tris[t + 2]);
    }
    const uv = D.uv;
    const sub = (list) => {
      const map = new Map(), verts = [];
      const idx = list.map((r) => { if (!map.has(r)) { map.set(r, verts.length); verts.push(r); } return map.get(r); });
      return { verts, idx };
    };
    const fabricAttrs = (g, verts) => {
      const m = verts.length;
      const pos = new Float32Array(m * 3), uvs = new Float32Array(m * 2), nrm = new Float32Array(m * 3);
      verts.forEach((r, i) => {
        const p = rv[r];
        pos.set([P[p * 3], P[p * 3 + 1], P[p * 3 + 2]], i * 3);
        nrm.set([restN[p * 3], restN[p * 3 + 1], restN[p * 3 + 2]], i * 3);
        uvs.set([uv[r * 2], uv[r * 2 + 1]], i * 2);
      });
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
      g.setAttribute('fabricUv', new THREE.BufferAttribute(uvs, 2));
      g.setAttribute('restPos', new THREE.BufferAttribute(pos.slice(), 3));
      g.setAttribute('restNormal', new THREE.BufferAttribute(new Float32Array(m * 3), 3));
    };

    // Bustier : maillage skinné, déformé par la carte graphique.
    {
      const { verts, idx } = sub(bod);
      const g = new THREE.BufferGeometry();
      fabricAttrs(g, verts);
      const skI = new Uint16Array(verts.length * 4), skW = new Float32Array(verts.length * 4);
      verts.forEach((r, i) => { const p = rv[r]; for (let c = 0; c < 4; c++) { skI[i * 4 + c] = this.si[p * 4 + c]; skW[i * 4 + c] = this.sw[p * 4 + c]; } });
      g.setAttribute('skinIndex', new THREE.BufferAttribute(skI, 4));
      g.setAttribute('skinWeight', new THREE.BufferAttribute(skW, 4));
      g.setIndex(idx);
      this.bodice = new THREE.SkinnedMesh(g, material);
      this.bodice.castShadow = this.bodice.receiveShadow = true;
      this.bodice.frustumCulled = false;
      scene.add(this.bodice);
      this.skeleton = new THREE.Skeleton(bones, this.restInv.map((m) => m.clone()));
      this.bodice.bind(this.skeleton, new THREE.Matrix4());
    }

    // Jupe : particules simulées sur le processeur.
    {
      const { verts, idx } = sub(sk);
      const g = new THREE.BufferGeometry();
      fabricAttrs(g, verts);
      g.setIndex(idx);
      this.skirtRv = Uint32Array.from(verts.map((r) => rv[r]));
      this.skirtTris = Uint32Array.from(idx.map((i) => this.skirtRv[i]));
      const active = [...new Set(this.skirtRv)].sort((a, b) => a - b);
      this.active = Uint32Array.from(active);
      this.free = Uint32Array.from(active.filter((p) => stiff[p] < 1));
      this.held = Uint32Array.from(active.filter((p) => stiff[p] >= 1));
      this.skirtGeo = g;
      this.mesh = new THREE.Mesh(g, material);
      this.mesh.castShadow = this.mesh.receiveShadow = true;
      this.mesh.frustumCulled = false;
      scene.add(this.mesh);
    }

    this.pos = new Float32Array(n * 3);
    this.prev = new Float32Array(n * 3);
    this.target = new Float32Array(n * 3);
    this.nrm = new Float32Array(n * 3);
    this.caps = new Float64Array(8 * 14);
    this.legFreedom = 0.85;
    this.reset();
  }

  /** Positions cibles de la jupe = robe au repos, déformée par le squelette. */
  computeTargets() {
    const { bones, restInv, skinM, rest, si, sw, target, active, held, restN, nrm } = this;
    for (let b = 0; b < bones.length; b++) skinM[b].multiplyMatrices(bones[b].matrixWorld, restInv[b]);
    const E = skinM.map((mm) => mm.elements);
    for (let q = 0; q < active.length; q++) {
      const i = active[q];
      const x = rest[i * 3], y = rest[i * 3 + 1], z = rest[i * 3 + 2];
      let ox = 0, oy = 0, oz = 0;
      for (let c = 0; c < 4; c++) {
        const w = sw[i * 4 + c];
        if (!w) continue;
        const e = E[si[i * 4 + c]];
        ox += w * (e[0] * x + e[4] * y + e[8] * z + e[12]);
        oy += w * (e[1] * x + e[5] * y + e[9] * z + e[13]);
        oz += w * (e[2] * x + e[6] * y + e[10] * z + e[14]);
      }
      target[i * 3] = ox; target[i * 3 + 1] = oy; target[i * 3 + 2] = oz;
    }
    // normales de la couture bustier/jupe : identiques à celles du bustier (pas de ligne)
    for (let q = 0; q < held.length; q++) {
      const i = held[q];
      const x = restN[i * 3], y = restN[i * 3 + 1], z = restN[i * 3 + 2];
      let ox = 0, oy = 0, oz = 0;
      for (let c = 0; c < 4; c++) {
        const w = sw[i * 4 + c];
        if (!w) continue;
        const e = E[si[i * 4 + c]];
        ox += w * (e[0] * x + e[4] * y + e[8] * z);
        oy += w * (e[1] * x + e[5] * y + e[9] * z);
        oz += w * (e[2] * x + e[6] * y + e[10] * z);
      }
      const l = Math.sqrt(ox * ox + oy * oy + oz * oz) || 1;
      nrm[i * 3] = ox / l; nrm[i * 3 + 1] = oy / l; nrm[i * 3 + 2] = oz / l;
    }
    const hm = this.body.bones.Hips.matrixWorld;
    this.hipsM = hm.elements;
    this.invHips = (this._inv ||= new THREE.Matrix4()).copy(hm).invert().elements;
  }

  /** Segments de collision (jambes, avant-bras, mains), à plat : 14 nombres par segment. */
  colliders() {
    const b = this.body.bones;
    const s = this.body.root.scale.x;
    const C = this.caps;
    const A = new THREE.Vector3(), B = new THREE.Vector3(), q = new THREE.Quaternion();
    let k = 0;
    const put = (ra, rb) => {
      const r = Math.max(ra, rb) + 0.02 * s;
      C.set([A.x, A.y, A.z, B.x, B.y, B.z, ra, rb,
        Math.min(A.x, B.x) - r, Math.max(A.x, B.x) + r, Math.min(A.y, B.y) - r, Math.max(A.y, B.y) + r, Math.min(A.z, B.z) - r, Math.max(A.z, B.z) + r], k * 14);
      k++;
    };
    for (const lr of this.legRadii) {
      b[`${lr.side}UpLeg`].getWorldPosition(A); b[`${lr.side}Leg`].getWorldPosition(B); put(lr.thigh[0] * s, lr.thigh[1] * s);
      b[`${lr.side}Leg`].getWorldPosition(A); b[`${lr.side}Foot`].getWorldPosition(B); put(lr.calf[0] * s, lr.calf[1] * s);
      b[`${lr.side}ForeArm`].getWorldPosition(A); b[`${lr.side}Hand`].getWorldPosition(B); put(0.034 * s, 0.026 * s);
      b[`${lr.side}Hand`].getWorldPosition(A);
      B.set(0, -0.17 * s, 0).applyQuaternion(b[`${lr.side}Hand`].getWorldQuaternion(q)).add(A); put(0.028 * s, 0.016 * s);
    }
    this.nCaps = k;
  }

  reset() {
    this.body.root.updateMatrixWorld(true);
    this.computeTargets();
    this.pos.set(this.target);
    this.prev.set(this.target);
    this.colliders();
    this.acc = 0;
    for (let k = 0; k < 14; k++) this.step(1 / 60, true);
    this.writeRender();
  }

  step(dt, settle = false) {
    const { pos, prev, target, stiff, free, held } = this;
    const g = -9.81 * dt * dt;
    const damp = settle ? 0.6 : 0.985;
    const soft = this.soft ?? 1;
    for (let q = 0; q < held.length; q++) {
      const k = held[q] * 3;
      pos[k] = prev[k] = target[k]; pos[k + 1] = prev[k + 1] = target[k + 1]; pos[k + 2] = prev[k + 2] = target[k + 2];
    }
    for (let q = 0; q < free.length; q++) {
      const i = free[q], k = i * 3, s = stiff[i];
      const ks = s > 0.5 ? s : s * soft;
      const px = pos[k], py = pos[k + 1], pz = pos[k + 2];
      let nx = px + (px - prev[k]) * damp, ny = py + (py - prev[k + 1]) * damp + g, nz = pz + (pz - prev[k + 2]) * damp;
      nx += (target[k] - nx) * ks; ny += (target[k + 1] - ny) * ks; nz += (target[k + 2] - nz) * ks;
      prev[k] = px; prev[k + 1] = py; prev[k + 2] = pz;
      pos[k] = nx; pos[k + 1] = ny; pos[k + 2] = nz;
    }
    const scale = this.body.root.scale.x;
    const thick = 0.009 * scale;
    const C = this.caps, nC = this.nCaps, links = this.links, box = this.box, floorY = (this.floorY ?? 0) + thick * 0.5;
    const e = this.invHips, m = this.hipsM;
    const BIN = this.BIN, y0 = this.bodyY0, tab = this.bodyTab, hr = this.hipsRest;
    const near = this.nearPelvis;
    for (let it = 0; it < 2; it++) {
      for (let l = 0; l < links.length; l += 6) {
        const a = links[l], b = links[l + 1], rest = links[l + 2] * scale;
        const dx = pos[b] - pos[a], dy = pos[b + 1] - pos[a + 1], dz = pos[b + 2] - pos[a + 2];
        const d2 = dx * dx + dy * dy + dz * dz;
        let goal, k;
        if (links[l + 3] === 0) { goal = rest * 1.02; if (d2 <= goal * goal) continue; k = 1; } // le tissu ne s'étire pas, il plisse
        else { goal = rest * 0.9; if (d2 >= goal * goal) continue; k = 0.3; } // flexion : garde du corps
        const d = Math.sqrt(d2) || 1e-9;
        const f = ((d - goal) / d) * k, fa = f * links[l + 4], fb = f * links[l + 5];
        pos[a] += dx * fa; pos[a + 1] += dy * fa; pos[a + 2] += dz * fa;
        pos[b] -= dx * fb; pos[b + 1] -= dy * fb; pos[b + 2] -= dz * fb;
      }
      for (let q = 0; q < free.length; q++) {
        const i = free[q], k = i * 3;
        let px = pos[k], py = pos[k + 1], pz = pos[k + 2];
        for (let c = 0; c < nC; c++) {
          const o = c * 14;
          if (px < C[o + 8] || px > C[o + 9] || py < C[o + 10] || py > C[o + 11] || pz < C[o + 12] || pz > C[o + 13]) continue;
          const ax = C[o], ay = C[o + 1], az = C[o + 2];
          const ex = C[o + 3] - ax, ey = C[o + 4] - ay, ez = C[o + 5] - az;
          const len2 = ex * ex + ey * ey + ez * ez || 1e-9;
          let t = ((px - ax) * ex + (py - ay) * ey + (pz - az) * ez) / len2;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const cx = ax + ex * t, cy = ay + ey * t, cz = az + ez * t;
          const r = C[o + 6] + (C[o + 7] - C[o + 6]) * t + thick;
          const ox = px - cx, oy = py - cy, oz = pz - cz;
          const d = ox * ox + oy * oy + oz * oz;
          if (d < r * r && d > 1e-12) { const f = r / Math.sqrt(d); px = cx + ox * f; py = cy + oy * f; pz = cz + oz * f; }
        }
        // bassin : repère des hanches, table du corps au repos
        if (near[i]) {
          const lx = e[0] * px + e[4] * py + e[8] * pz + e[12];
          const ly = e[1] * px + e[5] * py + e[9] * pz + e[13];
          const lz = e[2] * px + e[6] * py + e[10] * pz + e[14];
          const sec = tab[Math.round((ly + hr.y) / BIN) - y0];
          if (sec) {
            const dx = lx + hr.x - sec.c[0], dz = lz + hr.z - sec.c[1];
            const r = Math.sqrt(dx * dx + dz * dz) || 1e-6;
            const R = radiusAt(sec, dx / r, dz / r) + 0.01;
            if (r < R) {
              const nx = sec.c[0] + (dx / r) * R - hr.x, nz = sec.c[1] + (dz / r) * R - hr.z;
              px = m[0] * nx + m[4] * ly + m[8] * nz + m[12];
              py = m[1] * nx + m[5] * ly + m[9] * nz + m[13];
              pz = m[2] * nx + m[6] * ly + m[10] * nz + m[14];
            }
          }
        }
        if (box && px > box.x0 && px < box.x1 && pz > box.z0 && pz < box.z1 && py < box.top + thick) {
          const p0 = box.top + thick - py, p1 = px - box.x0, p2 = box.x1 - px, p3 = pz - box.z0, p4 = box.z1 - pz;
          const mn = Math.min(p0, p1, p2, p3, p4);
          if (mn === p0) py = box.top + thick; else if (mn === p1) px = box.x0; else if (mn === p2) px = box.x1; else if (mn === p3) pz = box.z0; else pz = box.z1;
        }
        if (py < floorY) py = floorY;
        pos[k] = px; pos[k + 1] = py; pos[k + 2] = pz;
      }
    }
  }

  update(dt, env) {
    this.floorY = env.floorY;
    this.box = env.box;
    // assise : la jupe épouse davantage les cuisses (cible plus présente)
    this.soft = env.seated ? 2.5 : 1;
    this.computeTargets();
    this.colliders();
    const h = 1 / 60;
    this.acc = Math.min(this.acc + dt, h * 3);
    while (this.acc >= h) { this.step(h); this.acc -= h; }
    this.writeRender();
  }

  writeRender() {
    const { pos, nrm, free, skirtRv, skirtTris } = this;
    // normales par particule (la couture bustier/jupe garde celles du bustier)
    for (let q = 0; q < free.length; q++) { const k = free[q] * 3; nrm[k] = nrm[k + 1] = nrm[k + 2] = 0; }
    const stiff = this.stiff;
    for (let t = 0; t < skirtTris.length; t += 3) {
      const a = skirtTris[t] * 3, b = skirtTris[t + 1] * 3, c = skirtTris[t + 2] * 3;
      const ux = pos[b] - pos[a], uy = pos[b + 1] - pos[a + 1], uz = pos[b + 2] - pos[a + 2];
      const vx = pos[c] - pos[a], vy = pos[c + 1] - pos[a + 1], vz = pos[c + 2] - pos[a + 2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      if (stiff[a / 3] < 1) { nrm[a] += nx; nrm[a + 1] += ny; nrm[a + 2] += nz; }
      if (stiff[b / 3] < 1) { nrm[b] += nx; nrm[b + 1] += ny; nrm[b + 2] += nz; }
      if (stiff[c / 3] < 1) { nrm[c] += nx; nrm[c + 1] += ny; nrm[c + 2] += nz; }
    }
    for (let q = 0; q < free.length; q++) {
      const k = free[q] * 3;
      const l = Math.sqrt(nrm[k] * nrm[k] + nrm[k + 1] * nrm[k + 1] + nrm[k + 2] * nrm[k + 2]) || 1;
      nrm[k] /= l; nrm[k + 1] /= l; nrm[k + 2] /= l;
    }
    const P = this.skirtGeo.attributes.position.array, N = this.skirtGeo.attributes.normal.array;
    for (let i = 0; i < skirtRv.length; i++) {
      const s = skirtRv[i] * 3, d = i * 3;
      P[d] = pos[s]; P[d + 1] = pos[s + 1]; P[d + 2] = pos[s + 2];
      N[d] = nrm[s]; N[d + 1] = nrm[s + 1]; N[d + 2] = nrm[s + 2];
    }
    this.skirtGeo.attributes.position.needsUpdate = true;
    this.skirtGeo.attributes.normal.needsUpdate = true;
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
    for (const m of [this.mesh, this.bodice]) { m.parent?.remove(m); m.geometry.dispose(); }
    this.mesh.material.dispose();
    this.skeleton.dispose();
  }
}

function accumulateNormals(P, tris, rv, out, from, to) {
  for (let t = from; t < to; t += 3) {
    const a = rv[tris[t]] * 3, b = rv[tris[t + 1]] * 3, c = rv[tris[t + 2]] * 3;
    const ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2];
    const vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    for (const v of [a, b, c]) { out[v] += nx; out[v + 1] += ny; out[v + 2] += nz; }
  }
}
function normalizeAll(N, n) {
  for (let i = 0; i < n; i++) {
    const l = Math.hypot(N[i * 3], N[i * 3 + 1], N[i * 3 + 2]) || 1;
    N[i * 3] /= l; N[i * 3 + 1] /= l; N[i * 3 + 2] /= l;
  }
}
