// Tenues en wax.
// - Le haut (corsage, manches, pantalon) est taillé dans la surface du corps puis
//   décollé de quelques millimètres : il porte les mêmes poids que le corps et
//   suit donc exactement chaque pose.
// - La jupe est un tissu simulé (Verlet) accroché à la taille : elle tombe,
//   se balance, s'écarte quand les jambes avancent et s'évase quand le
//   mannequin tourne sur lui-même.
// - Le motif est plaqué à l'échelle réelle (taille d'un motif en mètres).
import * as THREE from 'three';
import { DressCloth, hasDress } from './dress.js';

export const OUTFITS = {
  femme: [
    { id: 'aucune', label: 'Sans tenue', hint: 'Le mannequin seul, pour juger la silhouette.' },
    {
      id: 'aveline', label: 'Robe longue épaules dénudées', hint: 'Modèle 3D importé : bustier à bandeau, jupe longue fendue.',
      mesh: 'aveline',
    },
    {
      id: 'sirene', label: 'Robe sirène', hint: 'Ajustée jusqu’aux genoux, évasée jusqu’au sol, épaules dénudées.',
      top: { neck: 'offshoulder', bottom: 'hip', sleeves: 'band' },
      skirt: { from: 'hip', to: 'floor', cut: 'fitted', flare: 0.42 },
    },
    {
      id: 'evasee', label: 'Robe évasée', hint: 'Corsage ajusté, manches bouffantes, jupe ample sous le genou.',
      top: { neck: 'round', bottom: 'waist', sleeves: 'puff' },
      skirt: { from: 'waist', to: 'midcalf', cut: 'aline', flare: 0.5 },
    },
    {
      id: 'ensemble', label: 'Ensemble pagne', hint: 'Haut à encolure carrée et pagne long noué à la taille.',
      top: { neck: 'square', bottom: 'waistLow', sleeves: 'short' },
      skirt: { from: 'waist', to: 'ankle', cut: 'straight', flare: 0.14 },
    },
  ],
  homme: [
    { id: 'aucune', label: 'Sans tenue', hint: 'Le mannequin seul, pour juger la silhouette.' },
    {
      id: 'chemise', label: 'Chemise wax', hint: 'Chemise ample à manches courtes, pantalon uni.',
      top: { neck: 'collar', bottom: 'hipLow', sleeves: 'short', loose: true }, pants: true,
    },
    {
      id: 'tunique', label: 'Tunique & pantalon', hint: 'Tunique longue à manches longues sur pantalon uni.',
      top: { neck: 'round', bottom: 'hip', sleeves: 'long', loose: true },
      skirt: { from: 'hip', to: 'midthigh', cut: 'aline', flare: 0.16 },
      pants: true,
    },
  ],
};

// ---------- Matériau tissu : motif plaqué en coordonnées de repos ----------
export function fabricUniforms() {
  return { uMap: { value: null }, uScale: { value: 0.3 }, uHasMap: { value: 0 }, trim: new THREE.Color(0xe0a33a) };
}

