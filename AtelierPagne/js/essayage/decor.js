// Décor : showroom clair et épuré. Mur blanc, sol en béton, plaque d'acier
// sous le mannequin, socles cubiques, cadres métalliques drapés de lin et un
// peu de végétation.
import * as THREE from 'three';

const WALL = 0xe9e7e3;
export const PLATE_TOP = 0.012;

export function buildDecor(scene, renderer, { lite = false } = {}) {
  scene.background = new THREE.Color(WALL);
  scene.fog = new THREE.Fog(WALL, 9, 24);
  const group = new THREE.Group();
  scene.add(group);

  // ---------- Lumière douce de jour ----------
  scene.add(new THREE.HemisphereLight(0xffffff, 0xcfcac2, 0.62));
  const key = new THREE.DirectionalLight(0xfffaf3, 1.75);
  key.position.set(-2.6, 5.2, 3.4);
  key.castShadow = true;
  key.shadow.mapSize.set(lite ? 1024 : 2048, lite ? 1024 : 2048);
  Object.assign(key.shadow.camera, { left: -3.4, right: 3.4, top: 3.2, bottom: -3.2, near: 1, far: 14 });
  key.shadow.bias = -0.0003;
  key.shadow.normalBias = 0.02;
  key.shadow.radius = 7;
  key.shadow.blurSamples = 16;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xf3f6ff, 0.55);
  fill.position.set(3, 2.4, 2);
  scene.add(fill);
  const back = new THREE.DirectionalLight(0xffffff, 0.6);
  back.position.set(0.5, 3, -4);
  scene.add(back);

  // ---------- Sol béton et mur circulaire ----------
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(12, 96),
    new THREE.MeshStandardMaterial({ map: concreteTexture(), roughness: 0.82 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  group.add(floor);
  const wall = new THREE.Mesh(
    new THREE.CylinderGeometry(9, 9, 9, 128, 1, true),
    new THREE.MeshStandardMaterial({ color: WALL, roughness: 1, side: THREE.BackSide }),
  );
  wall.position.y = 4.5;
  group.add(wall);

  // ---------- Plaque d'acier sous le mannequin ----------
  const steel = new THREE.MeshStandardMaterial({ color: 0xc7c9cc, metalness: 0.6, roughness: 0.38 });
  const plate = new THREE.Mesh(new THREE.BoxGeometry(0.56, PLATE_TOP, 0.56), steel);
  plate.position.y = PLATE_TOP / 2;
  plate.castShadow = plate.receiveShadow = true;
  group.add(plate);

  // ---------- Socles en béton ----------
  const concrete = new THREE.MeshStandardMaterial({ color: 0xd6d3ce, roughness: 0.93 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x2a2a2a, roughness: 0.7 });
  const cube = (w, h, d, x, z, ry = 0, mat = concrete) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, h / 2, z);
    m.rotation.y = ry;
    m.castShadow = m.receiveShadow = true;
    group.add(m);
    return m;
  };
  cube(0.5, 0.5, 0.5, -1.75, -1.75, 0.2);
  cube(0.42, 0.82, 0.42, -1.25, -2.15, 0.2);
  cube(0.32, 0.36, 0.32, -1.3, -1.5, 0.3, dark);
  cube(0.46, 0.62, 0.46, 1.95, -1.35, -0.25);
  cube(0.4, 0.34, 0.4, 2.3, -0.95, -0.1);

  // ---------- Cadres métalliques drapés ----------
  const chrome = new THREE.MeshStandardMaterial({ color: 0xc9cbce, metalness: 0.95, roughness: 0.22 });
  const frame = (x, z, ry, w, h, cloth) => {
    const f = new THREE.Group();
    const bar = (len, px, py, horiz) => {
      const b = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, len, 10), chrome);
      b.position.set(px, py, 0);
      if (horiz) b.rotation.z = Math.PI / 2;
      b.castShadow = true;
      f.add(b);
    };
    bar(h, -w / 2, h / 2); bar(h, w / 2, h / 2);
    bar(w, 0, h, true); bar(w, 0, 0.012, true);
    const fab = new THREE.Mesh(drape(w * 0.86, h * 0.92, cloth.seed), new THREE.MeshStandardMaterial({ color: cloth.color, roughness: 0.95, side: THREE.DoubleSide }));
    fab.position.set(0, h, 0);
    fab.castShadow = fab.receiveShadow = true;
    f.add(fab);
    f.position.set(x, 0, z);
    f.rotation.y = ry;
    group.add(f);
  };
  frame(1.05, -2.5, -0.22, 0.95, 2.0, { color: 0xd8cdbd, seed: 1 });
  frame(1.95, -2.15, -0.55, 0.85, 1.85, { color: 0xb9b2a8, seed: 2.4 });
  frame(-2.6, -0.9, 0.9, 0.9, 1.9, { color: 0xcfc4b3, seed: 3.7 });

  // ---------- Végétation ----------
  group.add(plant(-1.55, -1.35, 1, 42));
  group.add(plant(-2.05, -1.95, 0.8, 7));
  group.add(plant(2.25, -1.7, 0.85, 19));

  scene.add(key.target);
  const keyOffset = key.position.clone();
  return {
    plate,
    /** L'ombre portée suit le mannequin quand il se déplace (défilé). */
    follow(x, z) { key.position.set(keyOffset.x + x, keyOffset.y, keyOffset.z + z); key.target.position.set(x, 0, z); },
    update() {},
  };
}

