// Mannequin de vitrine épuré, gris clair, sans visage.
// Silhouette allongée, tête ovale, long cou, jambes lisses d'un seul tenant ;
// seules les articulations des bras (épaule, coude, poignet) restent visibles,
// dans un gris un peu plus soutenu.
// Le squelette reprend les noms d'os standards (Hips, Spine, LeftArm…) : les
// poses resteront valables avec un mannequin GLB rigué de la même façon.
import * as THREE from 'three';
import { loftGeometry, tapeAt, ringAt } from './geometry.js';

export const PRESETS = {
  femme: {
    label: 'Femme', chest: 0.97, shoulder: 0.98, chestZ: 0.97, bustBump: 0.02, waist: 0.93, hip: 0.97, glute: 0.95,
    limb: 0.9, leg: 0.92, neck: 0.9, head: 0.9, scale: 1,
  },
  homme: {
    label: 'Homme', chest: 1.08, shoulder: 1.16, chestZ: 0.95, bustBump: 0, waist: 1.1, hip: 0.92, glute: 0.82,
    limb: 1.04, leg: 1.02, neck: 1.08, head: 0.96, scale: 1.05,
  },
};

// Hauteurs (repère des sections, avant allongement des jambes) où l'on pose le mètre ruban.
export const TAPE_Y = { bust: 1.25, waist: 1.065, hip: 0.885 };
// Allongement des jambes par rapport aux proportions « standard ».
const EXTRA = 0.05;
const THIGH = 0.435, CALF = 0.435;

const lerpPts = (pts, y) => {
  if (y <= pts[0][0]) return pts[0][1];
  for (let i = 0; i < pts.length - 1; i++) {
    const [y0, v0] = pts[i], [y1, v1] = pts[i + 1];
    if (y <= y1) return v0 + (v1 - v0) * ((y - y0) / (y1 - y0));
  }
  return pts.at(-1)[1];
};

export function createSiliconeMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xbdbec1, roughness: 0.58, metalness: 0, sheen: 0.25, sheenRoughness: 0.7, sheenColor: new THREE.Color(0xffffff),
  });
}
const jointMaterial = new THREE.MeshStandardMaterial({ color: 0x9fa1a5, roughness: 0.45 });

/** Pose les poids de peau (2 os) le long de y, avec une zone de fondu. */
function skin(geo, from, to) {
  const pos = geo.attributes.position;
  const idx = new Uint16Array(pos.count * 4), w = new Float32Array(pos.count * 4);
  for (let i = 0; i < pos.count; i++) {
    const t = THREE.MathUtils.smoothstep(pos.getY(i), from, to);
    idx.set([0, 1, 0, 0], i * 4);
    w.set([1 - t, t, 0, 0], i * 4);
  }
  geo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4));
  geo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(w, 4));
}

/**
 * @param {object} preset  PRESETS.femme | PRESETS.homme
 * @param {object} k       facteurs radiaux {bust, waist, hip} (mesures client)
 */
