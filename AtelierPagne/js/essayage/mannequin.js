// Mannequin de vitrine : corps réaliste et lisse (maillage MakeHuman, CC0),
// tête ovale sans visage, gris clair.
// Le maillage est préparé hors ligne par tools/build_mannequin.py :
// assets/mannequin/<silhouette>.bin (géométrie + poids) et .json (articulations,
// repères de mesure). Le squelette reprend les noms d'os standards (Hips,
// Spine, LeftArm…) ; les poses de poses.js s'y appliquent telles quelles.
import * as THREE from 'three';
import { loftGeometry, convexHull, perimeter } from './geometry.js';

export const PRESETS = {
  femme: { id: 'femme', label: 'Femme', scale: 1 },
  homme: { id: 'homme', label: 'Homme', scale: 1 },
};

const DATA = {};

/** Charge les deux silhouettes (à appeler une fois au démarrage). */
export async function loadMannequins(base = 'assets/mannequin/') {
  await Promise.all(Object.keys(PRESETS).map(async (id) => {
    const [meta, bin] = await Promise.all([
      fetch(`${base}${id}.json`).then((r) => r.json()),
      fetch(`${base}${id}.bin`).then((r) => r.arrayBuffer()),
    ]);
    const n = meta.vertexCount;
    let o = 0;
    const pos = new Float32Array(bin, o, n * 3); o += n * 12;
    const skinIndex = new Uint8Array(bin, o, n * 4); o += n * 4;
    const skinWeight = new Uint8Array(bin, o, n * 4); o += n * 4;
    const index = new Uint16Array(bin, o, meta.indexCount);
    // animations du modèle (défilé…) : rotations des os image par image
    const clips = Object.fromEntries(await Promise.all((meta.clips || []).map(async (c) => [c, await fetch(`${base}${id}-${c}.json`).then((r) => r.json())])));
    DATA[id] = { meta, pos, skinIndex, skinWeight, index, clips };
  }));
}

export function createSiliconeMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xbdbec1, roughness: 0.55, metalness: 0, sheen: 0.3, sheenRoughness: 0.6, sheenColor: new THREE.Color(0xffffff),
  });
}

const PARENT = {
  Hips: null, Spine: 'Hips', Neck: 'Spine', Head: 'Neck',
  LeftArm: 'Spine', LeftForeArm: 'LeftArm', LeftHand: 'LeftForeArm',
  RightArm: 'Spine', RightForeArm: 'RightArm', RightHand: 'RightForeArm',
  LeftUpLeg: 'Hips', LeftLeg: 'LeftUpLeg', LeftFoot: 'LeftLeg',
  RightUpLeg: 'Hips', RightLeg: 'RightUpLeg', RightFoot: 'RightLeg',
};
// Segments orientés le long du membre (axe local -Y), pour que les poses
// (épaule, coude, hanche, genou) tournent autour des bons axes.
const AIM = {
  LeftArm: 'LeftForeArm', LeftForeArm: 'LeftHand', LeftHand: 'LeftHandTip',
  RightArm: 'RightForeArm', RightForeArm: 'RightHand', RightHand: 'RightHandTip',
  LeftUpLeg: 'LeftLeg', LeftLeg: 'LeftFoot', RightUpLeg: 'RightLeg', RightLeg: 'RightFoot',
};
// Petites corrections de la position de repos (bras le long du corps,
// paumes tournées vers les cuisses).
const REST = {
  LeftForeArm: [0, -0.9, 0], RightForeArm: [0, 0.9, 0],
};

