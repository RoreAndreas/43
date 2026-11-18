// Décor : studio comme les rendus de la vidéo « Walk Cycle » (P2Design).
// Fond gris foncé en dégradé, sol qui se fond dans le fond, lumière de studio
// douce (lumière principale, contre-jour chaud, débouchage froid), ombre au sol.
import * as THREE from 'three';

export const PLATE_TOP = 0; // pas de plaque : le mannequin est posé au sol

function gradientTexture(top, bottom) {
  const c = document.createElement('canvas');
  c.width = 4; c.height = 512;
  const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, 512);
  g.addColorStop(0, top); g.addColorStop(0.62, bottom); g.addColorStop(1, bottom);
  x.fillStyle = g; x.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function floorTexture() {
  // tache claire au centre qui se fond dans le fond (studio « infini »)
  const S = 512, c = document.createElement('canvas');
  c.width = c.height = S;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.35, 'rgba(255,255,255,0.85)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, S, S);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function buildDecor(scene, renderer, { lite = false } = {}) {
  const BG = '#2c2c2f';
  scene.background = gradientTexture('#17171a', BG);
  scene.fog = null;
  const group = new THREE.Group();
  scene.add(group);

  scene.add(new THREE.HemisphereLight(0xdfe4ee, 0x2a2a2c, 0.55));
  // lumière principale : avant gauche, haute, ombres douces
  const key = new THREE.DirectionalLight(0xfff6ec, 2.1);
  key.position.set(-2.2, 5.5, 3.6);
  key.castShadow = true;
  key.shadow.mapSize.set(lite ? 1024 : 2048, lite ? 1024 : 2048);
  Object.assign(key.shadow.camera, { left: -2.2, right: 2.2, top: 2.6, bottom: -1.2, near: 1, far: 14 });
  key.shadow.bias = -0.0003;
  key.shadow.normalBias = 0.015;
  key.shadow.radius = 4;
  key.shadow.blurSamples = 12;
  scene.add(key, key.target);
  // contre-jour chaud (le liseré orangé des rendus de la vidéo)
  const rim = new THREE.DirectionalLight(0xffb36b, 2.4);
  rim.position.set(3.2, 3.2, -3.4);
  scene.add(rim, rim.target);
  // débouchage froid, côté opposé
  const fill = new THREE.DirectionalLight(0xc9d6ff, 0.55);
  fill.position.set(3.5, 1.6, 2.5);
  scene.add(fill, fill.target);

  // sol : gris moyen, éclairci sous le mannequin, fondu dans le fond
  const base = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: 0x2c2c2f, roughness: 0.95 }));
  base.rotation.x = -Math.PI / 2;
  base.position.y = -0.002;
  base.receiveShadow = true;
  group.add(base);
  const pool = new THREE.Mesh(
    new THREE.CircleGeometry(4.2, 64),
    new THREE.MeshStandardMaterial({ color: 0x8c8b88, roughness: 0.85, map: floorTexture(), transparent: true, depthWrite: false }),
  );
  pool.rotation.x = -Math.PI / 2;
  pool.receiveShadow = true;
  group.add(pool);
  // ombre portée seule, plus marquée (le sol clair la rend peu visible)
  const shadowCatcher = new THREE.Mesh(new THREE.CircleGeometry(4.2, 64), new THREE.ShadowMaterial({ opacity: 0.35 }));
  shadowCatcher.rotation.x = -Math.PI / 2;
  shadowCatcher.position.y = 0.001;
  shadowCatcher.receiveShadow = true;
  group.add(shadowCatcher);

  const plate = new THREE.Object3D(); // (compatibilité : pas de plaque dans le studio)
  const lights = [[key, key.position.clone()], [rim, rim.position.clone()], [fill, fill.position.clone()]];
  return {
    plate,
    /** Le studio suit le mannequin (défilé) : sol éclairé, lumières et ombre. */
    follow(x, z) {
      for (const [l, p] of lights) { l.position.set(p.x + x, p.y, p.z + z); l.target.position.set(x, 0, z); }
      pool.position.set(x, 0, z);
      shadowCatcher.position.set(x, 0.001, z);
    },
    update() {},
  };
}