export function buildMannequin(preset, k = { bust: 1, waist: 1, hip: 1 }, material = createSiliconeMaterial()) {
  const P = preset;
  const L = P.limb;
  const bones = {};
  const meshes = [];

  const bone = (name, parent, x, y, z) => {
    const b = new THREE.Bone();
    b.name = name;
    b.position.set(x, y, z);
    parent.add(b);
    bones[name] = b;
    return b;
  };
  const mesh = (geo, parent, tag, mat = material) => {
    const m = new THREE.Mesh(geo, mat);
    m.castShadow = true;
    m.receiveShadow = true;
    m.userData.tag = tag;
    parent.add(m);
    meshes.push(m);
    return m;
  };
  const joint = (r, parent) => mesh(new THREE.SphereGeometry(r, 32, 20), parent, 'joint', jointMaterial);
  const skinned = (geo, boneList, tag) => {
    root.updateMatrixWorld(true);
    const m = new THREE.SkinnedMesh(geo, material);
    m.castShadow = m.receiveShadow = true;
    m.frustumCulled = false;
    m.userData.tag = tag;
    root.add(m);
    root.updateMatrixWorld(true);
    m.bind(new THREE.Skeleton(boneList));
    meshes.push(m);
    return m;
  };

  // Facteur de silhouette (morphologie) + facteur des mesures client.
  const silhouette = (y) => lerpPts([
    [0.75, P.hip], [0.9, P.hip], [1.065, P.waist], [1.2, P.chest], [1.27, P.chest], [1.36, P.shoulder], [1.42, P.shoulder], [1.47, P.neck],
  ], y);
  const client = (y) => lerpPts([
    [0.72, k.hip], [TAPE_Y.hip, k.hip], [TAPE_Y.waist, k.waist], [TAPE_Y.bust, k.bust], [1.4, 1 + (k.bust - 1) * 0.35], [1.5, 1],
  ], y);
  const radial = (y) => silhouette(y) * client(y);

  // ---------- Squelette ----------
  const root = new THREE.Group();
  root.name = 'Root';
  const shX = 0.156 * P.shoulder;
  const hipX = 0.088 * (0.5 + 0.5 * P.hip * k.hip);
  const hips = bone('Hips', root, 0, 0.95 + EXTRA, 0);
  const spine = bone('Spine', hips, 0, 0.09, 0);
  const neck = bone('Neck', spine, 0, 0.42, 0);
  const head = bone('Head', neck, 0, 0.1, 0.006);
  for (const side of ['Left', 'Right']) {
    const sx = side === 'Left' ? 1 : -1;
    const arm = bone(`${side}Arm`, spine, sx * shX, 0.336, -0.006);
    const fore = bone(`${side}ForeArm`, arm, 0, -0.29, 0);
    bone(`${side}Hand`, fore, 0, -0.25, 0);
    const up = bone(`${side}UpLeg`, hips, sx * hipX, -0.05, 0);
    const leg = bone(`${side}Leg`, up, 0, -THIGH, 0);
    bone(`${side}Foot`, leg, 0, -CALF, 0);
  }

  // ---------- Buste et bassin d'un seul tenant (skinné sur Hips/Spine) ----------
  const g = P.glute, cz = P.chestZ;
  const bodyRings = [
    { y: 0.77, rx: 0.03, zf: 0.022, zb: 0.028 },
    { y: 0.79, rx: 0.115, zf: 0.06, zb: 0.08 * g },
    { y: 0.83, rx: 0.165, zf: 0.09, zb: 0.114 * g },
    { y: 0.885, rx: 0.177, zf: 0.1, zb: 0.132 * g },
    { y: 0.94, rx: 0.171, zf: 0.097, zb: 0.12 * g },
    { y: 1.0, rx: 0.151, zf: 0.092, zb: 0.1 },
    { y: 1.065, rx: 0.128, zf: 0.088, zb: 0.087 },
    { y: 1.14, rx: 0.14, zf: 0.094 * cz, zb: 0.09 },
    { y: 1.19, rx: 0.148, zf: 0.1 * cz, zb: 0.095 },
    { y: 1.25, rx: 0.158, zf: 0.112 * cz, zb: 0.1, b: P.bustBump },
    { y: 1.31, rx: 0.164, zf: 0.104 * cz, zb: 0.099, b: P.bustBump * 0.35 },
    { y: 1.36, rx: 0.168, zf: 0.087, zb: 0.09 },
    { y: 1.40, rx: 0.158, zf: 0.069, zb: 0.075 },
    { y: 1.43, rx: 0.122, zf: 0.058, zb: 0.063 },
    { y: 1.455, rx: 0.075, zf: 0.05, zb: 0.054 },
    { y: 1.475, rx: 0.05, zf: 0.043, zb: 0.048 },
    { y: 1.49, rx: 0.03, zf: 0.03, zb: 0.03 },
  ];
  const torsoGeo = loftGeometry(bodyRings, { scale: radial, yOffset: 0, seg: 72, sub: 5 });
  skin(torsoGeo, 0.98, 1.12);
  torsoGeo.translate(0, EXTRA, 0);
  const torso = skinned(torsoGeo, [hips, spine], 'torso');

  // ---------- Cou long et tête ovale ----------
  const n = P.neck;
  mesh(loftGeometry([
    { y: -0.06, rx: 0.056 * n, zf: 0.047 * n, zb: 0.052 * n },
    { y: 0, rx: 0.047 * n, zf: 0.045 * n, zb: 0.046 * n },
    { y: 0.07, rx: 0.042 * n, zf: 0.042 * n, zb: 0.042 * n, cz: 0.004 },
    { y: 0.13, rx: 0.04 * n, zf: 0.041 * n, zb: 0.041 * n, cz: 0.012 },
    { y: 0.16, rx: 0.02, zf: 0.02, zb: 0.02, cz: 0.012 },
  ]), neck, 'neck');
  const headGeo = loftGeometry([
    { y: -0.035, rx: 0.012, zf: 0.012, zb: 0.012, cz: 0.03 },
    { y: -0.02, rx: 0.034, zf: 0.033, zb: 0.03, cz: 0.03 },
    { y: 0.012, rx: 0.056, zf: 0.06, zb: 0.058, cz: 0.014 },
    { y: 0.06, rx: 0.069, zf: 0.083, zb: 0.08, cz: 0.005 },
    { y: 0.11, rx: 0.074, zf: 0.088, zb: 0.095, cz: 0 },
    { y: 0.16, rx: 0.07, zf: 0.079, zb: 0.09, cz: -0.006 },
    { y: 0.2, rx: 0.054, zf: 0.057, zb: 0.068, cz: -0.009 },
    { y: 0.226, rx: 0.025, zf: 0.025, zb: 0.03, cz: -0.009 },
    { y: 0.234, rx: 0.004, zf: 0.004, zb: 0.004, cz: -0.009 },
  ], { seg: 56 });
  headGeo.scale(P.head, P.head, P.head);
  const headMesh = mesh(headGeo, head, 'head');
  headMesh.rotation.x = 0.1;

  // ---------- Bras (articulations visibles) ----------
  const armRings = [
    { y: 0.026, rx: 0.018 * L },
    { y: 0.01, rx: 0.04 * L, zf: 0.041 * L, zb: 0.042 * L },
    { y: -0.03, rx: 0.046 * L, zf: 0.044 * L, zb: 0.046 * L },
    { y: -0.09, rx: 0.042 * L, zf: 0.041 * L, zb: 0.043 * L },
    { y: -0.19, rx: 0.036 * L, zf: 0.037 * L, zb: 0.039 * L },
    { y: -0.272, rx: 0.029 * L, zf: 0.03 * L, zb: 0.031 * L },
    { y: -0.29, rx: 0.016 * L },
    { y: -0.296, rx: 0.003 },
  ];
  const foreRings = [
    { y: -0.004, rx: 0.003 },
    { y: -0.012, rx: 0.022 * L },
    { y: -0.03, rx: 0.031 * L, zf: 0.03 * L, zb: 0.032 * L },
    { y: -0.08, rx: 0.033 * L, zf: 0.03 * L, zb: 0.032 * L },
    { y: -0.17, rx: 0.026 * L, zf: 0.022 * L, zb: 0.023 * L },
    { y: -0.232, rx: 0.022 * L, zf: 0.016 * L, zb: 0.017 * L },
    { y: -0.244, rx: 0.012 * L, zf: 0.01, zb: 0.01 },
    { y: -0.248, rx: 0.002 },
  ];
  // Main fine, doigts joints : paume tournée vers le corps (axe mince = x).
  const handRings = [
    { y: -0.006, rx: 0.006 * L, zf: 0.012 * L, zb: 0.012 * L },
    { y: -0.016, rx: 0.013 * L, zf: 0.021 * L, zb: 0.021 * L },
    { y: -0.06, rx: 0.015 * L, zf: 0.034 * L, zb: 0.032 * L },
    { y: -0.1, rx: 0.012 * L, zf: 0.033 * L, zb: 0.031 * L },
    { y: -0.15, rx: 0.009 * L, zf: 0.025 * L, zb: 0.024 * L },
    { y: -0.18, rx: 0.005 * L, zf: 0.011 * L, zb: 0.011 * L },
    { y: -0.186, rx: 0.002 },
  ];
  const thumbRings = [
    { y: 0, rx: 0.009 * L },
    { y: -0.03, rx: 0.009 * L },
    { y: -0.056, rx: 0.0075 * L },
    { y: -0.064, rx: 0.002 },
  ];
  const geoArm = loftGeometry(armRings, { seg: 40 });
  const geoFore = loftGeometry(foreRings, { seg: 36 });
  const geoHand = loftGeometry(handRings, { seg: 36 });
  const geoThumb = loftGeometry(thumbRings, { seg: 20, sub: 3 });

  // ---------- Jambes lisses : cuisse + mollet d'un seul tenant ----------
  const lg = P.leg;
  const kThigh = (P.hip * k.hip + 1) / 2;
  const legRings = [
    { y: 0.075, rx: 0.05 },
    { y: 0.035, rx: 0.088, zf: 0.087, zb: 0.091 },
    { y: -0.05, rx: 0.087, zf: 0.087, zb: 0.09 },
    { y: -0.16, rx: 0.075, zf: 0.075, zb: 0.077 },
    { y: -0.29, rx: 0.06, zf: 0.06, zb: 0.06 },
    { y: -0.39, rx: 0.049, zf: 0.05, zb: 0.047 },
    { y: -THIGH, rx: 0.045, zf: 0.047, zb: 0.044 },
    { y: -0.48, rx: 0.045, zf: 0.044, zb: 0.048 },
    { y: -0.56, rx: 0.046, zf: 0.042, zb: 0.056 },
    { y: -0.64, rx: 0.04, zf: 0.037, zb: 0.046 },
    { y: -0.75, rx: 0.029, zf: 0.029, zb: 0.031 },
    { y: -0.83, rx: 0.023, zf: 0.025, zb: 0.025 },
    { y: -0.86, rx: 0.018 },
    { y: -0.872, rx: 0.003 },
  ].map((r) => ({ ...r, rx: r.rx * lg, zf: (r.zf ?? r.rx) * lg, zb: (r.zb ?? r.zf ?? r.rx) * lg }));
  const legScale = (y) => (y > -0.3 ? 1 + (kThigh - 1) * THREE.MathUtils.smoothstep(y, -0.3, -0.05) : 1);

  // Pied fin, construit le long de y puis basculé vers l'avant (+z).
  const footRings = [
    { y: -0.066, rx: 0.011, zf: 0.014, zb: 0.011, cz: 0.05 },
    { y: -0.055, rx: 0.025, zf: 0.03, zb: 0.028, cz: 0.049 },
    { y: -0.02, rx: 0.029, zf: 0.035, zb: 0.04, cz: 0.044 },
    { y: 0.04, rx: 0.034, zf: 0.029, zb: 0.029, cz: 0.05 },
    { y: 0.11, rx: 0.039, zf: 0.018, zb: 0.017, cz: 0.061 },
    { y: 0.165, rx: 0.035, zf: 0.013, zb: 0.011, cz: 0.066 },
    { y: 0.192, rx: 0.019, zf: 0.009, zb: 0.008, cz: 0.068 },
    { y: 0.199, rx: 0.004, zf: 0.003, zb: 0.003, cz: 0.068 },
  ];
  const geoFoot = loftGeometry(footRings, { seg: 40 });
  geoFoot.rotateX(Math.PI / 2);

  const feet = [];
  for (const side of ['Left', 'Right']) {
    const sx = side === 'Left' ? 1 : -1;
    const arm = bones[`${side}Arm`], fore = bones[`${side}ForeArm`], hand = bones[`${side}Hand`];
    joint(0.04 * L, arm);
    mesh(geoArm, arm, 'arm');
    joint(0.026 * L, fore);
    mesh(geoFore, fore, 'forearm');
    joint(0.017 * L, hand);
    const handMesh = mesh(geoHand, hand, 'hand');
    handMesh.scale.x = sx; // la main droite est le miroir de la gauche
    const thumb = mesh(geoThumb, hand, 'thumb');
    thumb.position.set(-0.007 * sx * L, -0.034 * L, 0.021 * L);
    thumb.rotation.set(-0.5, 0, 0.22 * sx);

    const up = bones[`${side}UpLeg`], leg = bones[`${side}Leg`], foot = bones[`${side}Foot`];
    const geoLeg = loftGeometry(legRings, { seg: 48, scale: legScale });
    skin(geoLeg, -THIGH - 0.035, -THIGH + 0.035);
    // Le poids 0 doit aller à la cuisse : smoothstep monte vers le haut, on inverse.
    const w = geoLeg.attributes.skinWeight;
    for (let i = 0; i < w.count; i++) w.setXY(i, w.getY(i), w.getX(i));
    const upPos = new THREE.Vector3();
    root.updateMatrixWorld(true);
    up.getWorldPosition(upPos);
    geoLeg.translate(upPos.x, upPos.y, upPos.z);
    skinned(geoLeg, [up, leg], 'leg');
    mesh(new THREE.SphereGeometry(0.021 * lg, 24, 16), foot, 'ankle');
    feet.push(mesh(geoFoot, foot, 'foot'));
  }

  // Légère convergence des jambes vers les genoux (posture naturelle).
  const rest = {};
  for (const name of Object.keys(bones)) rest[name] = new THREE.Quaternion();
  rest.LeftUpLeg.setFromEuler(new THREE.Euler(0, 0, -0.025));
  rest.RightUpLeg.setFromEuler(new THREE.Euler(0, 0, 0.025));
  rest.LeftLeg.setFromEuler(new THREE.Euler(0, 0, 0.025));
  rest.RightLeg.setFromEuler(new THREE.Euler(0, 0, -0.025));
  for (const name of Object.keys(bones)) bones[name].quaternion.copy(rest[name]);

  // Mesures (sections avant allongement ; la position est relative à l'os porteur).
  const tapes = {
    bust: { ...tapeAt(torsoGeo, TAPE_Y.bust), bone: spine, yOffset: 1.04 },
    waist: { ...tapeAt(torsoGeo, TAPE_Y.waist), bone: spine, yOffset: 1.04 },
    hip: { ...tapeAt(torsoGeo, TAPE_Y.hip), bone: hips, yOffset: 0.95 },
  };

  /** Demi-largeur du bassin à une hauteur donnée (pour poser les mains). */
  const halfWidthAt = (y) => {
    const r = ringAt(torsoGeo, y);
    return r ? r.rx : 0.15;
  };

  return { root, bones, rest, meshes, feet, pelvis: torso, torso, tapes, halfWidthAt, material, yShift: EXTRA };
}