/** Cou skinné : anneaux de l'anneau découpé du corps vers une section ronde sous la tête. */
function buildNeck(nc, hd, J, pos, SI, SW, bi, material) {
  const ring = nc.ring, N = ring.length;
  const top = nc.top;
  const yTop = hd.chin + 0.06;
  const slope = (J.Head.z - J.Neck.z) / (J.Head.y - J.Neck.y); // le cou penche vers l'avant
  const base = ring.map((i) => [pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]]);
  const cx0 = base.reduce((a, p) => a + p[0], 0) / N, cz0 = base.reduce((a, p) => a + p[2], 0) / N;
  const czAt = (y) => top.cz + (y - top.y) * slope;
  // sens de l'anneau (pour orienter les faces vers l'extérieur)
  let area = 0;
  for (let k = 0; k < N; k++) { const a = base[k], b = base[(k + 1) % N]; area += (a[0] - cx0) * (b[2] - cz0) - (b[0] - cx0) * (a[2] - cz0); }
  const U = [0, 0.1, 0.22, 0.38, 0.56, 0.76, 0.92, 1];
  const ss = THREE.MathUtils.smoothstep;
  const P = [], skI = [], skW = [], idx = [];
  U.forEach((u, r) => {
    const shape = ss(u, 0, 0.75);
    const shrink = u > 0.9 ? 1 - (u - 0.9) * 4 : 1; // se referme dans la tête
    const toNeck = ss(u, 0, 0.55);
    base.forEach((p, k) => {
      const ang = Math.atan2(p[0] - cx0, p[2] - cz0);
      const taper = 0.97 - 0.2 * ss(u, 0.45, 1); // s'affine en montant pour rentrer sous la tête
      const ex = Math.sin(ang) * top.rx * taper, ez = Math.cos(ang) * top.rz * taper;
      const x = (p[0] - cx0) * (1 - shape) + ex * shape;
      const z = (p[2] - cz0) * (1 - shape) + ez * shape;
      const y = p[1] + (yTop - p[1]) * u; // chaque point monte depuis sa hauteur réelle
      P.push(x * shrink + cx0 * (1 - shape), y, z * shrink + cz0 * (1 - shape) + czAt(y) * shape);
      // poids : ceux du corps au bord, puis le seul os du cou
      const i = ring[k];
      const w = new Map();
      for (let c = 0; c < 4; c++) { const b = SI[i * 4 + c], v = (SW[i * 4 + c] / 255) * (1 - toNeck); if (v > 0) w.set(b, (w.get(b) || 0) + v); }
      w.set(bi.Neck, (w.get(bi.Neck) || 0) + toNeck);
      const top4 = [...w.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);
      const sum = top4.reduce((a, e) => a + e[1], 0) || 1;
      for (let c = 0; c < 4; c++) { skI.push(top4[c] ? top4[c][0] : 0); skW.push(top4[c] ? top4[c][1] / sum : 0); }
    });
    if (r < U.length - 1) {
      for (let k = 0; k < N; k++) {
        const a = r * N + k, b = r * N + ((k + 1) % N), c = a + N, d = b + N;
        if (area > 0) idx.push(a, c, b, b, c, d); else idx.push(a, b, c, b, d, c);
      }
    }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(skI, 4));
  g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(skW, 4));
  g.setIndex(idx);
  g.computeVertexNormals();
  return new THREE.SkinnedMesh(g, material);
}

const lerpPts = (pts, y) => {
  if (y <= pts[0][0]) return pts[0][1];
  for (let i = 0; i < pts.length - 1; i++) {
    const [y0, v0] = pts[i], [y1, v1] = pts[i + 1];
    if (y <= y1) return v0 + (v1 - v0) * ((y - y0) / (y1 - y0));
  }
  return pts.at(-1)[1];
};

/**
 * @param {object} preset  PRESETS.femme | PRESETS.homme
 * @param {object} k       facteurs radiaux {bust, waist, hip} (mesures client)
 */
