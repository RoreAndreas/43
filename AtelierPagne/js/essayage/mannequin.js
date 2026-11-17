// Mannequin procédural en « silicone » gris clair.
// Le squelette reprend les noms d'os standards (Hips, Spine, LeftArm…) : la
// bibliothèque de poses restera valable le jour où l'on chargera un mannequin
// GLB modélisé et rigué avec ces mêmes noms, et les vêtements 3D s'y
// accrocheront de la même façon.
import * as THREE from 'three';
import { loftGeometry, tapeAt, ringAt } from './geometry.js';

export const PRESETS = {
  femme: {
    label: 'Femme', chest: 1, shoulder: 1, chestZ: 1, bustBump: 0.026, waist: 1, hip: 1, glute: 1,
    limb: 1, neck: 1, scale: 1,
  },
  homme: {
    label: 'Homme', chest: 1.09, shoulder: 1.17, chestZ: 0.96, bustBump: 0, waist: 1.15, hip: 0.92, glute: 0.84,
    limb: 1.14, neck: 1.2, scale: 1.06,
  },
};

// Hauteurs (repère du mannequin de base, en mètres) où l'on pose le mètre ruban.
export const TAPE_Y = { bust: 1.25, waist: 1.065, hip: 0.885 };

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
    color: 0xbfc1c5,
    roughness: 0.48,
    metalness: 0,
    clearcoat: 0.35,
    clearcoatRoughness: 0.45,
    sheen: 0.35,
    sheenRoughness: 0.6,
    sheenColor: new THREE.Color(0xf2f2f2),
    transparent: false,
  });
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
  const mesh = (geo, parent, tag) => {
    const m = new THREE.Mesh(geo, material);
    m.castShadow = true;
    m.receiveShadow = true;
    m.userData.tag = tag;
    parent.add(m);
    meshes.push(m);
    return m;
  };
  const sphere = (r, parent, x = 0, y = 0, z = 0) => {
    const m = mesh(new THREE.SphereGeometry(r, 32, 20), parent, 'joint');
    m.position.set(x, y, z);
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
  const shX = 0.158 * P.shoulder;
  const hipX = 0.09 * (0.5 + 0.5 * P.hip * k.hip);
  const hips = bone('Hips', root, 0, 0.95, 0);
  const spine = bone('Spine', hips, 0, 0.09, 0); // 1.04
  const neck = bone('Neck', spine, 0, 0.42, 0); // 1.46
  const head = bone('Head', neck, 0, 0.075, 0.004); // 1.535
  for (const side of ['Left', 'Right']) {
    const sx = side === 'Left' ? 1 : -1;
    const arm = bone(`${side}Arm`, spine, sx * shX, 0.338, -0.006);
    const fore = bone(`${side}ForeArm`, arm, 0, -0.29, 0);
    bone(`${side}Hand`, fore, 0, -0.245, 0);
    const up = bone(`${side}UpLeg`, hips, sx * hipX, -0.05, 0);
    const leg = bone(`${side}Leg`, up, 0, -0.41, 0);
    bone(`${side}Foot`, leg, 0, -0.41, 0);
  }

  // ---------- Bassin ----------
  const g = P.glute;
  const pelvisRings = [
    { y: 0.784, rx: 0.03, zf: 0.022, zb: 0.028 },
    { y: 0.8, rx: 0.085, zf: 0.055, zb: 0.075 * g },
    { y: 0.83, rx: 0.156, zf: 0.088, zb: 0.112 * g },
    { y: 0.885, rx: 0.177, zf: 0.1, zb: 0.132 * g },
    { y: 0.94, rx: 0.171, zf: 0.097, zb: 0.12 * g },
    { y: 1.0, rx: 0.151, zf: 0.092, zb: 0.1 },
    { y: 1.065, rx: 0.127, zf: 0.087, zb: 0.086 },
    { y: 1.11, rx: 0.122, zf: 0.083, zb: 0.082 },
    { y: 1.128, rx: 0.06, zf: 0.04, zb: 0.04 },
  ];

  // ---------- Buste ----------
  const cz = P.chestZ;
  const torsoRings = [
    { y: 0.96, rx: 0.06, zf: 0.04, zb: 0.04 },
    { y: 0.975, rx: 0.12, zf: 0.083, zb: 0.085 },
    { y: 1.065, rx: 0.128, zf: 0.088, zb: 0.087 },
    { y: 1.14, rx: 0.14, zf: 0.094 * cz, zb: 0.09 },
    { y: 1.19, rx: 0.148, zf: 0.1 * cz, zb: 0.095 },
    { y: 1.25, rx: 0.158, zf: 0.112 * cz, zb: 0.1, b: P.bustBump },
    { y: 1.31, rx: 0.164, zf: 0.104 * cz, zb: 0.099, b: P.bustBump * 0.35 },
    { y: 1.36, rx: 0.17, zf: 0.087, zb: 0.09 },
    { y: 1.40, rx: 0.162, zf: 0.069, zb: 0.075 },
    { y: 1.43, rx: 0.127, zf: 0.058, zb: 0.063 },
    { y: 1.455, rx: 0.08, zf: 0.05, zb: 0.054 },
    { y: 1.475, rx: 0.055, zf: 0.045, zb: 0.05 },
    { y: 1.49, rx: 0.03, zf: 0.03, zb: 0.03 },
  ];
  // Bassin + buste d'un seul tenant, « skinné » sur Hips et Spine : pas de
  // jointure visible à la taille, la flexion du dos se répartit en douceur.
  const bodyRings = [...pelvisRings.filter((r) => r.y <= 1.0), ...torsoRings.filter((r) => r.y >= 1.065)];
  const torsoGeo = loftGeometry(bodyRings, { scale: radial, yOffset: 0, seg: 72, sub: 5 });
  const pelvisGeo = torsoGeo;
  {
    const pos = torsoGeo.attributes.position;
    const idx = new Uint16Array(pos.count * 4), w = new Float32Array(pos.count * 4);
    for (let i = 0; i < pos.count; i++) {
      const t = THREE.MathUtils.smoothstep(pos.getY(i), 0.98, 1.12);
      idx.set([0, 1, 0, 0], i * 4);
      w.set([1 - t, t, 0, 0], i * 4);
    }
    torsoGeo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4));
    torsoGeo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(w, 4));
  }
  root.updateMatrixWorld(true);
  const torso = new THREE.SkinnedMesh(torsoGeo, material);
  torso.castShadow = torso.receiveShadow = true;
  torso.frustumCulled = false;
  torso.userData.tag = 'torso';
  root.add(torso);
  root.updateMatrixWorld(true);
  torso.bind(new THREE.Skeleton([hips, spine]));
  meshes.push(torso);
  const pelvis = torso;

  // ---------- Cou et tête (tête « œuf » sans visage, comme en vitrine) ----------
  const n = P.neck;
  mesh(loftGeometry([
    { y: -0.06, rx: 0.06 * n, zf: 0.05 * n, zb: 0.055 * n },
    { y: 0, rx: 0.052 * n, zf: 0.05 * n, zb: 0.05 * n },
    { y: 0.06, rx: 0.047 * n, zf: 0.047 * n, zb: 0.047 * n, cz: 0.005 },
    { y: 0.11, rx: 0.044 * n, zf: 0.045 * n, zb: 0.045 * n, cz: 0.012 },
    { y: 0.135, rx: 0.02, zf: 0.02, zb: 0.02, cz: 0.012 },
  ]), neck, 'neck');
  const hs = P === PRESETS.homme ? 1.05 : 1;
  const headGeo = loftGeometry([
    { y: -0.035, rx: 0.012, zf: 0.012, zb: 0.012, cz: 0.032 },
    { y: -0.02, rx: 0.036, zf: 0.034, zb: 0.03, cz: 0.032 },
    { y: 0.012, rx: 0.058 * hs, zf: 0.06, zb: 0.06, cz: 0.016 },
    { y: 0.06, rx: 0.071 * hs, zf: 0.085, zb: 0.08, cz: 0.006 },
    { y: 0.11, rx: 0.076 * hs, zf: 0.09, zb: 0.096, cz: 0 },
    { y: 0.16, rx: 0.072 * hs, zf: 0.081, zb: 0.091, cz: -0.006 },
    { y: 0.2, rx: 0.056 * hs, zf: 0.059, zb: 0.069, cz: -0.009 },
    { y: 0.226, rx: 0.026, zf: 0.026, zb: 0.031, cz: -0.009 },
    { y: 0.234, rx: 0.004, zf: 0.004, zb: 0.004, cz: -0.009 },
  ], { seg: 56 });
  const headMesh = mesh(headGeo, head, 'head');
  headMesh.rotation.x = 0.08;

  // ---------- Membres ----------
  const armRings = [
    { y: 0.03, rx: 0.02 * L },
    { y: 0.012, rx: 0.042 * L, zf: 0.043 * L, zb: 0.044 * L },
    { y: -0.02, rx: 0.049 * L, zf: 0.047 * L, zb: 0.048 * L },
    { y: -0.07, rx: 0.045 * L, zf: 0.044 * L, zb: 0.046 * L },
    { y: -0.18, rx: 0.038 * L, zf: 0.039 * L, zb: 0.041 * L },
    { y: -0.29, rx: 0.031 * L, zf: 0.032 * L, zb: 0.033 * L },
    { y: -0.315, rx: 0.016 * L },
    { y: -0.322, rx: 0.003 },
  ];
  const foreRings = [
    { y: 0.022, rx: 0.02 * L },
    { y: 0.0, rx: 0.032 * L, zf: 0.031 * L, zb: 0.033 * L },
    { y: -0.06, rx: 0.036 * L, zf: 0.033 * L, zb: 0.035 * L },
    { y: -0.16, rx: 0.028 * L, zf: 0.024 * L, zb: 0.025 * L },
    { y: -0.24, rx: 0.024 * L, zf: 0.017 * L, zb: 0.018 * L },
    { y: -0.262, rx: 0.012 * L, zf: 0.01, zb: 0.01 },
    { y: -0.268, rx: 0.002 },
  ];
  // Main en « moufle » : paume tournée vers le corps (axe mince = x).
  const handRings = [
    { y: 0.012, rx: 0.01 * L, zf: 0.016 * L, zb: 0.016 * L },
    { y: 0, rx: 0.015 * L, zf: 0.024 * L, zb: 0.024 * L },
    { y: -0.05, rx: 0.016 * L, zf: 0.037 * L, zb: 0.035 * L },
    { y: -0.095, rx: 0.013 * L, zf: 0.037 * L, zb: 0.035 * L },
    { y: -0.14, rx: 0.01 * L, zf: 0.028 * L, zb: 0.027 * L },
    { y: -0.168, rx: 0.006 * L, zf: 0.013 * L, zb: 0.013 * L },
    { y: -0.175, rx: 0.002 },
  ];
  const thumbRings = [
    { y: 0, rx: 0.011 * L },
    { y: -0.03, rx: 0.011 * L },
    { y: -0.055, rx: 0.009 * L },
    { y: -0.064, rx: 0.002 },
  ];
  const thighRings = [
    { y: 0.075, rx: 0.045 },
    { y: 0.035, rx: 0.084, zf: 0.087, zb: 0.091 },
    { y: -0.05, rx: 0.088, zf: 0.09, zb: 0.093 },
    { y: -0.15, rx: 0.08, zf: 0.08, zb: 0.082 },
    { y: -0.27, rx: 0.066, zf: 0.066, zb: 0.066 },
    { y: -0.37, rx: 0.054, zf: 0.056, zb: 0.052 },
    { y: -0.42, rx: 0.05, zf: 0.052, zb: 0.048 },
    { y: -0.455, rx: 0.03, zf: 0.03, zb: 0.03 },
    { y: -0.468, rx: 0.004 },
  ];
  const kThigh = (P.hip * k.hip + 1) / 2;
  const calfRings = [
    { y: 0.04, rx: 0.03 },
    { y: 0.02, rx: 0.048, zf: 0.05, zb: 0.05 },
    { y: -0.04, rx: 0.05, zf: 0.048, zb: 0.056 },
    { y: -0.11, rx: 0.052, zf: 0.048, zb: 0.064 },
    { y: -0.19, rx: 0.045, zf: 0.042, zb: 0.052 },
    { y: -0.3, rx: 0.032, zf: 0.032, zb: 0.034 },
    { y: -0.39, rx: 0.028, zf: 0.03, zb: 0.03 },
    { y: -0.425, rx: 0.02 },
    { y: -0.435, rx: 0.004 },
  ];
  // Pied : construit le long de y puis basculé vers l'avant (+z).
  const footRings = [
    { y: -0.07, rx: 0.012, zf: 0.015, zb: 0.012, cz: 0.05 },
    { y: -0.058, rx: 0.028, zf: 0.031, zb: 0.03, cz: 0.049 },
    { y: -0.02, rx: 0.033, zf: 0.036, zb: 0.045, cz: 0.044 },
    { y: 0.04, rx: 0.039, zf: 0.03, zb: 0.032, cz: 0.05 },
    { y: 0.11, rx: 0.045, zf: 0.019, zb: 0.019, cz: 0.061 },
    { y: 0.165, rx: 0.041, zf: 0.014, zb: 0.012, cz: 0.066 },
    { y: 0.19, rx: 0.022, zf: 0.009, zb: 0.008, cz: 0.068 },
    { y: 0.196, rx: 0.004, zf: 0.003, zb: 0.003, cz: 0.068 },
  ];

  const geoArm = loftGeometry(armRings, { seg: 40 });
  const geoFore = loftGeometry(foreRings, { seg: 36 });
  const geoHand = loftGeometry(handRings, { seg: 36 });
  const geoThumb = loftGeometry(thumbRings, { seg: 20, sub: 3 });
  const geoThigh = loftGeometry(thighRings, { seg: 48, scale: () => kThigh });
  const geoCalf = loftGeometry(calfRings, { seg: 40 });
  const geoFoot = loftGeometry(footRings, { seg: 40 });
  geoFoot.rotateX(Math.PI / 2);
  geoFoot.computeBoundingBox();

  const feet = [];
  for (const side of ['Left', 'Right']) {
    const sx = side === 'Left' ? 1 : -1;
    const arm = bones[`${side}Arm`], fore = bones[`${side}ForeArm`], hand = bones[`${side}Hand`];
    sphere(0.044 * L, arm);
    mesh(geoArm, arm, 'arm');
    sphere(0.031 * L, fore);
    mesh(geoFore, fore, 'forearm');
    const handMesh = mesh(geoHand, hand, 'hand');
    handMesh.scale.x = sx; // la main droite est le miroir de la gauche
    const thumb = mesh(geoThumb, hand, 'thumb');
    thumb.position.set(-0.008 * sx * L, -0.03 * L, 0.024 * L);
    thumb.rotation.set(-0.55, 0, 0.25 * sx);
    const up = bones[`${side}UpLeg`], leg = bones[`${side}Leg`], foot = bones[`${side}Foot`];
    mesh(geoThigh, up, 'thigh');
    sphere(0.047, leg);
    mesh(geoCalf, leg, 'calf');
    sphere(0.028, foot);
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

  // Mesures (repère du mannequin non mis à l'échelle).
  const tapes = {
    bust: { ...tapeAt(torsoGeo, TAPE_Y.bust), bone: spine, yOffset: 1.04 },
    waist: { ...tapeAt(torsoGeo, TAPE_Y.waist), bone: spine, yOffset: 1.04 },
    hip: { ...tapeAt(pelvisGeo, TAPE_Y.hip), bone: hips, yOffset: 0.95 },
  };

  /** Demi-largeur du bassin à une hauteur donnée (pour poser les mains). */
  const halfWidthAt = (y) => {
    const r = ringAt(pelvisGeo, y) || ringAt(torsoGeo, y);
    return r ? r.rx : 0.15;
  };

  return { root, bones, rest, meshes, feet, pelvis, torso, tapes, halfWidthAt, material };
}