// ---------- Textures et géométries ----------
function concreteTexture() {
  const S = 1024;
  const c = document.createElement('canvas');
  c.width = c.height = S;
  const x = c.getContext('2d');
  x.fillStyle = '#cfccc6'; x.fillRect(0, 0, S, S);
  let seed = 11;
  const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  // Nuages de teinte, raccordables.
  for (let i = 0; i < 160; i++) {
    const px = r() * S, py = r() * S, rad = 40 + r() * 180;
    const light = r() > 0.5;
    for (const dx of [-S, 0, S]) for (const dy of [-S, 0, S]) {
      const g = x.createRadialGradient(px + dx, py + dy, 0, px + dx, py + dy, rad);
      g.addColorStop(0, light ? 'rgba(255,255,255,0.035)' : 'rgba(90,85,78,0.03)');
      g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g;
      x.fillRect(px + dx - rad, py + dy - rad, rad * 2, rad * 2);
    }
  }
  // Grain fin.
  const img = x.getImageData(0, 0, S, S);
  for (let i = 0; i < img.data.length; i += 4) {
    const n = (r() - 0.5) * 10;
    img.data[i] += n; img.data[i + 1] += n; img.data[i + 2] += n;
  }
  x.putImageData(img, 0, 0);
  // Joints de dalles.
  x.fillStyle = 'rgba(80,76,70,0.18)';
  x.fillRect(0, 0, S, 2);
  x.fillRect(0, 0, 2, S);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(10, 10);
  t.offset.set(0.37, 0.61); // aucun joint de dalle sous le mannequin
  t.anisotropy = 8;
  return t;
}

/** Tissu jeté sur la barre haute : un pan devant, un pan derrière, plis souples. */
function drape(W, H, seed) {
  const geo = new THREE.PlaneGeometry(W, H * 1.55, 36, 48);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i);
    const s = (p.getY(i) + (H * 1.55) / 2) / (H * 1.55); // 0..1 le long du tissu
    const along = s * H * 1.55;
    const front = along < H; // premier pan devant, le reste replié derrière
    const d = front ? along : along - H;
    const y = front ? -H + along : -d * 0.95;
    const fold = 0.012 + 0.03 * (front ? 1 - along / H : d / (H * 0.55));
    let z = (front ? 0.02 : -0.02) + fold * Math.sin((x / W) * Math.PI * 4 + seed) + 0.008 * Math.sin((x / W) * 13 + seed * 2);
    if (Math.abs(y) < 0.03) z *= 0.3;
    p.setXYZ(i, x * (1 - 0.04 * (front ? 1 - along / H : 0)), y, z);
  }
  geo.computeVertexNormals();
  return geo;
}

/** Touffe de feuillage : tiges souples, petites feuilles, quelques fleurs blanches. */
function plant(x, z, size, seed) {
  const g = new THREE.Group();
  let s = seed;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const stemMat = new THREE.MeshStandardMaterial({ color: 0x55603f, roughness: 0.8 });
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x4d5c3a, roughness: 0.75, side: THREE.DoubleSide });
  const flowerMat = new THREE.MeshStandardMaterial({ color: 0xf4f2ec, roughness: 0.7 });
  const leafGeo = new THREE.CircleGeometry(0.03, 8);
  leafGeo.scale(0.45, 1, 1);
  const leaves = [], flowers = [];
  for (let i = 0; i < 26; i++) {
    const a = r() * Math.PI * 2, lean = 0.2 + r() * 0.5, h = (0.35 + r() * 0.55) * size;
    const pts = [];
    for (let k = 0; k <= 6; k++) {
      const t = k / 6;
      pts.push(new THREE.Vector3(Math.cos(a) * lean * h * t * t, h * t, Math.sin(a) * lean * h * t * t));
    }
    const curve = new THREE.CatmullRomCurve3(pts);
    const stem = new THREE.Mesh(new THREE.TubeGeometry(curve, 8, 0.003, 4), stemMat);
    stem.castShadow = true;
    g.add(stem);
    for (let k = 0; k < 7; k++) {
      const t = 0.25 + r() * 0.75;
      const m = new THREE.Matrix4();
      const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(r() * 3, r() * 6, r() * 3));
      m.compose(curve.getPoint(t), q, new THREE.Vector3(1, 1, 1).multiplyScalar(0.7 + r() * 0.6));
      leaves.push(m);
    }
    if (r() > 0.55) flowers.push(new THREE.Matrix4().makeTranslation(curve.getPoint(1)));
  }
  const L = new THREE.InstancedMesh(leafGeo, leafMat, leaves.length);
  leaves.forEach((m, i) => L.setMatrixAt(i, m));
  L.castShadow = true;
  const F = new THREE.InstancedMesh(new THREE.SphereGeometry(0.014, 8, 6), flowerMat, flowers.length);
  flowers.forEach((m, i) => F.setMatrixAt(i, m));
  g.add(L, F);
  g.position.set(x, 0, z);
  return g;
}