export function buildMannequin(preset, k = { bust: 1, waist: 1, hip: 1 }, material = createSiliconeMaterial()) {
  const D = DATA[preset.id];
  if (!D) throw new Error(`Mannequin « ${preset.id} » non chargé`);
  const { meta } = D;
  const J = Object.fromEntries(Object.entries(meta.joints).map(([n, v]) => [n, new THREE.Vector3(...v)]));
  const lm = meta.landmarks;
  const B = meta.bones;
  const bi = Object.fromEntries(B.map((n, i) => [n, i]));

  // ---------- Morphologie : élargit buste, taille, hanches selon les mesures ----------
  const pos = new Float32Array(D.pos);
  const n = meta.vertexCount;
  const upLegY = J.LeftUpLeg.y;
  const factor = (y) => lerpPts([
    [upLegY - 0.28, 1], [upLegY - 0.08, 1 + (k.hip - 1) * 0.6], [lm.hip, k.hip], [lm.waist, k.waist], [lm.bust, k.bust],
    [J.LeftArm.y - 0.02, 1 + (k.bust - 1) * 0.4], [J.Neck.y, 1],
  ], y);
  const centerZ = (y) => lerpPts([[J.Hips.y, J.Hips.z], [J.Spine.y, J.Spine.z], [J.Neck.y, J.Neck.z]], y);
  const torsoW = new Float32Array(n);
  const tW = [bi.Hips, bi.Spine, bi.LeftUpLeg, bi.RightUpLeg];
  for (let i = 0; i < n; i++) {
    let w = 0;
    for (let c = 0; c < 4; c++) if (tW.includes(D.skinIndex[i * 4 + c])) w += D.skinWeight[i * 4 + c] / 255;
    torsoW[i] = w;
    if (w <= 0) continue;
    const y = pos[i * 3 + 1];
    const f = 1 + (factor(y) - 1) * w;
    const cz = centerZ(y);
    pos[i * 3] *= f;
    pos[i * 3 + 2] = cz + (pos[i * 3 + 2] - cz) * f;
  }

  /** Même déformation pour un point proche du corps (vêtement modélisé sur ce mannequin). */
  const morphPoint = (x, y, z, w) => {
    const f = 1 + (factor(y) - 1) * w, cz = centerZ(y);
    return [x * f, y, cz + (z - cz) * f];
  };

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('skinIndex', new THREE.Uint8BufferAttribute(D.skinIndex, 4));
  geo.setAttribute('skinWeight', new THREE.Uint8BufferAttribute(D.skinWeight, 4, true));
  geo.setIndex(new THREE.BufferAttribute(D.index, 1));
  geo.computeVertexNormals();

  // ---------- Squelette, posé sur les articulations du maillage ----------
  const root = new THREE.Group();
  root.name = 'Root';
  const bones = {};
  const bindQ = {};
  const down = new THREE.Vector3(0, -1, 0);
  for (const name of B) {
    bindQ[name] = AIM[name]
      ? new THREE.Quaternion().setFromUnitVectors(down, J[AIM[name]].clone().sub(J[name]).normalize())
      : new THREE.Quaternion();
  }
  for (const name of B) {
    const b = new THREE.Bone();
    b.name = name;
    const p = PARENT[name];
    const pq = p ? bindQ[p].clone().invert() : new THREE.Quaternion();
    b.position.copy(J[name]).sub(p ? J[p] : new THREE.Vector3()).applyQuaternion(pq);
    b.quaternion.copy(pq.multiply(bindQ[name]));
    (p ? bones[p] : root).add(b);
    bones[name] = b;
  }
  root.updateMatrixWorld(true);
  const body = new THREE.SkinnedMesh(geo, material);
  body.castShadow = body.receiveShadow = true;
  body.frustumCulled = false;
  root.add(body);
  root.updateMatrixWorld(true);
  body.bind(new THREE.Skeleton(B.map((name) => bones[name])));
  const meshes = [body];

  // ---------- Cou prolongé et tête ovale sans visage ----------
  // (seulement si la tête du modèle a été retirée : MakeHuman ; le mannequin
  // femme garde la sienne, déjà lisse et sans visage)
  if (meta.neckCut) {
    const nc = meta.neckCut, hd = meta.head;
    // Le cou part exactement du bord découpé du corps (anneau exporté), puis
    // s'arrondit en montant sous la tête : aucune marche ni trait à la jonction.
    // Il est skinné comme le corps : le raccord tient pendant les mouvements.
    const neckMesh = buildNeck(nc, hd, J, pos, D.skinIndex, D.skinWeight, bi, material);
    root.add(neckMesh);
    neckMesh.bind(body.skeleton, body.bindMatrix);
    // normales communes sur l'anneau de jonction : pas de ligne d'éclairage
    {
      const bn = geo.attributes.normal.array, nn = neckMesh.geometry.attributes.normal.array;
      nc.ring.forEach((i, k) => {
        let x = bn[i * 3] + nn[k * 3], y = bn[i * 3 + 1] + nn[k * 3 + 1], z = bn[i * 3 + 2] + nn[k * 3 + 2];
        const l = Math.hypot(x, y, z) || 1; x /= l; y /= l; z /= l;
        bn[i * 3] = nn[k * 3] = x; bn[i * 3 + 1] = nn[k * 3 + 1] = y; bn[i * 3 + 2] = nn[k * 3 + 2] = z;
      });
    }

    // Œuf lisse : gabarit normalisé (hauteur 1, demi-largeur 0.29, profondeur 0.69).
    const H = (hd.top - hd.chin) * 0.97;
    const headGeo = loftGeometry([
      { y: 0, rx: 0.004, zf: 0.004, zb: 0.004, cz: 0.1 },
      { y: 0.035, rx: 0.12, zf: 0.12, zb: 0.12, cz: 0.1 },
      { y: 0.15, rx: 0.205, zf: 0.235, zb: 0.24, cz: 0.06 },
      { y: 0.34, rx: 0.268, zf: 0.31, zb: 0.33, cz: 0.02 },
      { y: 0.55, rx: 0.29, zf: 0.33, zb: 0.36, cz: 0 },
      { y: 0.75, rx: 0.276, zf: 0.3, zb: 0.34, cz: -0.01 },
      { y: 0.9, rx: 0.2, zf: 0.21, zb: 0.25, cz: -0.02 },
      { y: 0.985, rx: 0.08, zf: 0.08, zb: 0.1, cz: -0.02 },
      { y: 1, rx: 0.004, zf: 0.004, zb: 0.004, cz: -0.02 },
    ], { seg: 56 });
    const width = Math.min(hd.rx, 0.078) * 0.94;
    headGeo.scale(width / 0.29, H, ((hd.zf - hd.zb) * 0.86) / 0.69);
    const headMesh = new THREE.Mesh(headGeo, material);
    headMesh.position.set(0, hd.chin + 0.006 - J.Head.y, (hd.zf + hd.zb) / 2 - 0.012 - J.Head.z);
    headMesh.rotation.x = 0.04;
    bones.Head.add(headMesh);
    for (const m of [neckMesh, headMesh]) { m.castShadow = m.receiveShadow = true; meshes.push(m); }
    neckMesh.frustumCulled = false;
  }

  // ---------- Position de repos ----------
  const rest = {};
  const restEuler = meta.rest ?? REST; // le modèle importé est déjà dans la position de repos
  for (const name of B) {
    const r = restEuler[name];
    rest[name] = r ? new THREE.Quaternion().setFromEuler(new THREE.Euler(...r)) : new THREE.Quaternion();
    bones[name].quaternion.copy(rest[name]);
  }
  root.updateMatrixWorld(true);

  // Corps au repos (bras le long du corps, jambes droites), en repère mannequin :
  // sert à tailler les vêtements et à régler leurs collisions.
  const restPos = new Float32Array(n * 3);
  const rv = new THREE.Vector3();
  for (let i = 0; i < n; i++) { body.getVertexPosition(i, rv); restPos.set([rv.x, rv.y, rv.z], i * 3); }
  const restJ = Object.fromEntries(B.map((name) => [name, bones[name].getWorldPosition(new THREE.Vector3())]));
  // passage position de liaison → repos, par os (pour placer un vêtement modélisé sur le maillage)
  const restSkin = body.skeleton.bones.map((b, i) => new THREE.Matrix4().multiplyMatrices(b.matrixWorld, body.skeleton.boneInverses[i]));

  // ---------- Mesures (tour du mètre ruban, sur le maillage au repos) ----------
  const slab = (y, h = 0.007) => {
    const pts = [];
    for (let i = 0; i < n; i++) {
      if (torsoW[i] < 0.6 || Math.abs(pos[i * 3 + 1] - y) > h) continue;
      pts.push([pos[i * 3], pos[i * 3 + 2]]);
    }
    return pts;
  };
  const tape = (key, boneName) => {
    const y = lm[key];
    const hull = convexHull(slab(y));
    const o = J[boneName];
    return {
      hull: hull.map(([x, z]) => [x - o.x, z - o.z]), length: perimeter(hull), y, bone: bones[boneName], yOffset: o.y,
    };
  };
  const tapes = { bust: tape('bust', 'Spine'), waist: tape('waist', 'Spine'), hip: tape('hip', 'Hips') };

  /** Demi-largeur du torse à une hauteur donnée (pour poser les mains). */
  const halfWidthAt = (y) => slab(y, 0.01).reduce((m, [x]) => Math.max(m, Math.abs(x)), 0) || 0.15;

  /** Point le plus bas (repère monde) d'un ensemble de sommets déformés. */
  const v = new THREE.Vector3();
  const lowest = (ids) => {
    let min = Infinity;
    for (const i of ids) {
      body.getVertexPosition(i, v);
      v.applyMatrix4(body.matrixWorld);
      if (v.y < min) min = v.y;
    }
    return min;
  };

  return {
    root, bones, rest, meshes, body, tapes, halfWidthAt, material, restPos, restJ, torsoW, bi, sex: preset.id,
    basePos: D.pos, morphPoint, restSkin, bindQ, clips: D.clips || {}, soleIds: meta.soles,
    lm: { ...lm, joints: J, thigh: J.LeftUpLeg.distanceTo(J.LeftLeg) },
    lowestSole: () => lowest(meta.soles),
    lowestSeat: () => lowest(meta.seat),
  };
}