function fabricMaterial(uniforms, { mode, color = 0xffffff, side = THREE.FrontSide }) {
  const m = new THREE.MeshStandardMaterial({ color, roughness: 0.86, metalness: 0, side });
  m.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `#include <common>
        attribute vec3 restPos; attribute vec3 restNormal; attribute vec2 fabricUv;
        varying vec3 vRestPos; varying vec3 vRestN; varying vec2 vFabricUv;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vRestPos = restPos; vRestN = restNormal; vFabricUv = fabricUv;`);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform sampler2D uMap; uniform float uScale; uniform float uHasMap;
        varying vec3 vRestPos; varying vec3 vRestN; varying vec2 vFabricUv;`)
      .replace('#include <map_fragment>', mode === 'uv' ? `
        if (uHasMap > 0.5) diffuseColor.rgb *= texture2D(uMap, vFabricUv / uScale).rgb;` : `
        if (uHasMap > 0.5) {
          vec3 w = pow(abs(normalize(vRestN)), vec3(14.0)); w /= (w.x + w.y + w.z);
          vec3 p = vRestPos / uScale;
          vec3 c = texture2D(uMap, p.zy * vec2(-1.0, -1.0)).rgb * w.x + texture2D(uMap, p.xz).rgb * w.y + texture2D(uMap, p.xy * vec2(1.0, -1.0)).rgb * w.z;
          diffuseColor.rgb *= c;
        }`);
  };
  m.customProgramCacheKey = () => `fabric-${mode}`;
  return m;
}

const ss = THREE.MathUtils.smoothstep;

// ---------- Pièces taillées dans le corps ----------
function bodyPiece(body, select, offset, uniforms, opts = {}) {
  const geo = body.body.geometry;
  const P = geo.attributes.position.array, N = geo.attributes.normal.array;
  const SI = geo.attributes.skinIndex.array, SW = geo.attributes.skinWeight.array;
  const idx = geo.index.array;
  const n = P.length / 3;
  const sel = new Uint8Array(n);
  for (let i = 0; i < n; i++) sel[i] = select(i) ? 1 : 0;
  const map = new Int32Array(n).fill(-1);
  const tris = [];
  let count = 0;
  for (let t = 0; t < idx.length; t += 3) {
    const a = idx[t], b = idx[t + 1], c = idx[t + 2];
    if (!(sel[a] && sel[b] && sel[c])) continue;
    for (const v of [a, b, c]) if (map[v] < 0) map[v] = count++;
    tris.push(map[a], map[b], map[c]);
  }
  if (!count) return null;
  const pos = new Float32Array(count * 3), rest = new Float32Array(count * 3), nrm = new Float32Array(count * 3);
  const si = new Uint8Array(count * 4), sw = new Uint8Array(count * 4);
  const p = new THREE.Vector3(), nn = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    const k = map[i];
    if (k < 0) continue;
    p.fromArray(P, i * 3); nn.fromArray(N, i * 3);
    rest.set([p.x, p.y, p.z], k * 3); nrm.set([nn.x, nn.y, nn.z], k * 3);
    offset(i, p, nn);
    pos.set([p.x, p.y, p.z], k * 3);
    for (let c = 0; c < 4; c++) { si[k * 4 + c] = SI[i * 4 + c]; sw[k * 4 + c] = SW[i * 4 + c]; }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('restPos', new THREE.BufferAttribute(rest, 3));
  g.setAttribute('restNormal', new THREE.BufferAttribute(nrm, 3));
  g.setAttribute('fabricUv', new THREE.BufferAttribute(new Float32Array(count * 2), 2));
  g.setAttribute('skinIndex', new THREE.Uint8BufferAttribute(si, 4));
  g.setAttribute('skinWeight', new THREE.Uint8BufferAttribute(sw, 4, true));
  g.setIndex(tris);
  let loops = boundaryLoops(tris, count);
  // Bas de la pièce : coupé net à l'horizontale (et rentré sous la jupe s'il y en a une).
  if (opts.bottomY !== undefined) {
    const isBottom = (loop) => loop.reduce((m, v) => m + rest[v * 3 + 1], 0) / loop.length < opts.bottomY + 0.035;
    for (const loop of loops) if (isBottom(loop)) for (const v of loop) pos[v * 3 + 1] -= rest[v * 3 + 1] - opts.bottomY;
    if (opts.hideBottom) loops = loops.filter((l) => !isBottom(l));
  }
  // Bords nets : on lisse le tracé des encolures, emmanchures et ourlets.
  for (const loop of loops) {
    for (let it = 0; it < 4; it++) {
      const cur = loop.map((v) => [pos[v * 3], pos[v * 3 + 1], pos[v * 3 + 2]]);
      loop.forEach((v, k) => {
        const a = cur[(k - 1 + loop.length) % loop.length], b = cur[(k + 1) % loop.length], c = cur[k];
        for (let d = 0; d < 3; d++) pos[v * 3 + d] = c[d] * 0.5 + (a[d] + b[d]) * 0.25;
      });
    }
  }
  g.computeVertexNormals();
  const mesh = new THREE.SkinnedMesh(g, fabricMaterial(uniforms, { mode: 'tri', color: opts.color, side: THREE.DoubleSide }));
  mesh.castShadow = mesh.receiveShadow = true;
  mesh.frustumCulled = false;
  body.root.add(mesh);
  mesh.bind(body.body.skeleton, body.body.bindMatrix);
  // Passepoil (biais contrasté) le long des bords, porté par les mêmes os.
  if (opts.piping !== false && loops.length) {
    const pipe = pipingMesh(g, loops, uniforms.trim ?? new THREE.Color(0x2b2a2e), opts.pipingRadius ?? 0.0038);
    body.root.add(pipe);
    pipe.bind(body.body.skeleton, body.body.bindMatrix);
    mesh.userData.extra = [pipe];
  }
  return mesh;
}

/** Poids regroupés par région, pour un sommet du corps. */
function regionWeights(body) {
  const geo = body.body.geometry;
  const SI = geo.attributes.skinIndex.array, SW = geo.attributes.skinWeight.array;
  const { bi } = body;
  const groups = {
    torso: [bi.Hips, bi.Spine], neck: [bi.Neck], head: [bi.Head],
    arm: [bi.LeftArm, bi.RightArm], fore: [bi.LeftForeArm, bi.RightForeArm], hand: [bi.LeftHand, bi.RightHand],
    upleg: [bi.LeftUpLeg, bi.RightUpLeg], leg: [bi.LeftLeg, bi.RightLeg], foot: [bi.LeftFoot, bi.RightFoot],
  };
  const lookup = {};
  for (const [g, ids] of Object.entries(groups)) for (const id of ids) lookup[id] = g;
  return (i) => {
    const w = { torso: 0, neck: 0, head: 0, arm: 0, fore: 0, hand: 0, upleg: 0, leg: 0, foot: 0 };
    for (let c = 0; c < 4; c++) w[lookup[SI[i * 4 + c]]] += SW[i * 4 + c] / 255;
    return w;
  };
}

function buildTop(body, spec, uniforms) {
  const J = body.lm.joints, lm = body.lm;
  const P = body.body.geometry.attributes.position.array;
  const W = regionWeights(body);
  const n = P.length / 3;
  const y = (i) => P[i * 3 + 1], x = (i) => P[i * 3], z = (i) => P[i * 3 + 2];
  const bottom = { waist: lm.waist - 0.02, waistLow: lm.waist - 0.05, hip: lm.hip - 0.055, hipLow: J.LeftUpLeg.y - 0.09 }[spec.bottom];
  const neckY = J.Neck.y, neckZ = J.Neck.z;
  // Bras (repère de liaison : pose en A) : abscisse le long du bras depuis l'épaule.
  const armAxis = (i) => {
    const side = x(i) > 0 ? 'Left' : 'Right';
    const s = J[`${side}Arm`], e = J[`${side}ForeArm`], w = J[`${side}Hand`];
    const d1 = e.clone().sub(s), l1 = d1.length(); d1.normalize();
    const d2 = w.clone().sub(e), l2 = d2.length(); d2.normalize();
    const p = new THREE.Vector3(x(i), y(i), z(i));
    const t1 = p.clone().sub(s).dot(d1);
    const t2 = p.clone().sub(e).dot(d2);
    return { s, d1, l1, t1, t2, l2, p };
  };
  const neckline = (i) => {
    const yy = y(i), xx = Math.abs(x(i)), zz = z(i);
    switch (spec.neck) {
      case 'offshoulder': return yy < lm.bust + 0.085;
      case 'square': {
        if (zz > neckZ && xx < 0.085 && yy > lm.bust + 0.075) return false;
        return yy < neckY - 0.02 || ((xx / 0.075) ** 2 + ((zz - neckZ) / 0.07) ** 2 > 1 && yy < neckY + 0.02);
      }
      case 'collar':
      case 'round': {
        const scoop = spec.neck === 'round' ? 0.06 : 0.035;
        if (zz > neckZ + 0.02 && xx < 0.06 && yy > neckY - scoop) return false;
        return (xx / 0.068) ** 2 + ((zz - neckZ - 0.005) / 0.062) ** 2 > 1 || yy < neckY - 0.045;
      }
      default: return true;
    }
  };
  const sleeve = (i, w) => {
    const armW = w.arm + w.fore;
    if (armW < 0.5) return false;
    const a = armAxis(i);
    switch (spec.sleeves) {
      case 'band': return w.arm > 0.5 && a.t1 > 0.03 && a.t1 < 0.13;
      case 'puff': return w.arm > 0.4 && a.t1 < 0.14;
      case 'short': return w.arm > 0.4 && a.t1 < 0.16;
      case 'long': return (w.arm > 0.4) || (w.fore > 0.4 && a.t2 < a.l2 - 0.03);
      default: return false;
    }
  };
  const inTorso = (i, w) => (w.torso + w.neck + w.upleg >= 0.5) && w.arm + w.fore + w.hand < 0.5 && w.head < 0.3 && y(i) >= bottom && neckline(i);
  const isSleeve = new Uint8Array(n);
  const select = (i) => {
    const w = W(i);
    if (sleeve(i, w)) { isSleeve[i] = 1; return spec.sleeves === 'band' || y(i) >= bottom; }
    if (spec.sleeves === 'band' || spec.neck === 'offshoulder') return inTorso(i, w) && w.neck < 0.3;
    return inTorso(i, w);
  };

  // Tension du tissu : il passe par-dessus les creux (entre les seins, au creux des reins).
  const bins = new Map();
  const tension = spec.loose ? 0.95 : 0.85;
  for (let i = 0; i < n; i++) {
    const w = W(i);
    if (w.torso + w.upleg < 0.6 || w.arm + w.fore + w.hand > 0.2) continue;
    const k = Math.round(y(i) / 0.01);
    if (!bins.has(k)) bins.set(k, []);
    bins.get(k).push([x(i), z(i)]);
  }
  const hulls = new Map();
  for (const [k, pts] of bins) if (pts.length > 6) hulls.set(k, hull2d(pts));
  const thick = spec.loose ? 0.013 : 0.006;
  const offset = (i, p, nn) => {
    const w = W(i);
    if (isSleeve[i]) {
      const a = armAxis(i);
      const radial = a.p.clone().sub(a.s).addScaledVector(a.d1, -a.t1).normalize();
      let extra = thick;
      if (spec.sleeves === 'puff' || spec.sleeves === 'band') {
        // manche bouffante, avec ses fronces
        const u = new THREE.Vector3().crossVectors(a.d1, new THREE.Vector3(0, 0, 1)).normalize();
        const v = new THREE.Vector3().crossVectors(a.d1, u);
        const ang = Math.atan2(radial.dot(v), radial.dot(u));
        const puff = Math.sin(Math.PI * THREE.MathUtils.clamp((a.t1 + 0.02) / 0.16, 0, 1));
        extra += 0.028 * puff * (1 + 0.22 * Math.sin(12 * ang));
      }
      if (spec.sleeves === 'short' && spec.loose) extra += 0.012 * ss(a.t1, 0, 0.15);
      p.addScaledVector(radial, extra * 0.7).addScaledVector(nn, extra * 0.3);
      return;
    }
    const h = hulls.get(Math.round(p.y / 0.01));
    if (h && w.torso + w.upleg > 0.6) {
      const c = h.center;
      const dx = p.x - c[0], dz = p.z - c[1];
      const r = Math.hypot(dx, dz) || 1e-6;
      const R = rayHull(h.pts, c, dx / r, dz / r);
      if (R > r) {
        const t = dz > 0 ? tension : tension * 0.6;
        const k = 1 + ((R - r) * t) / r;
        p.x = c[0] + dx * k; p.z = c[1] + dz * k;
      }
    }
    p.addScaledVector(nn, thick);
  };
  return bodyPiece(body, select, offset, uniforms, { bottomY: bottom, hideBottom: spec.tucked });
}

function buildPants(body, uniforms) {
  const J = body.lm.joints, lm = body.lm;
  const P = body.body.geometry.attributes.position.array;
  const W = regionWeights(body);
  const ankle = J.LeftFoot.y + 0.07;
  const select = (i) => {
    const w = W(i);
    const yy = P[i * 3 + 1];
    return w.torso + w.upleg + w.leg >= 0.6 && w.arm + w.fore + w.hand < 0.3 && w.foot < 0.4 && yy > ankle && yy < lm.waist + 0.01;
  };
  const offset = (i, p, nn) => {
    const yy = p.y;
    const side = p.x > 0 ? 'Left' : 'Right';
    // évasement léger vers le bas, autour de l'axe de la jambe
    const flare = 0.016 * ss(J[`${side}Leg`].y - yy, -0.05, 0.4);
    const axis = J[`${side}Leg`].clone().lerp(J[`${side}Foot`], THREE.MathUtils.clamp((J[`${side}Leg`].y - yy) / (J[`${side}Leg`].y - J[`${side}Foot`].y), 0, 1));
    const radial = new THREE.Vector3(p.x - axis.x, 0, p.z - axis.z).normalize();
    p.addScaledVector(nn, 0.011).addScaledVector(radial, yy < J[`${side}Leg`].y ? flare : 0);
  };
  return bodyPiece(body, select, offset, { uMap: { value: null }, uScale: { value: 1 }, uHasMap: { value: 0 } }, { color: 0x2b2a2e });
}

// ---------- Jupe simulée ----------
class Skirt {
  constructor(body, spec, uniforms, scene) {
    this.body = body;
    const J = body.restJ, lm = body.lm;
    const s = body.scale ?? 1;
    const yTop = spec.from === 'waist' ? lm.waist + 0.01 : lm.hip - 0.035;
    const yHem = {
      floor: 0.06, ankle: J.LeftFoot.y + 0.06, midcalf: (J.LeftLeg.y + J.LeftFoot.y) / 2 - 0.02,
      knee: J.LeftLeg.y - 0.03, midthigh: (J.LeftUpLeg.y + J.LeftLeg.y) / 2,
    }[spec.to];
    const R = Math.max(12, Math.round((yTop - yHem) / 0.034) + 1);
    this.R = R; this.M = 96;

    // Gabarit du corps au repos (sans les bras) : ellipse par hauteur.
    const rp = body.restPos;
    const W = regionWeights(body);
    const n = rp.length / 3;
    const keep = [];
    for (let i = 0; i < n; i++) {
      const w = W(i);
      if (w.arm + w.fore + w.hand < 0.2 && w.head + w.neck < 0.2) keep.push(i);
    }
    // Coupe du corps à une hauteur : enveloppe convexe (le tissu passe par-dessus les creux).
    const sectionAt = (yy) => {
      const pts = [];
      for (const i of keep) if (Math.abs(rp[i * 3 + 1] - yy) < 0.012) pts.push([rp[i * 3], rp[i * 3 + 2]]);
      if (pts.length < 8) return null;
      const h = hull2d(pts);
      let zmin = Infinity, zmax = -Infinity;
      for (const q of h.pts) { zmin = Math.min(zmin, q[1]); zmax = Math.max(zmax, q[1]); }
      return { hull: h.pts, cz: (zmin + zmax) / 2 };
    };
    const M = 96;
    const kneeY = J.LeftLeg.y;
    const crotchY = J.LeftUpLeg.y - 0.06;
    const rings = [];
    let last = null;
    for (let i = 0; i < R; i++) {
      const yy = yTop - (i / (R - 1)) * (yTop - yHem);
      const sec = sectionAt(Math.max(yy, J.LeftFoot.y + 0.03));
      const radii = new Float32Array(M);
      const cz = sec ? sec.cz : last.cz;
      let grow = 0;
      if (spec.cut === 'fitted') {
        const t = Math.max(0, kneeY + 0.06 - yy);
        grow = spec.flare * t * (0.6 + 0.4 * Math.min(1, t / 0.35));
      } else grow = (spec.flare * (yTop - yy)) / (yTop - yHem) * 0.5;
      const base = new Float32Array(M);
      const bodyR = sec && yy > crotchY ? new Float32Array(M) : null;
      // Plis : godets qui s'ouvrent vers l'ourlet, fronces sous la ceinture.
      const t = i / (R - 1);
      const drop = yTop - yy;
      let godet = 0, nGodet = 9, gather = 0;
      if (spec.cut === 'aline') { godet = 0.024 * t ** 1.3; gather = spec.from === 'waist' ? 0.006 * Math.max(0, 1 - drop / 0.16) : 0; }
      else if (spec.cut === 'fitted') { godet = 0.03 * Math.min(1, Math.max(0, kneeY + 0.06 - yy) / 0.4) ** 1.2; nGodet = 7; }
      else { godet = 0.009 * t; nGodet = 11; gather = spec.from === 'waist' ? 0.004 * Math.max(0, 1 - drop / 0.12) : 0; }
      for (let j = 0; j < M; j++) {
        const th = (j / M) * Math.PI * 2;
        const dx = Math.sin(th), dz = Math.cos(th);
        const body0 = sec ? rayHull(sec.hull, [0, cz], dx, dz) : last.body0[j];
        if (bodyR) bodyR[j] = body0;
        const fit = body0 + 0.013;
        let r = fit + (spec.cut === 'fitted' ? grow : 0);
        if (spec.cut !== 'fitted' && i > 0) r = Math.max(fit, rings[0].base[j] + grow, last.base[j]);
        base[j] = r;
        radii[j] = r + godet * (0.5 + 0.5 * Math.sin(nGodet * th + 0.7)) + gather * (0.5 + 0.5 * Math.sin(32 * th));
      }
      const body0 = new Float32Array(M);
      for (let j = 0; j < M; j++) body0[j] = base[j] - 0.013;
      last = { radii, base, body0, bodyR, cz, y: yy };
      rings.push(last);
    }
    this.rings = rings;

    // Positions de repos (repère du bassin), particules, liens.
    const hips = J.Hips;
    this.hipsZ = hips.z;
    this.hipsY = hips.y;
    this.give = spec.cut === 'aline' ? 1.0 : 1.06; // légère élasticité des coupes ajustées
    // Une jupe étroite limite l'amplitude des jambes (pas plus court).
    this.legFreedom = spec.cut === 'aline' ? 1 : spec.cut === 'straight' ? 0.55 : 0.45;
    const count = R * M;
    this.local = new Float32Array(count * 3);
    for (let i = 0; i < R; i++) for (let j = 0; j < M; j++) {
      const th = (j / M) * Math.PI * 2;
      const r = rings[i];
      this.local.set([r.radii[j] * Math.sin(th), r.y - hips.y, r.cz - hips.z + r.radii[j] * Math.cos(th)], (i * M + j) * 3);
    }
    this.pos = new Float32Array(count * 3);
    this.prev = new Float32Array(count * 3);
    this.target = new Float32Array(count * 3);
    const links = [];
    const L = this.local;
    const dist = (a, b) => Math.hypot(L[a * 3] - L[b * 3], L[a * 3 + 1] - L[b * 3 + 1], L[a * 3 + 2] - L[b * 3 + 2]);
    for (let i = 0; i < R; i++) for (let j = 0; j < M; j++) {
      const a = i * M + j;
      const h = i * M + ((j + 1) % M);
      links.push(a, h, dist(a, h) * s, 1);
      if (i < R - 1) { const v = a + M; links.push(a, v, dist(a, v) * s, 0); }
      if (i < R - 2) { const v2 = a + 2 * M; links.push(a, v2, dist(a, v2) * s, 2); }
    }
    this.links = new Float32Array(links);
    // Raideur de forme : forte à la taille, souple vers l'ourlet.
    this.stiff = new Float32Array(R);
    for (let i = 0; i < R; i++) {
      const t = i / (R - 1);
      this.stiff[i] = spec.cut === 'fitted' && rings[i].y > kneeY + 0.06 ? 0.22 - 0.12 * t : 0.12 * (1 - t) ** 2 + 0.008;
    }

    // Rayons des jambes (pour les collisions), mesurés sur le corps au repos.
    const legR = (side, yy) => {
      const c = J[`${side}UpLeg`];
      let m = 0;
      for (const i of keep) {
        const px = rp[i * 3];
        if (Math.sign(px) !== (side === 'Left' ? 1 : -1) || Math.abs(rp[i * 3 + 1] - yy) > 0.01) continue;
        m = Math.max(m, Math.hypot(px - c.x, rp[i * 3 + 2] - c.z));
      }
      return m || 0.05;
    };
    this.legRadii = ['Left', 'Right'].map((side) => ({
      side,
      // rayons pris au plus large (cuisse galbée, genou) : le genou ne perce pas la jupe
      thigh: [Math.max(legR(side, J[`${side}UpLeg`].y - 0.12), legR(side, J[`${side}UpLeg`].y - 0.2)) * 1.04, Math.max(legR(side, J[`${side}Leg`].y + 0.06), legR(side, J[`${side}Leg`].y)) * 1.08],
      calf: [legR(side, J[`${side}Leg`].y - 0.08) * 1.06, legR(side, J[`${side}Foot`].y + 0.08) * 1.05],
    }));

    // Maillage de rendu (colonne de couture dupliquée pour le motif).
    const vc = R * (M + 1);
    const g = new THREE.BufferGeometry();
    this.renderPos = new Float32Array(vc * 3);
    const rest = new Float32Array(vc * 3), rn = new Float32Array(vc * 3), uv = new Float32Array(vc * 2);
    for (let i = 0; i < R; i++) {
      const r = rings[i];
      let circ = 0;
      for (let j = 0; j < M; j++) circ += dist(i * M + j, i * M + ((j + 1) % M));
      for (let j = 0; j <= M; j++) {
        const k = i * (M + 1) + j, src = i * M + (j % M);
        rest.set([L[src * 3] + hips.x, L[src * 3 + 1] + hips.y, L[src * 3 + 2] + hips.z], k * 3);
        const th = (j / M) * Math.PI * 2;
        rn.set([Math.sin(th), 0, Math.cos(th)], k * 3);
        uv.set([(j / M) * circ, (yTop - r.y) * 1.0], k * 2);
      }
    }
    const index = [];
    for (let i = 0; i < R - 1; i++) for (let j = 0; j < M; j++) {
      const a = i * (M + 1) + j, b = a + 1, c = a + M + 1, d = c + 1;
      index.push(a, c, b, b, c, d);
    }
    g.setAttribute('position', new THREE.BufferAttribute(this.renderPos, 3));
    g.setAttribute('restPos', new THREE.BufferAttribute(rest, 3));
    g.setAttribute('restNormal', new THREE.BufferAttribute(rn, 3));
    g.setAttribute('fabricUv', new THREE.BufferAttribute(uv, 2));
    g.setIndex(index);
    this.geo = g;
    this.mesh = new THREE.Mesh(g, fabricMaterial(uniforms, { mode: 'uv', side: THREE.DoubleSide }));
    this.mesh.castShadow = this.mesh.receiveShadow = true;
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);

    // Ceinture : bande unie qui couvre la couture entre le haut et la jupe.
    const bandH = spec.from === 'waist' ? 0.04 : 0.018;
    const r0 = rings[0];
    const bandGeo = new THREE.BufferGeometry();
    const bp = [], bn = [], bi = [];
    for (let j = 0; j <= M; j++) {
      const th = (j / M) * Math.PI * 2;
      // la ceinture recouvre les fronces de la jupe sur toute sa hauteur
      let rr = 0;
      for (const ring of rings) if (ring.y > r0.y - bandH * 0.7) rr = Math.max(rr, ring.radii[j % M]);
      rr += 0.008;
      for (const dy of [-bandH * 0.6, bandH * 0.4]) {
        bp.push(Math.sin(th) * rr, r0.y - hips.y + dy, r0.cz - hips.z + Math.cos(th) * rr);
        bn.push(Math.sin(th), 0, Math.cos(th));
      }
      if (j < M) { const a = j * 2; bi.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    bandGeo.setAttribute('position', new THREE.Float32BufferAttribute(bp, 3));
    bandGeo.setAttribute('normal', new THREE.Float32BufferAttribute(bn, 3));
    bandGeo.setIndex(bi);
    const trimMat = new THREE.MeshStandardMaterial({ roughness: 0.7, side: THREE.DoubleSide });
    trimMat.color = uniforms.trim;
    this.band = new THREE.Mesh(bandGeo, trimMat);
    this.band.castShadow = true;
    body.bones.Hips.add(this.band);

    // Ourlet roulé : petit boudin qui suit le bas de la jupe.
    this.hem = new LoopTube(M, 0.0042, trimMat);
    scene.add(this.hem.mesh);
    this.reset();
  }

  /** Profondeur (m, repère du bassin non mis à l'échelle) d'un point à l'intérieur de la jupe ; < 0 s'il est dehors. */
  penetration(lx, ly, lz) {
    const y = ly + this.hipsY;
    const rs = this.rings;
    if (y > rs[0].y + 0.02 || y < rs.at(-1).y) return -1;
    let i = rs.findIndex((r) => r.y <= y);
    if (i < 0) i = rs.length - 1;
    const r = rs[i];
    const dz = lz - (r.cz - this.hipsZ);
    const d = Math.hypot(lx, dz);
    let a = Math.atan2(lx, dz) / (Math.PI * 2);
    if (a < 0) a += 1;
    const f = a * this.M, j0 = f | 0, w = f - j0;
    const R = r.radii[j0 % this.M] * (1 - w) + r.radii[(j0 + 1) % this.M] * w;
    return R - d;
  }

  computeTargets() {
    const hm = this.body.bones.Hips.matrixWorld;
    this.hipsM = hm.elements;
    this.invHips = (this._inv ||= new THREE.Matrix4()).copy(hm).invert().elements;
    const m = hm.elements;
    const L = this.local, T = this.target;
    for (let k = 0; k < L.length; k += 3) {
      const x = L[k], y = L[k + 1], z = L[k + 2];
      T[k] = m[0] * x + m[4] * y + m[8] * z + m[12];
      T[k + 1] = m[1] * x + m[5] * y + m[9] * z + m[13];
      T[k + 2] = m[2] * x + m[6] * y + m[10] * z + m[14];
    }
  }

  reset() {
    this.body.root.updateMatrixWorld(true);
    this.computeTargets();
    this.pos.set(this.target);
    this.prev.set(this.target);
    this.caps = this.colliders();
    this.acc = 0;
    for (let k = 0; k < 40; k++) this.step(1 / 60, true);
    this.writeRender();
  }

  colliders() {
    const b = this.body.bones;
    const s = this.body.root.scale.x;
    const caps = [];
    const wp = (name) => b[name].getWorldPosition(new THREE.Vector3());
    for (const lr of this.legRadii) {
      caps.push([wp(`${lr.side}UpLeg`), wp(`${lr.side}Leg`), lr.thigh[0] * s, lr.thigh[1] * s]);
      caps.push([wp(`${lr.side}Leg`), wp(`${lr.side}Foot`), lr.calf[0] * s, lr.calf[1] * s]);
      // Les mains et avant-bras repoussent le tissu au lieu de le traverser.
      const hand = wp(`${lr.side}Hand`);
      const tip = new THREE.Vector3(0, -0.17 * s, 0).applyQuaternion(b[`${lr.side}Hand`].getWorldQuaternion(new THREE.Quaternion())).add(hand);
      caps.push([wp(`${lr.side}ForeArm`), hand, 0.034 * s, 0.026 * s]);
      caps.push([hand, tip, 0.028 * s, 0.016 * s]);
    }
    return caps;
  }

  step(dt, settle = false) {
    const { pos, prev, target, R, M } = this;
    const g = -9.81 * dt * dt;
    const damp = settle ? 0.6 : 0.985;
    for (let i = 1; i < R; i++) {
      const k0 = this.stiff[i] * (i < 3 ? 1 : this.soft ?? 1);
      for (let j = 0; j < M; j++) {
        const k = (i * M + j) * 3;
        for (let c = 0; c < 3; c++) {
          const v = (pos[k + c] - prev[k + c]) * damp;
          prev[k + c] = pos[k + c];
          pos[k + c] += v + (c === 1 ? g : 0);
          pos[k + c] += (target[k + c] - pos[k + c]) * k0;
        }
      }
    }
    const caps = this.caps;
    const thick = 0.011 * this.body.root.scale.x;
    const floorY = this.floorY ?? 0;
    const box = this.box;
    const links = this.links;
    for (let it = 0; it < 4; it++) {
      for (let l = 0; l < links.length; l += 4) {
        const a = links[l] * 3, b = links[l + 1] * 3, rest = links[l + 2], type = links[l + 3];
        const dx = pos[b] - pos[a], dy = pos[b + 1] - pos[a + 1], dz = pos[b + 2] - pos[a + 2];
        const d = Math.hypot(dx, dy, dz) || 1e-9;
        // le tissu résiste à l'étirement, plisse librement à la compression (sauf en vertical)
        if (type === 1 && d < rest * this.give) continue;
        if (type === 2 && d > rest * 0.98) continue;
        const target = type === 1 ? rest * this.give : rest;
        const diff = ((d - target) / d) * (type === 2 ? 0.25 : 0.5);
        const wa = a < M * 3 ? 0 : 1, wb = b < M * 3 ? 0 : 1;
        const sum = wa + wb || 1;
        pos[a] += dx * diff * (wa / sum) * 2; pos[a + 1] += dy * diff * (wa / sum) * 2; pos[a + 2] += dz * diff * (wa / sum) * 2;
        pos[b] -= dx * diff * (wb / sum) * 2; pos[b + 1] -= dy * diff * (wb / sum) * 2; pos[b + 2] -= dz * diff * (wb / sum) * 2;
      }
      // accroche à la taille
      for (let j = 0; j < M * 3; j++) pos[j] = target[j];
      // collisions : jambes, socle, sol
      for (let k = M * 3; k < pos.length; k += 3) {
        let px = pos[k], py = pos[k + 1], pz = pos[k + 2];
        for (const [A, B, ra, rb] of caps) {
          const ex = B.x - A.x, ey = B.y - A.y, ez = B.z - A.z;
          const len2 = ex * ex + ey * ey + ez * ez || 1e-9;
          let t = ((px - A.x) * ex + (py - A.y) * ey + (pz - A.z) * ez) / len2;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const cx = A.x + ex * t, cy = A.y + ey * t, cz = A.z + ez * t;
          const r = ra + (rb - ra) * t + thick;
          const ox = px - cx, oy = py - cy, oz = pz - cz;
          const d = Math.hypot(ox, oy, oz);
          if (d < r && d > 1e-6) { const f = r / d; px = cx + ox * f; py = cy + oy * f; pz = cz + oz * f; }
        }
        const ring = this.rings[(k / 3 / M) | 0];
        if (ring.bodyR) {
          const e = this.invHips;
          const lx = e[0] * px + e[4] * py + e[8] * pz + e[12];
          const ly = e[1] * px + e[5] * py + e[9] * pz + e[13];
          const lz = e[2] * px + e[6] * py + e[10] * pz + e[14] - (ring.cz - this.hipsZ);
          const rr = Math.hypot(lx, lz);
          let a = Math.atan2(lx, lz) / (Math.PI * 2);
          if (a < 0) a += 1;
          const f = a * M, j0 = f | 0, w = f - j0;
          const minR = ring.bodyR[j0 % M] * (1 - w) + ring.bodyR[(j0 + 1) % M] * w + 0.006;
          if (rr < minR && rr > 1e-6) {
            const q = minR / rr;
            const nx = lx * q, nz = lz * q + (ring.cz - this.hipsZ);
            const m = this.hipsM;
            px = m[0] * nx + m[4] * ly + m[8] * nz + m[12];
            py = m[1] * nx + m[5] * ly + m[9] * nz + m[13];
            pz = m[2] * nx + m[6] * ly + m[10] * nz + m[14];
          }
        }
        if (box && px > box.x0 && px < box.x1 && pz > box.z0 && pz < box.z1 && py < box.top + thick) {
          const pen = [box.top + thick - py, px - box.x0, box.x1 - px, pz - box.z0, box.z1 - pz];
          const m = pen.indexOf(Math.min(...pen));
          if (m === 0) py = box.top + thick; else if (m === 1) px = box.x0; else if (m === 2) px = box.x1; else if (m === 3) pz = box.z0; else pz = box.z1;
        }
        if (py < floorY + thick) py = floorY + thick;
        pos[k] = px; pos[k + 1] = py; pos[k + 2] = pz;
      }
    }
  }

  update(dt, env) {
    this.floorY = env.floorY;
    this.soft = env.seated ? 0.25 : 1;
    this.box = env.box;
    this.computeTargets();
    this.caps = this.colliders();
    const h = 1 / 90;
    this.acc = Math.min(this.acc + dt, h * 4);
    while (this.acc >= h) { this.step(h); this.acc -= h; }
    this.writeRender();
  }

  writeRender() {
    const { pos, renderPos, R, M } = this;
    for (let i = 0; i < R; i++) for (let j = 0; j <= M; j++) {
      const s = (i * M + (j % M)) * 3, d = (i * (M + 1) + j) * 3;
      renderPos[d] = pos[s]; renderPos[d + 1] = pos[s + 1]; renderPos[d + 2] = pos[s + 2];
    }
    this.geo.attributes.position.needsUpdate = true;
    this.geo.computeVertexNormals();
    if (this.hem) this.hem.update(pos, (R - 1) * M, this.body.root.scale.x);
    // normales lissées sur la couture
    const nr = this.geo.attributes.normal.array;
    for (let i = 0; i < R; i++) {
      const a = i * (M + 1) * 3, b = (i * (M + 1) + M) * 3;
      for (let c = 0; c < 3; c++) { const v = (nr[a + c] + nr[b + c]) / 2; nr[a + c] = nr[b + c] = v; }
    }
  }

  dispose() {
    this.mesh.parent?.remove(this.mesh);
    this.geo.dispose();
    this.mesh.material.dispose();
    this.band.parent?.remove(this.band); this.band.geometry.dispose(); this.band.material.dispose();
    this.hem.mesh.parent?.remove(this.hem.mesh); this.hem.mesh.geometry.dispose();
  }
}

// ---------- Assemblage d'une tenue ----------
export function buildOutfit(body, outfit, uniforms, scene) {
  const parts = [];
  let skirt = null;
  if (outfit?.top) { const m = buildTop(body, { ...outfit.top, tucked: !!outfit.skirt }, uniforms); if (m) parts.push(m); }
  if (outfit?.pants) { const m = buildPants(body, uniforms); if (m) parts.push(m); }
  if (outfit?.skirt) skirt = new Skirt(body, outfit.skirt, uniforms, scene);
  if (outfit?.mesh && hasDress(outfit.mesh)) {
    skirt = new DressCloth(body, outfit.mesh, fabricMaterial(uniforms, { mode: 'uv', side: THREE.DoubleSide }), scene);
  }
  return {
    skirt,
    legFreedom: skirt?.legFreedom ?? 1,
    /** Demi-largeur de la tenue (côtés) à une hauteur du mannequin au repos. */
    halfWidthAt(y) {
      if (!skirt) return 0;
      if (skirt.halfWidthAt) return skirt.halfWidthAt(y);
      const rs = skirt.rings;
      if (y > rs[0].y || y < rs.at(-1).y) return 0;
      const i = rs.findIndex((r) => r.y <= y);
      const r = rs[Math.max(0, i)];
      // largeur réelle sur les côtés (plis compris), là où pendent les mains
      let w = 0;
      for (let j = 0; j < skirt.M; j++) w = Math.max(w, Math.abs(r.radii[j] * Math.sin((j / skirt.M) * Math.PI * 2)));
      return w;
    },
    /** Un point du monde est-il dans la jupe ? (profondeur en m) */
    penetration(world, hipsBone, scale) {
      if (!skirt) return -1;
      const l = hipsBone.worldToLocal(world.clone());
      return skirt.penetration(l.x, l.y, l.z) * 1 + 0 * scale;
    },
    update(dt, env) { skirt?.update(dt, env); },
    reset() { skirt?.reset(); },
    dispose() {
      for (const m of parts) {
        for (const e of [m, ...(m.userData.extra || [])]) { e.parent?.remove(e); e.geometry.dispose(); e.material.dispose(); }
      }
      skirt?.dispose();
    },
  };
}

// ---------- Finitions : bords, passepoil, ourlet ----------
function boundaryLoops(tris, count) {
  const edges = new Map();
  const key = (a, b) => (a < b ? a * count + b : b * count + a);
  for (let t = 0; t < tris.length; t += 3) {
    for (const [a, b] of [[tris[t], tris[t + 1]], [tris[t + 1], tris[t + 2]], [tris[t + 2], tris[t]]]) {
      const k = key(a, b);
      edges.set(k, edges.has(k) ? null : [a, b]);
    }
  }
  const next = new Map();
  for (const e of edges.values()) if (e) { next.set(e[0], e[1]); }
  const seen = new Set(), loops = [];
  for (const start of next.keys()) {
    if (seen.has(start)) continue;
    const loop = [];
    let v = start;
    while (v !== undefined && !seen.has(v)) { seen.add(v); loop.push(v); v = next.get(v); }
    if (loop.length >= 8 && v === start) loops.push(loop);
  }
  return loops;
}

/** Biais tubulaire le long des bords d'une pièce skinnée (mêmes poids que le bord). */
function pipingMesh(g, loops, color, radius) {
  const P = g.attributes.position.array, N = g.attributes.normal.array;
  const SI = g.attributes.skinIndex.array, SW = g.attributes.skinWeight.array;
  const S = 6;
  const pos = [], nrm = [], si = [], sw = [], idx = [];
  const t = new THREE.Vector3(), n = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (const loop of loops) {
    const base = pos.length / 3;
    const L = loop.length;
    loop.forEach((v, k) => {
      const a = loop[(k - 1 + L) % L], d = loop[(k + 1) % L];
      t.set(P[d * 3] - P[a * 3], P[d * 3 + 1] - P[a * 3 + 1], P[d * 3 + 2] - P[a * 3 + 2]).normalize();
      n.fromArray(N, v * 3);
      b.crossVectors(t, n).normalize();
      n.crossVectors(b, t).normalize();
      c.fromArray(P, v * 3);
      for (let r = 0; r < S; r++) {
        const ang = (r / S) * Math.PI * 2;
        const ox = Math.cos(ang), oy = Math.sin(ang);
        pos.push(c.x + (n.x * ox + b.x * oy) * radius, c.y + (n.y * ox + b.y * oy) * radius, c.z + (n.z * ox + b.z * oy) * radius);
        nrm.push(n.x * ox + b.x * oy, n.y * ox + b.y * oy, n.z * ox + b.z * oy);
        for (let q = 0; q < 4; q++) { si.push(SI[v * 4 + q]); sw.push(SW[v * 4 + q]); }
      }
      const k2 = (k + 1) % L;
      for (let r = 0; r < S; r++) {
        const a0 = base + k * S + r, a1 = base + k * S + ((r + 1) % S), b0 = base + k2 * S + r, b1 = base + k2 * S + ((r + 1) % S);
        idx.push(a0, b0, a1, a1, b0, b1);
      }
    });
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
  geo.setAttribute('skinIndex', new THREE.Uint8BufferAttribute(si, 4));
  geo.setAttribute('skinWeight', new THREE.Uint8BufferAttribute(sw, 4, true));
  geo.setIndex(idx);
  const mat = new THREE.MeshStandardMaterial({ roughness: 0.65 });
  mat.color = color;
  const mesh = new THREE.SkinnedMesh(geo, mat);
  mesh.castShadow = true;
  mesh.frustumCulled = false;
  return mesh;
}

/** Boudin le long d'une boucle de particules (ourlet de la jupe simulée). */
class LoopTube {
  constructor(M, radius, material) {
    this.M = M; this.radius = radius; this.S = 6;
    const S = this.S;
    this.pos = new Float32Array(M * S * 3);
    const idx = [];
    for (let k = 0; k < M; k++) for (let r = 0; r < S; r++) {
      const a0 = k * S + r, a1 = k * S + ((r + 1) % S), b0 = ((k + 1) % M) * S + r, b1 = ((k + 1) % M) * S + ((r + 1) % S);
      idx.push(a0, b0, a1, a1, b0, b1);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    g.setIndex(idx);
    this.mesh = new THREE.Mesh(g, material);
    this.mesh.castShadow = true;
    this.mesh.frustumCulled = false;
  }
  update(src, start, scale) {
    const { M, S, pos } = this;
    const r = this.radius * scale;
    let cx = 0, cz = 0;
    for (let k = 0; k < M; k++) { cx += src[(start + k) * 3]; cz += src[(start + k) * 3 + 2]; }
    cx /= M; cz /= M;
    for (let k = 0; k < M; k++) {
      const p = (start + k) * 3, a = (start + ((k - 1 + M) % M)) * 3, b = (start + ((k + 1) % M)) * 3;
      const tx = src[b] - src[a], ty = src[b + 1] - src[a + 1], tz = src[b + 2] - src[a + 2];
      const tl = Math.hypot(tx, ty, tz) || 1;
      let nx = src[p] - cx, nz = src[p + 2] - cz;
      const nl = Math.hypot(nx, nz) || 1; nx /= nl; nz /= nl;
      // binormale = t × n (n horizontal)
      const bx = (ty / tl) * nz, by = (tz / tl) * nx - (tx / tl) * nz, bz = -(ty / tl) * nx;
      for (let q = 0; q < S; q++) {
        const ang = (q / S) * Math.PI * 2, ox = Math.cos(ang) * r, oy = Math.sin(ang) * r;
        const o = (k * S + q) * 3;
        pos[o] = src[p] + nx * ox + bx * oy;
        pos[o + 1] = src[p + 1] + by * oy;
        pos[o + 2] = src[p + 2] + nz * ox + bz * oy;
      }
    }
    this.mesh.geometry.attributes.position.needsUpdate = true;
    this.mesh.geometry.computeVertexNormals();
  }
}

// ---------- Géométrie plane ----------
function hull2d(points) {
  const p = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const q of p) { while (lo.length >= 2 && cr(lo.at(-2), lo.at(-1), q) <= 0) lo.pop(); lo.push(q); }
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cr(up.at(-2), up.at(-1), q) <= 0) up.pop(); up.push(q); }
  const pts = lo.slice(0, -1).concat(up.slice(0, -1));
  const center = pts.reduce((c, q) => [c[0] + q[0] / pts.length, c[1] + q[1] / pts.length], [0, 0]);
  return { pts, center };
}

/** Distance du centre au bord de l'enveloppe, dans la direction (dx, dz). */
function rayHull(pts, c, dx, dz) {
  let best = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const ex = b[0] - a[0], ez = b[1] - a[1];
    const den = dx * ez - dz * ex;
    if (Math.abs(den) < 1e-9) continue;
    const t = ((a[0] - c[0]) * ez - (a[1] - c[1]) * ex) / den;
    const u = ((a[0] - c[0]) * dz - (a[1] - c[1]) * dx) / den;
    if (t > 0 && u >= 0 && u <= 1) best = Math.max(best, t);
  }
  return best;
}
