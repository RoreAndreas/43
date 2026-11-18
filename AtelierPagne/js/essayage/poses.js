// Bibliothèque de poses. Angles en radians, ordre d'Euler XYZ, relatifs à la
// position de repos (debout, bras le long du corps).
//  - bras : z > 0 écarte le bras gauche du corps ; x < 0 l'avance.
//  - coude : x < 0 plie l'avant-bras vers l'avant.
//  - hanche : x < 0 avance la cuisse ; genou : x > 0 plie la jambe.
// `sym: true` recopie le côté gauche sur le côté droit en miroir quand le côté
// droit n'est pas précisé. `ik` place le poignet sur une cible (repère du
// mannequin) : la cible peut dépendre de la morphologie (largeur des hanches).

// Cibles des poignets, calculées sur la morphologie (repère du mannequin au repos).
const handOnHip = (b, side, dz = 0) => {
  const y = (b.lm.waist + b.lm.hip) / 2 + 0.02;
  return [side * (b.halfWidthAt(y) + 0.05), y, b.lm.joints.Hips.z + dz];
};
const handOnThigh = (b, side) => {
  const j = b.lm.joints[side > 0 ? 'LeftUpLeg' : 'RightUpLeg'];
  return [j.x + side * 0.05, j.y + 0.11, j.z + b.lm.thigh * 0.62];
};

/** Bras qui pendent juste à l'extérieur des hanches (et de la jupe) : s'adapte aux courbes. */
const hangOutside = (b, side, fwd = 0.03, out = 0.075) => {
  const J = b.lm.joints, n = side > 0 ? 'Left' : 'Right';
  const S = J[`${n}Arm`];
  const L = (S.distanceTo(J[`${n}ForeArm`]) + J[`${n}ForeArm`].distanceTo(J[`${n}Hand`])) * 0.985;
  let w = 0;
  let g = 0;
  // du bout des doigts (≈ 18 cm sous le poignet) jusqu'au haut de la cuisse
  for (let y = S.y - L - 0.22; y < S.y - L + 0.2; y += 0.02) {
    w = Math.max(w, b.halfWidthAt(y));
    g = Math.max(g, b.garmentHalfWidthAt?.(y) ?? 0); // le corps s'écarte de la tenue
  }
  const x = Math.max(w + out, g ? g + 0.028 : 0, Math.abs(S.x) + 0.02); // la main effleure la robe
  const dx = x - Math.abs(S.x);
  const dy = Math.sqrt(Math.max(0.01, L * L - dx * dx - fwd * fwd));
  return [side * x, S.y - dy, S.z + fwd];
};
// Cible exprimée dans le repère du bassin : si la pose fait pivoter les hanches
// (et donc la jupe), la main reste à l'extérieur de la tenue.
const HANG = (side, fwd, out) => ({ target: (b) => hangOutside(b, side, fwd, out), pole: [side * 0.25, 0, -1], frame: 'Hips' });

