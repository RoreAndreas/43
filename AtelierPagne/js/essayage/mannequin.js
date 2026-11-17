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
    DATA[id] = { meta, pos, skinIndex, skinWeight, index };
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
  const nc = meta.neckCut, hd = meta.head;
  const slope = (J.Head.z - J.Neck.z) / (J.Head.y - J.Neck.y); // le cou penche vers l'avant
  const czAt = (y) => nc.cz + (y - nc.y) * slope;
  const nr = (y, f) => ({ y, rx: nc.rx * f, zf: nc.rz * f, zb: nc.rz * f, cz: czAt(y) });
  const neckGeo = loftGeometry([
    nr(nc.y - 0.05, 0.99), nr(nc.y - 0.01, 1.03), nr(nc.y + 0.004, 1.035), nr(hd.chin + 0.02, 0.98), nr(hd.chin + 0.07, 0.94),
    { ...nr(hd.chin + 0.08, 0.2) },
  ], { seg: 48, yOffset: J.Neck.y });
  neckGeo.translate(0, 0, -J.Neck.z);
  const neckMesh = new THREE.Mesh(neckGeo, material);
  bones.Neck.add(neckMesh);

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

  // ---------- Position de repos ----------
  const rest = {};
  for (const name of B) {
    const r = REST[name];
    rest[name] = r ? new THREE.Quaternion().setFromEuler(new THREE.Euler(...r)) : new THREE.Quaternion();
    bones[name].quaternion.copy(rest[name]);
  }
  root.updateMatrixWorld(true);

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
    root, bones, rest, meshes, body, tapes, halfWidthAt, material,
    lm: { ...lm, joints: J, thigh: J.LeftUpLeg.distanceTo(J.LeftLeg) },
    lowestSole: () => lowest(meta.soles),
    lowestSeat: () => lowest(meta.seat),
  };
}
