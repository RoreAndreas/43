// Cycle de marche procédural (mannequin sans animation de marche : l'homme).
// Principes classiques du cycle de marche :
//  - 4 poses par pas : contact (talon), amorti (genou fléchi, bassin au plus
//    bas), passage (jambe libre sous le corps), élévation (poussée, bassin au
//    plus haut) ; un cycle = 2 pas ;
//  - bassin : rotation vers la jambe qui avance, bascule du côté de la jambe
//    libre, léger balancement sur la jambe d'appui ;
//  - buste en contre-rotation, bras opposés aux jambes avec un léger retard
//    (l'avant-bras suit le bras) ; tête stabilisée (elle regarde devant) ;
//  - pied : attaque du talon, pied à plat, déroulé jusqu'à la pointe.
// Angles relatifs à la position de repos, mêmes conventions que poses.js.
import * as THREE from 'three';

const TAU = Math.PI * 2;
const ss = THREE.MathUtils.smoothstep;

// Courbe périodique définie par des clés (phase 0..1 → valeur), interpolation
// Catmull-Rom (mouvement continu, sans arrêt sur les poses clés).
function curve(keys) {
  const n = keys.length;
  return (p) => {
    p -= Math.floor(p);
    let i = n - 1;
    for (let k = 0; k < n; k++) if (keys[k][0] <= p) i = k;
    const at = (k) => keys[((k % n) + n) % n];
    const [p1, v1] = at(i), [p2r, v2] = at(i + 1);
    const p2 = p2r <= p1 ? p2r + 1 : p2r;
    const q = p < p1 ? p + 1 : p;
    const t = (q - p1) / (p2 - p1);
    const v0 = at(i - 1)[1], v3 = at(i + 2)[1];
    return 0.5 * (2 * v1 + (-v0 + v2) * t + (2 * v0 - 5 * v1 + 4 * v2 - v3) * t * t + (-v0 + 3 * v1 - 3 * v2 + v3) * t * t * t);
  };
}

// Poses clés de la vidéo « Walk Cycle » (P2Design) : contact (image 1), amorti (4),
// passage (7), élévation/poussée (10), puis les mêmes en miroir (13, 16, 19, 22) ;
// cycle de 24 images = 1 s. Phase de la jambe : 0 = contact devant (talon),
// 0,5 = contact derrière (sur la pointe).
const K = (vals) => vals.map((v, i) => [i / 8, v]);
//                 contact amorti passage élévation | contact amorti passage élévation (jambe arrière puis libre)
const THIGH = curve(K([-0.48, -0.3, -0.05, 0.2, 0.38, 0.45, -0.15, -0.45]));
const KNEE = curve(K([0.05, 0.3, 0.1, 0.02, 0.25, 0.7, 1.05, 0.35]));
// inclinaison du pied dans le monde (> 0 : pointe vers le bas) : talon, à plat, talon qui se lève, sur la pointe
const FOOT = curve(K([-0.35, 0, 0, 0.2, 0.6, 1.0, 0.35, -0.1]));
// bras : écartés au contact, alignés au passage, plus loin à l'élévation (phase de la jambe opposée)
const ARM = curve(K([0.42, 0.3, 0.02, -0.25, -0.42, -0.3, -0.02, 0.25]));
const ELBOW = curve(K([0.12, 0.14, 0.25, 0.4, 0.55, 0.45, 0.3, 0.18]));

const STYLES = {
  // allure masculine : grand pas, bras amples, bassin stable
  homme: { arm: 0.34, armOut: 0.13, fore: 0.32, hipYaw: 0.08, hipTilt: 0.035, sway: 0.012, chest: 0.12, lean: 0.04, cross: 0 },
  // allure féminine : pas croisés, bassin plus mobile, bras près du corps
  femme: { arm: 0.24, armOut: 0.09, fore: 0.28, hipYaw: 0.12, hipTilt: 0.07, sway: 0.02, chest: 0.1, lean: 0.02, cross: 0.05 },
};

/** Animation de marche (format de rig.clipFrames : rotations locales et bassin, 30 i/s). */
export function proceduralWalk(body, style = body.sex) {
  const S = STYLES[style] || STYLES.homme;
  const N = 30, fps = 30; // cycle d'1 s, comme la vidéo (24 images à 24 i/s)
  const q = (x, y, z) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z));
  const frames = [];
  for (let i = 0; i < N; i++) {
    const p = i / N;
    const rot = {};
    for (const [side, ph, sx] of [['Left', p, 1], ['Right', p + 0.5, -1]]) {
      const th = THIGH(ph), kn = KNEE(ph);
      // pas croisé : la jambe qui avance vient vers l'axe du corps
      const swing = ss((ph - Math.floor(ph)), 0.6, 1);
      rot[`${side}UpLeg`] = [th, 0, -sx * S.cross * swing];
      rot[`${side}Leg`] = [kn, 0, 0];
      rot[`${side}Foot`] = [FOOT(ph) - (th + kn), 0, 0];
      // bras opposé à la jambe : en arrière quand la jambe du même côté est devant
      rot[`${side}Arm`] = [S.arm / 0.42 * ARM(ph - 0.04), 0, sx * S.armOut];
      rot[`${side}ForeArm`] = [-S.fore / 0.3 * ELBOW(ph - 0.06), 0, 0];
      rot[`${side}Hand`] = [0, 0, -sx * 0.06];
    }
    const c = Math.cos(TAU * p), s = Math.sin(TAU * p);
    rot.Hips = [0, -S.hipYaw * c, -S.hipTilt * s];
    rot.Spine = [S.lean, S.chest * c + S.hipYaw * c, S.hipTilt * s * 0.7];
    rot.Neck = [-S.lean * 0.4, -S.chest * c * 0.45, 0];
    rot.Head = [-S.lean * 0.3, -S.chest * c * 0.4, 0];
    const L = {};
    for (const n of Object.keys(body.bones)) {
      const r = rot[n];
      L[n] = body.rest[n].clone();
      if (r) L[n].multiply(q(r[0], r[1], r[2]));
    }
    // bassin : balancement latéral vers la jambe d'appui (la hauteur est donnée par les pieds)
    frames.push({ L, h: new THREE.Vector3(S.sway * s, 0, 0) });
  }
  return { fps, frames, speed: 1.2 };
}
