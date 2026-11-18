// Tenues : robes modélisées dans Blender (voir tools/convert_garment.py et dress.js),
// habillées du pagne choisi, avec une matière de tissu (reflet, grain de tissage).
import * as THREE from 'three';
import { DressCloth, BakedDress, hasDress } from './dress.js';

export const OUTFITS = {
  femme: [
    { id: 'aucune', label: 'Sans tenue', hint: 'Le mannequin seul, pour juger la silhouette.' },
    {
      id: 'aveline', label: 'Robe longue épaules dénudées', hint: 'Bustier à bandeau, jupe longue fendue.',
      mesh: 'aveline',
    },
    /* Robe à bretelles du tutoriel : coupée sur l'ancien mannequin, à recouper pour le mannequin articulé.
    {
      id: 'bretelles', label: 'Robe fendue à bretelles', hint: 'Robe midi à fines bretelles, fendue sur la cuisse : coupée sur le mannequin.',
      mesh: 'bretelles',
    }, */
  ],
  homme: [
    { id: 'aucune', label: 'Sans tenue', hint: 'Aucune tenue homme pour l’instant : ajoutez-en une modélisée dans Blender.' },
  ],
};

export function fabricUniforms() {
  return { uMap: { value: null }, uScale: { value: 0.3 }, uHasMap: { value: 0 } };
}

// ---------- Grain de tissage (carte de relief générée, raccordable) ----------
let weave = null;
function weaveNormalMap() {
  if (weave) return weave;
  const S = 64;
  const c = document.createElement('canvas');
  c.width = c.height = S;
  const x = c.getContext('2d');
  const img = x.createImageData(S, S);
  // toile : fils de chaîne et de trame qui passent dessus / dessous en alternance
  const h = (u, v) => {
    const cu = Math.floor(u * 8), cv = Math.floor(v * 8);
    const fu = (u * 8) % 1, fv = (v * 8) % 1;
    return (cu + cv) % 2 === 0 ? Math.sin(Math.PI * fv) : Math.sin(Math.PI * fu);
  };
  for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) {
    const u = i / S, v = j / S, e = 1 / S;
    const nx = -(h(u + e, v) - h(u - e, v)) * 2, ny = -(h(u, v + e) - h(u, v - e)) * 2, nz = 1;
    const l = Math.hypot(nx, ny, nz);
    const k = (j * S + i) * 4;
    img.data[k] = (nx / l * 0.5 + 0.5) * 255;
    img.data[k + 1] = (ny / l * 0.5 + 0.5) * 255;
    img.data[k + 2] = (nz / l * 0.5 + 0.5) * 255;
    img.data[k + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  weave = new THREE.CanvasTexture(c);
  weave.wrapS = weave.wrapT = THREE.RepeatWrapping;
  weave.repeat.set(1 / 0.008, 1 / 0.008); // un motif de tissage tous les 8 mm (UV en mètres)
  weave.anisotropy = 4;
  return weave;
}

/** Matière de tissu : pagne plaqué selon le patron (UV en mètres), reflet de fibre, grain. */
export function fabricMaterial(uniforms, { side = THREE.DoubleSide } = {}) {
  const m = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, roughness: 0.82, metalness: 0, side,
    sheen: 0.7, sheenRoughness: 0.45, sheenColor: new THREE.Color(0xffffff),
    normalMap: weaveNormalMap(), normalScale: new THREE.Vector2(0.35, 0.35),
  });
  m.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `#include <common>
        attribute vec2 fabricUv; varying vec2 vFabricUv;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vFabricUv = fabricUv;`);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform sampler2D uMap; uniform float uScale; uniform float uHasMap; varying vec2 vFabricUv;`)
      .replace('#include <map_fragment>', `
        if (uHasMap > 0.5) diffuseColor.rgb *= texture2D(uMap, vFabricUv / uScale).rgb;`);
  };
  m.customProgramCacheKey = () => 'fabric-uv';
  return m;
}

// ---------- Assemblage d'une tenue ----------
export function buildOutfit(body, outfit, uniforms, scene) {
  if (!outfit?.mesh || !hasDress(outfit.mesh)) return null;
  const material = fabricMaterial(uniforms);
  const dress = new DressCloth(body, outfit.mesh, material, scene);
  let baked = null; // tombé pré-calculé affiché (sinon : robe animée en direct)
  const live = (on) => { dress.mesh.visible = on; if (dress.hem) dress.hem.visible = on; };
  return {
    skirt: dress,
    mesh: outfit.mesh,
    get isBaked() { return !!baked?.mesh.visible; },
    showBaked(pos) {
      baked ||= new BakedDress(outfit.mesh, material, body.root);
      baked.show(pos);
      live(false);
    },
    /** Tombé animé (défilé) : image f (fractionnaire) d'un cycle de `frames` images. */
    showBakedFrame(pos, frames, f) {
      baked ||= new BakedDress(outfit.mesh, material, body.root);
      baked.showFrame(pos, frames, f);
      live(false);
    },
    showLive() { baked?.hide(); live(true); dress.reset(); },
    legFreedom: dress.legFreedom,
    halfWidthAt: (y) => dress.halfWidthAt(y),
    /** Un point du monde est-il dans la robe ? (profondeur en m, < 0 dehors) */
    penetration(world, hipsBone) {
      const l = hipsBone.worldToLocal(world.clone());
      return dress.penetration(l.x, l.y, l.z);
    },
    update(dt, env) { if (!baked?.mesh.visible) dress.update(dt, env); },
    reset() { if (!baked?.mesh.visible) dress.reset(); },
    dispose() { baked?.dispose(); dress.dispose(); },
  };
}
