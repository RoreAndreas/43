// Robe importée (Blender → assets/garments/<nom>.bin, voir tools/convert_garment.py),
// ajustée au mannequin et animée :
// 1. Ajustement : les hauteurs clés (ourlet, taille, haut du bustier) sont
//    recalées sur le corps, puis chaque tranche est mise à la largeur du corps
//    (+ aisance) ; aucun point ne reste à l'intérieur du corps.
// 2. Rig : chaque sommet reprend les poids du point du corps le plus proche ;
//    sous les hanches, la jupe ne suit plus que le bassin (elle ne se coupe pas
//    entre les jambes).
// 3. Tissu : tous les sommets sont des particules. Le bustier est tenu par le
//    squelette ; plus on descend, plus le tissu est libre (gravité, inertie,
//    collisions jambes / mains / bassin / socle / sol), avec les plis du modèle.
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

export class DressCloth {
  constructor(body, name, material, scene) {
    const D = DATA[name];
    this.body = body;
    const J = body.restJ, lm = body.lm;
    const n = D.meta.particles;
    this.n = n;
    const P0 = D.uniq;

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
    const cache = new Map();
    const bodySec = (y, withArms = y > bandY) => {
      const k = Math.round(y / BIN), ck = `${k}:${withArms}`;
      if (!cache.has(ck)) cache.set(ck, section((withArms ? aBins : tBins).get(k) || []));
      return cache.get(ck);
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
    // Facteur d'échelle et centres par tranche, puis lissés (pas de marches d'escalier).
    const EASE = 0.008;
    const keys = [...mBins.keys()].sort((a, b) => a - b);
    const raw = new Map();
    for (const k of keys) {
      const y = k * BIN;
      const ds = section(mBins.get(k).map((i) => [P0[i * 3], P0[i * 3 + 2]]));
      const bs = bodySec(Math.max(y, hipBodyY));
      if (!ds || !bs) continue;
      const s0 = THREE.MathUtils.clamp((bs.per + 2 * Math.PI * EASE) / ds.per, 0.8, 1.5);
      raw.set(k, { s: s0, dc: ds.c, bz: bs.c[1] });
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
    // jamais à l'intérieur du corps
    for (let i = 0; i < n; i++) {
      const y = P[i * 3 + 1];
      if (y < crotch) continue;
      const bs = bodySec(y);
      if (!bs) continue;
      const dx = P[i * 3] - bs.c[0], dz = P[i * 3 + 2] - bs.c[1];
      const r = Math.hypot(dx, dz) || 1e-6;
      const R = radiusAt(bs, dx / r, dz / r) + (y > bandY ? 0.016 : 0.012); // le bandeau reste décollé des épaules
      if (r < R) { P[i * 3] = bs.c[0] + (dx / r) * R; P[i * 3 + 2] = bs.c[1] + (dz / r) * R; }
    }
    this.rest = P;

    // ---------- 3. Poids : point du corps le plus proche ----------
    // Deux grilles : le bustier ne s'accroche qu'au torse, le bandeau peut suivre les bras.
    const cell = 0.03;
    const gk = (x, y, z) => `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
    const makeGrid = (keep) => {
      const g2 = new Map();
      for (let i = 0; i < nb; i++) {
        if (!keep(i)) continue;
        const k = gk(rp[i * 3], rp[i * 3 + 1], rp[i * 3 + 2]);
        if (!g2.has(k)) g2.set(k, []);
        g2.get(k).push(i);
      }
      return g2;
    };
    const gridTorso = makeGrid(torsoKeep), gridBand = makeGrid(bandKeep);
    let grid = gridTorso;
    const nearest = (x, y, z) => {
      const cx = Math.floor(x / cell), cy = Math.floor(y / cell), cz = Math.floor(z / cell);
      for (let r = 1; r < 8; r++) {
        let bestI = -1, bd = Infinity;
        for (let a = -r; a <= r; a++) for (let b = -r; b <= r; b++) for (let c = -r; c <= r; c++) {
          const list = grid.get(`${cx + a},${cy + b},${cz + c}`);
          if (!list) continue;
          for (const i of list) {
            const d = (rp[i * 3] - x) ** 2 + (rp[i * 3 + 1] - y) ** 2 + (rp[i * 3 + 2] - z) ** 2;
            if (d < bd) { bd = d; bestI = i; }
          }
        }
        if (bestI >= 0) return bestI;
      }
      return 0;
    };
    const nbr = Array.from({ length: n }, () => []);
    {
      const tr = D.tris, rvv = D.rv;
      for (let t = 0; t < tr.length; t += 3) {
        const v = [rvv[tr[t]], rvv[tr[t + 1]], rvv[tr[t + 2]]];
        for (let e = 0; e < 3; e++) { const a = v[e], b = v[(e + 1) % 3]; if (a !== b) { nbr[a].push(b); nbr[b].push(a); } }
      }
    }
    // Aisance précise : chaque point du tissu est au moins à 1,2 cm de la peau,
    // mesuré le long de la normale du point de peau le plus proche ; le
    // déplacement est lissé sur le tissu (pas de bosses).
    {
      const BN = geo.attributes.normal.array;
      for (let pass = 0; pass < 3; pass++) {
        const off = new Float32Array(n * 3);
        for (let i = 0; i < n; i++) {
          const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
          if (y < crotch - 0.03) continue;
          grid = y > bandY - 0.005 ? gridBand : gridTorso;
          const j = nearest(x, y, z);
          const nx = BN[j * 3], ny = BN[j * 3 + 1], nz = BN[j * 3 + 2];
          const sd = (x - rp[j * 3]) * nx + (y - rp[j * 3 + 1]) * ny + (z - rp[j * 3 + 2]) * nz;
          const want = y > bandY ? 0.016 : 0.012;
          if (sd < want) { const k = want - sd; off[i * 3] = nx * k; off[i * 3 + 1] = ny * k * 0.3; off[i * 3 + 2] = nz * k; }
        }
        for (let it = 0; it < 4; it++) {
          const o2 = new Float32Array(off);
          for (let i = 0; i < n; i++) {
            const nb2 = nbr[i];
            if (!nb2.length) continue;
            for (let c = 0; c < 3; c++) {
              let m = 0;
              for (const j of nb2) m += off[j * 3 + c];
              m /= nb2.length;
              // on garde au moins le déplacement propre du point (jamais moins d'aisance)
              o2[i * 3 + c] = Math.abs(m) > Math.abs(off[i * 3 + c]) ? m : off[i * 3 + c];
            }
          }
          off.set(o2);
        }
        for (let i = 0; i < n * 3; i++) P[i] += off[i];
      }
    }

    // Poids denses (un par os), puis lissés le long du tissu : la robe se déforme
    // en douceur, sans plis cassés entre le buste et les bras.
    const NB = body.body.skeleton.bones.length;
    let Wd = new Float32Array(n * NB);
    for (let i = 0; i < n; i++) {
      const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
      grid = y > bandY - 0.005 ? gridBand : gridTorso;
      const j = nearest(x, y, z);
      const t = ss(hipBodyY - y, 0.02, 0.16); // sous les hanches : le bassin seul
      for (let c = 0; c < 4; c++) Wd[i * NB + SI[j * 4 + c]] += (SW[j * 4 + c] / 255) * (1 - t);
      // Le devant de la jupe accompagne les jambes (assise, marche) ; le dos et les côtés suivent le bassin.
      const front = THREE.MathUtils.clamp((z - bzHip) / 0.1 + 0.15, 0, 1) * ss(hipBodyY - y, 0.06, 0.3) * 0.85;
      const wl = ss(x, -0.05, 0.05);
      const below = y < J.LeftLeg.y;
      Wd[i * NB + bi.Hips] += t * (1 - front);
      Wd[i * NB + (below ? bi.LeftLeg : bi.LeftUpLeg)] += t * front * wl;
      Wd[i * NB + (below ? bi.RightLeg : bi.RightUpLeg)] += t * front * (1 - wl);
    }
    // lissage limité au bandeau et à sa jonction : le bustier reste accroché au torse
    const smoothZone = new Uint8Array(n);
    for (let i = 0; i < n; i++) smoothZone[i] = P[i * 3 + 1] > bandY + 0.008 ? 1 : 0;
    for (let it = 0; it < 10; it++) {
      const Wn = new Float32Array(Wd);
      for (let i = 0; i < n; i++) {
        if (!smoothZone[i]) continue;
        const nb2 = nbr[i];
        for (let b = 0; b < NB; b++) {
          let acc = 0;
          for (const j of nb2) acc += Wd[j * NB + b];
          Wn[i * NB + b] = nb2.length ? Wd[i * NB + b] * 0.4 + (acc / nb2.length) * 0.6 : Wd[i * NB + b];
        }
      }
      Wd = Wn;
    }
    this.si = new Uint8Array(n * 4);
    this.sw = new Float32Array(n * 4);
    this.stiff = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const y = P[i * 3 + 1];
      const row = Array.from({ length: NB }, (_, b) => [b, Wd[i * NB + b]]).sort((a, b2) => b2[1] - a[1]).slice(0, 4);
      const sum = row.reduce((s2, e) => s2 + e[1], 0) || 1;
      row.forEach(([b, w], c) => { this.si[i * 4 + c] = b; this.sw[i * 4 + c] = w / sum; });
      // liberté du tissu : tenu au bustier, libre sous les hanches
      const free = ss(lm.hip - 0.02 - y, 0, 0.2); // ajustée jusqu'aux hanches, libre dessous
      const drop = THREE.MathUtils.clamp((lm.hip - y) / Math.max(0.3, lm.hip - 0.006), 0, 1);
      this.stiff[i] = free < 1e-3 ? 1 : (1 - free) * 1 + free * (0.09 * (1 - drop) ** 2 + 0.01);
    }

    // Matrices de repos des os (pour le skinning sur le processeur).
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

    // ---------- Liens du tissu (arêtes + flexion) ----------
    const tris = D.tris, rv = D.rv;
    const edges = new Map(), opp = new Map();
    const key = (a, b) => (a < b ? a * n + b : b * n + a);
    for (let t = 0; t < tris.length; t += 3) {
      const v = [rv[tris[t]], rv[tris[t + 1]], rv[tris[t + 2]]];
      for (let e = 0; e < 3; e++) {
        const a = v[e], b = v[(e + 1) % 3], c = v[(e + 2) % 3];
        if (a === b) continue;
        const k = key(a, b);
        edges.set(k, [a, b]);
        if (!opp.has(k)) opp.set(k, []);
        opp.get(k).push(c);
      }
    }
    const links = [];
    const dist = (a, b) => Math.hypot(P[a * 3] - P[b * 3], P[a * 3 + 1] - P[b * 3 + 1], P[a * 3 + 2] - P[b * 3 + 2]);
    for (const [k, [a, b]] of edges) {
      if (this.stiff[a] >= 1 && this.stiff[b] >= 1) continue;
      links.push(a, b, dist(a, b), 0);
      const o = opp.get(k);
      if (o && o.length === 2 && o[0] !== o[1]) links.push(o[0], o[1], dist(o[0], o[1]), 1);
    }
    this.links = new Float32Array(links);

    // Tables du corps pour la contrainte « ne pas rentrer dans le bassin ».
    this.bodyTab = [];
    this.bodyY0 = Math.round(crotch / BIN);
    for (let k = this.bodyY0; k <= Math.round((lm.waist + 0.05) / BIN); k++) this.bodyTab.push(bodySec(k * BIN));
    // Tables de la robe ajustée (pour écarter les bras et mesurer la largeur).
    this.dressTab = new Map();
    for (const [k, list] of mBins) {
      const s = section(list.map((i) => [P[i * 3], P[i * 3 + 2]]));
      if (s) this.dressTab.set(k, s);
    }
    this.BIN = BIN;
    this.hipsRest = J.Hips.clone();
    this.nearPelvis = new Uint8Array(n);
    for (let i = 0; i < n; i++) { const y = P[i * 3 + 1]; this.nearPelvis[i] = y > crotch - 0.05 && y < lm.waist + 0.06 ? 1 : 0; }

    // Rayons des jambes (collisions).
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
    this.legRadii = ['Left', 'Right'].map((side) => ({
      side,
      thigh: [Math.max(legR(side, J[`${side}UpLeg`].y - 0.12), legR(side, J[`${side}UpLeg`].y - 0.2)) * 1.04, legR(side, J[`${side}Leg`].y + 0.04) * 1.08],
      calf: [legR(side, J[`${side}Leg`].y - 0.08) * 1.06, legR(side, J[`${side}Foot`].y + 0.08) * 1.05],
    }));

    // ---------- Rendu ----------
    this.pos = new Float32Array(n * 3);
    this.prev = new Float32Array(n * 3);
    this.target = new Float32Array(n * 3);
    const m = D.meta.renderVertices;
    this.rv = rv;
    this.renderPos = new Float32Array(m * 3);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.renderPos, 3));
    g.setAttribute('fabricUv', new THREE.BufferAttribute(new Float32Array(D.uv), 2));
    const restR = new Float32Array(m * 3);
    for (let i = 0; i < m; i++) restR.set([P[rv[i] * 3], P[rv[i] * 3 + 1], P[rv[i] * 3 + 2]], i * 3);
    g.setAttribute('restPos', new THREE.BufferAttribute(restR, 3));
    g.setAttribute('restNormal', new THREE.BufferAttribute(new Float32Array(m * 3), 3));
    g.setIndex(new THREE.BufferAttribute(new Uint32Array(D.tris), 1));
    this.geo = g;
    this.mesh = new THREE.Mesh(g, material);
    this.mesh.castShadow = this.mesh.receiveShadow = true;
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
    this.legFreedom = 0.85;
    this.reset();
  }

  /** Positions cibles = robe au repos, déformée par le squelette (skinning sur processeur). */
  computeTargets() {
    const { bones, restInv, skinM, rest, si, sw, target, n } = this;
    for (let b = 0; b < bones.length; b++) skinM[b].multiplyMatrices(bones[b].matrixWorld, restInv[b]);
    const E = skinM.map((mm) => mm.elements);
    for (let i = 0; i < n; i++) {
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
    const hm = this.body.bones.Hips.matrixWorld;
    this.hipsM = hm.elements;
    this.invHips = (this._inv ||= new THREE.Matrix4()).copy(hm).invert().elements;
  }

  colliders() {
    const b = this.body.bones;
    const s = this.body.root.scale.x;
    const wp = (name) => b[name].getWorldPosition(new THREE.Vector3());
    const caps = [];
    for (const lr of this.legRadii) {
      caps.push([wp(`${lr.side}UpLeg`), wp(`${lr.side}Leg`), lr.thigh[0] * s, lr.thigh[1] * s]);
      caps.push([wp(`${lr.side}Leg`), wp(`${lr.side}Foot`), lr.calf[0] * s, lr.calf[1] * s]);
      const hand = wp(`${lr.side}Hand`);
      const tip = new THREE.Vector3(0, -0.17 * s, 0).applyQuaternion(b[`${lr.side}Hand`].getWorldQuaternion(new THREE.Quaternion())).add(hand);
      caps.push([wp(`${lr.side}ForeArm`), hand, 0.034 * s, 0.026 * s]);
      caps.push([hand, tip, 0.028 * s, 0.016 * s]);
    }
    // boîtes englobantes : on ne teste un segment que pour les particules proches
    const m = 0.02 * s;
    for (const c of caps) {
      const r = Math.max(c[2], c[3]) + m;
      c.push([Math.min(c[0].x, c[1].x) - r, Math.max(c[0].x, c[1].x) + r, Math.min(c[0].y, c[1].y) - r, Math.max(c[0].y, c[1].y) + r, Math.min(c[0].z, c[1].z) - r, Math.max(c[0].z, c[1].z) + r]);
    }
    return caps;
  }

  reset() {
    this.body.root.updateMatrixWorld(true);
    this.computeTargets();
    this.pos.set(this.target);
    this.prev.set(this.target);
    this.caps = this.colliders();
    this.acc = 0;
    for (let k = 0; k < 30; k++) this.step(1 / 60, true);
    this.writeRender();
  }

  step(dt, settle = false) {
    const { pos, prev, target, stiff, n } = this;
    const g = -9.81 * dt * dt;
    const damp = settle ? 0.6 : 0.985;
    const soft = this.soft ?? 1;
    for (let i = 0; i < n; i++) {
      const k = i * 3, s = stiff[i];
      if (s >= 1) { pos[k] = target[k]; pos[k + 1] = target[k + 1]; pos[k + 2] = target[k + 2]; prev[k] = pos[k]; prev[k + 1] = pos[k + 1]; prev[k + 2] = pos[k + 2]; continue; }
      const ks = s > 0.5 ? s : s * soft;
      for (let c = 0; c < 3; c++) {
        const v = (pos[k + c] - prev[k + c]) * damp;
        prev[k + c] = pos[k + c];
        pos[k + c] += v + (c === 1 ? g : 0);
        pos[k + c] += (target[k + c] - pos[k + c]) * ks;
      }
    }
    const scale = this.body.root.scale.x;
    const thick = 0.009 * scale;
    const caps = this.caps, links = this.links, box = this.box, floorY = this.floorY ?? 0;
    const e = this.invHips, m = this.hipsM;
    const BIN = this.BIN, y0 = this.bodyY0, tab = this.bodyTab, hr = this.hipsRest;
    const near = this.nearPelvis;
    for (let it = 0; it < 2; it++) {
      for (let l = 0; l < links.length; l += 4) {
        const a = links[l] * 3, b = links[l + 1] * 3, rest = links[l + 2] * scale, type = links[l + 3];
        const dx = pos[b] - pos[a], dy = pos[b + 1] - pos[a + 1], dz = pos[b + 2] - pos[a + 2];
        const d = Math.hypot(dx, dy, dz) || 1e-9;
        let goal;
        if (type === 0) { if (d <= rest * 1.02) continue; goal = rest * 1.02; } // le tissu ne s'étire pas, il plisse
        else { if (d >= rest * 0.9) continue; goal = rest * 0.9; } // flexion : garde du corps
        const wa = stiff[links[l]] >= 1 ? 0 : 1, wb = stiff[links[l + 1]] >= 1 ? 0 : 1;
        const sum = wa + wb;
        if (!sum) continue;
        const f = ((d - goal) / d) * (type === 0 ? 1 : 0.3);
        pos[a] += dx * f * (wa / sum); pos[a + 1] += dy * f * (wa / sum); pos[a + 2] += dz * f * (wa / sum);
        pos[b] -= dx * f * (wb / sum); pos[b + 1] -= dy * f * (wb / sum); pos[b + 2] -= dz * f * (wb / sum);
      }
      for (let i = 0; i < n; i++) {
        if (stiff[i] >= 1) continue;
        const k = i * 3;
        let px = pos[k], py = pos[k + 1], pz = pos[k + 2];
        for (const cap of caps) {
          const [A, B, ra, rb, bb] = cap;
          if (px < bb[0] || px > bb[1] || py < bb[2] || py > bb[3] || pz < bb[4] || pz > bb[5]) continue;
          const ex = B.x - A.x, ey = B.y - A.y, ez = B.z - A.z;
          const len2 = ex * ex + ey * ey + ez * ez || 1e-9;
          let t = ((px - A.x) * ex + (py - A.y) * ey + (pz - A.z) * ez) / len2;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const cx = A.x + ex * t, cy = A.y + ey * t, cz = A.z + ez * t;
          const r = ra + (rb - ra) * t + thick;
          const ox = px - cx, oy = py - cy, oz = pz - cz;
          const d = ox * ox + oy * oy + oz * oz;
          if (d < r * r && d > 1e-12) { const f = r / Math.sqrt(d); px = cx + ox * f; py = cy + oy * f; pz = cz + oz * f; }
        }
        // bassin : repère des hanches, table du corps au repos
        if (!near[i]) { if (py < floorY + thick * 0.5) py = floorY + thick * 0.5; pos[k] = px; pos[k + 1] = py; pos[k + 2] = pz; continue; }
        const lx = e[0] * px + e[4] * py + e[8] * pz + e[12];
        const ly = e[1] * px + e[5] * py + e[9] * pz + e[13];
        const lz = e[2] * px + e[6] * py + e[10] * pz + e[14];
        const sec = tab[Math.round((ly + hr.y) / BIN) - y0];
        if (sec) {
          const dx = lx + hr.x - sec.c[0], dz = lz + hr.z - sec.c[1];
          const r = Math.hypot(dx, dz) || 1e-6;
          const R = radiusAt(sec, dx / r, dz / r) + 0.01;
          if (r < R) {
            const nx = sec.c[0] + (dx / r) * R - hr.x, nz = sec.c[1] + (dz / r) * R - hr.z;
            px = m[0] * nx + m[4] * ly + m[8] * nz + m[12];
            py = m[1] * nx + m[5] * ly + m[9] * nz + m[13];
            pz = m[2] * nx + m[6] * ly + m[10] * nz + m[14];
          }
        }
        if (box && px > box.x0 && px < box.x1 && pz > box.z0 && pz < box.z1 && py < box.top + thick) {
          const pen = [box.top + thick - py, px - box.x0, box.x1 - px, pz - box.z0, box.z1 - pz];
          const mm = pen.indexOf(Math.min(...pen));
          if (mm === 0) py = box.top + thick; else if (mm === 1) px = box.x0; else if (mm === 2) px = box.x1; else if (mm === 3) pz = box.z0; else pz = box.z1;
        }
        if (py < floorY + thick * 0.5) py = floorY + thick * 0.5;
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
    this.caps = this.colliders();
    const h = 1 / 60;
    this.acc = Math.min(this.acc + dt, h * 3);
    while (this.acc >= h) { this.step(h); this.acc -= h; }
    this.writeRender();
  }

  writeRender() {
    const { pos, renderPos, rv } = this;
    for (let i = 0; i < rv.length; i++) {
      const s = rv[i] * 3, d = i * 3;
      renderPos[d] = pos[s]; renderPos[d + 1] = pos[s + 1]; renderPos[d + 2] = pos[s + 2];
    }
    this.geo.attributes.position.needsUpdate = true;
    this.geo.computeVertexNormals();
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
    this.mesh.parent?.remove(this.mesh);
    this.geo.dispose();
    this.mesh.material.dispose();
  }
}
