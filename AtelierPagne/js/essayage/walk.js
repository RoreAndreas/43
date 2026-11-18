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

// Courbe périodique définie par des clés (phase 0..1 → valeur), interpolation douce.
function curve(keys) {
  return (p) => {
    p -= Math.floor(p);
    for (let i = 0; i < keys.length; i++) {
      const [p0, v0] = keys[i], [p1r, v1] = keys[(i + 1) % keys.length];
      const p1 = i + 1 < keys.length ? p1r : p1r + 1;
      const q = p < p0 ? p + 1 : p;
      if (q >= p0 && q <= p1) { const u = (q - p0) / (p1 - p0); return v0 + (v1 - v0) * (u * u * (3 - 2 * u)); }
    }
    return keys[0][1];
  };
}

// Jambe, phase 0 = contact du talon ; appui 0 → 0,6 ; jambe libre 0,6 → 1.
const THIGH = curve([[0, -0.42], [0.12, -0.32], [0.3, -0.05], [0.58, 0.32], [0.72, 0.12], [0.88, -0.38]]);
const KNEE = curve([[0, 0.04], [0.12, 0.26], [0.3, 0.08], [0.5, 0.12], [0.62, 0.55], [0.74, 1.05], [0.9, 0.3]]);
// inclinaison du pied dans le monde (> 0 : pointe vers le bas)
const FOOT = curve([[0, -0.28], [0.1, 0], [0.42, 0], [0.6, 0.6], [0.72, 0.35], [0.9, -0.05]]);

const STYLES = {
  // allure masculine : grand pas, bras amples, bassin stable
  homme: { arm: 0.34, armOut: 0.13, fore: 0.32, hipYaw: 0.08, hipTilt: 0.035, sway: 0.012, chest: 0.12, lean: 0.04, cross: 0 },
  // allure féminine : pas croisés, bassin plus mobile, bras près du corps
  femme: { arm: 0.24, armOut: 0.09, fore: 0.28, hipYaw: 0.12, hipTilt: 0.07, sway: 0.02, chest: 0.1, lean: 0.02, cross: 0.05 },
};

/** Animation de marche (format de rig.clipFrames : rotations locales et bassin, 30 i/s). */
export function proceduralWalk(body, style = body.sex) {
  const S = STYLES[style] || STYLES.homme;
  const N = 36, fps = 30;
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
      // bras opposé à la jambe, avec retard (overlap)
      const a = Math.cos(TAU * (ph - 0.06));
      rot[`${side}Arm`] = [S.arm * a, 0, sx * S.armOut];
      rot[`${side}ForeArm`] = [-(S.fore * 0.5 + S.fore * Math.max(0, -Math.cos(TAU * (ph - 0.14)))), 0, 0];
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
  return { fps, frames, speed: 1.1 };
}
