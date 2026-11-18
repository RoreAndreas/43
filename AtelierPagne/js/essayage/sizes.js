// Tailles proposées (tours en cm, guide des tailles françaises courant).
// Les robes sont pré-calculées pour chacune de ces tailles et pour chaque pose
// (voir tools/bake/). La hauteur reste libre : le mannequin et la robe sont
// mis à l'échelle ensemble.
export const SIZES = {
  femme: [
    { id: '36', bust: 84, waist: 66, hip: 92 },
    { id: '38', bust: 88, waist: 70, hip: 96 },
    { id: '40', bust: 92, waist: 74, hip: 100 },
    { id: '42', bust: 96, waist: 78, hip: 104 },
    { id: '44', bust: 100, waist: 82, hip: 108 },
    { id: '46', bust: 106, waist: 88, hip: 114 },
  ],
  homme: [
    { id: '44', bust: 88, waist: 76, hip: 90 },
    { id: '46', bust: 92, waist: 80, hip: 94 },
    { id: '48', bust: 96, waist: 84, hip: 98 },
    { id: '50', bust: 100, waist: 88, hip: 102 },
    { id: '52', bust: 104, waist: 92, hip: 106 },
    { id: '54', bust: 108, waist: 96, hip: 110 },
  ],
};

export const DEFAULT_SIZE = { femme: '38', homme: '48' };

/** Mesures du mannequin pour une taille à une hauteur donnée (proportions conservées). */
export function sizeMeasures(preset, sizeId, height, baseHeight) {
  const s = SIZES[preset].find((x) => x.id === sizeId) || SIZES[preset][0];
  const k = height / baseHeight;
  return { height, bust: Math.round(s.bust * k), waist: Math.round(s.waist * k), hip: Math.round(s.hip * k) };
}