export const POSES = [
  {
    id: 'neutre',
    label: 'Debout',
    hint: 'La pose de référence pour juger la coupe.',
    sym: true,
    rot: {
      LeftHand: [0, 0, -0.06],
    },
    ik: { Left: HANG(1, 0.04), Right: HANG(-1, 0.04) },
  },
  {
    id: 'hanchement',
    label: 'Hanchement',
    hint: 'Le poids sur une jambe : le tombé naturel du tissu.',
    rot: {
      Hips: [0, 0.12, 0.07],
      Spine: [0.02, -0.08, -0.1],
      Neck: [0, 0.05, 0.05],
      Head: [0.02, 0.12, 0.03],
      RightUpLeg: [0.02, 0, -0.07],
      RightLeg: [0, 0, 0],
      LeftUpLeg: [-0.18, 0.1, -0.12],
      LeftLeg: [0.32, 0, 0.02],
      LeftFoot: [-0.08, -0.15, 0],
    },
    ik: { Left: HANG(1, 0.09, 0.09), Right: HANG(-1, 0.02, 0.07) },
  },
  {
    id: 'mains-hanches',
    label: 'Mains sur les hanches',
    hint: 'Contrôle l’aisance à la taille et aux emmanchures.',
    sym: true,
    rot: {
      LeftHand: [0.1, -0.35, 0.55],
    },
    ik: {
      Left: { target: (b) => handOnHip(b, 1), pole: [1, 0.1, -0.55] },
      Right: { target: (b) => handOnHip(b, -1), pole: [-1, 0.1, -0.55] },
    },
  },
  {
    id: 'bras-ouverts',
    label: 'Bras ouverts',
    hint: 'Pour juger les manches et la carrure.',
    sym: true,
    rot: {
      LeftArm: [-0.1, 0, 1.15],
      LeftForeArm: [-0.25, 0, 0],
      LeftHand: [0, 0, 0.1],
      LeftUpLeg: [0, 0, 0.05],
      LeftLeg: [0, 0, -0.05],
    },
  },
  {
    id: 'defile',
    label: 'Défilé',
    hint: 'En marche : le mouvement de la jupe ou du pantalon.',
    // animation de marche du modèle (mannequin femme) ; sinon, pas figé ci-dessous
    clip: 'defile',
    rot: {
      Hips: [0, -0.1, 0.03],
      Spine: [0.03, 0.14, -0.03],
      Head: [0.03, -0.04, 0],
      LeftUpLeg: [-0.38, 0, -0.02],
      LeftLeg: [0.12, 0, 0],
      LeftFoot: [0.18, 0, 0],
      RightUpLeg: [0.28, 0, 0.02],
      RightLeg: [0.32, 0, 0],
      RightFoot: [-0.3, 0, 0],
      LeftArm: [0.32, 0.05, 0.22],
      LeftForeArm: [-0.15, 0, 0],
      RightArm: [-0.34, -0.05, -0.22],
      RightForeArm: [-0.5, 0, 0],
    },
  },
  {
    id: 'photo',
    label: 'Pose photo',
    hint: 'Une main à la taille, regard de côté : la pose « vitrine ».',
    rot: {
      Hips: [0, -0.2, -0.06],
      Spine: [0, 0.12, 0.08],
      Neck: [0, 0.1, -0.03],
      Head: [0.04, 0.3, -0.06],
      LeftUpLeg: [0.01, 0, 0.06],
      RightUpLeg: [-0.2, -0.12, 0.13],
      RightLeg: [0.3, 0, -0.03],
      RightFoot: [-0.05, 0.25, 0],
      LeftHand: [0.1, -0.35, 0.55],
      RightHand: [0, 0, 0.05],
    },
    ik: {
      Left: { target: (b) => handOnHip(b, 1, 0.01), pole: [1, 0.1, -0.55] },
      Right: HANG(-1, 0.07, 0.08),
    },
  },
  {
    id: 'assise',
    label: 'Assise',
    hint: 'Vérifie le confort et la longueur une fois assise.',
    stool: true,
    sym: true,
    rot: {
      Spine: [-0.06, 0, 0],
      Head: [0.06, 0, 0],
      LeftUpLeg: [-1.5, 0, 0.1],
      LeftLeg: [1.45, 0, -0.1],
      LeftFoot: [0.06, 0.08, 0],
      LeftHand: [-0.2, 0.6, 0.15],
    },
    ik: {
      Left: { target: (b) => handOnThigh(b, 1), pole: [0.5, -0.3, -1] },
      Right: { target: (b) => handOnThigh(b, -1), pole: [-0.5, -0.3, -1] },
    },
  },
];

export function expandPose(pose) {
  const rot = { ...pose.rot };
  if (pose.sym) {
    for (const [name, [x, y, z]] of Object.entries(pose.rot)) {
      if (!name.startsWith('Left')) continue;
      const r = name.replace('Left', 'Right');
      if (!rot[r]) rot[r] = [x, -y, -z];
    }
  }
  return rot;
}
