// Salle d'essayage : scène 3D, caméra, interface.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
import { Rig } from './rig.js';
import { POSES } from './poses.js';
import { PRESETS } from './mannequin.js';
import { initUI } from './ui.js';

const viewport = document.getElementById('viewport');

// ---------- Rendu ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
// Tonemapping « neutre » : restitue fidèlement les couleurs (indispensable
// quand les pagnes seront appliqués sur les tenues).
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
viewport.appendChild(renderer.domElement);

const labels = new CSS2DRenderer();
labels.domElement.className = 'labels-layer';
viewport.appendChild(labels.domElement);

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;

const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 50);
camera.position.set(0, 1.1, 4.6);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.95, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 1.1;
controls.maxDistance = 7;
controls.maxPolarAngle = Math.PI * 0.6;
controls.minPolarAngle = 0.15;
controls.enablePan = true;
controls.screenSpacePanning = true;
controls.autoRotateSpeed = 1.6;
controls.addEventListener('start', () => { cameraTween = null; ui?.onUserOrbit(); });

// ---------- Lumières ----------
scene.add(new THREE.HemisphereLight(0xffffff, 0xd9cdbd, 0.55));
const key = new THREE.DirectionalLight(0xfff6ec, 2.1);
key.position.set(2.2, 4.4, 3.1);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -1.4; key.shadow.camera.right = 1.4;
key.shadow.camera.top = 2.4; key.shadow.camera.bottom = -0.4;
key.shadow.camera.near = 1; key.shadow.camera.far = 10;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.02;
key.shadow.radius = 5;
scene.add(key);
const fill = new THREE.DirectionalLight(0xffe2c4, 0.55);
fill.position.set(-3, 2, 1.5);
scene.add(fill);
const rim = new THREE.DirectionalLight(0xdfe8ff, 1.1);
rim.position.set(-0.5, 3, -4);
scene.add(rim);

// ---------- Podium avec surpiqûre ----------
const stage = new THREE.Group();
scene.add(stage);
const podium = new THREE.Mesh(
  new THREE.CylinderGeometry(1.0, 1.03, 0.07, 128),
  [
    new THREE.MeshStandardMaterial({ color: 0x24304e, roughness: 0.75 }),
    new THREE.MeshStandardMaterial({ color: 0xd9cfbf, roughness: 0.85 }),
    new THREE.MeshStandardMaterial({ color: 0x24304e }),
  ],
);
podium.position.y = -0.035;
podium.receiveShadow = true;
stage.add(podium);

const STITCHES = 140;
const stitchGeo = new THREE.CapsuleGeometry(0.0045, 0.022, 3, 8);
stitchGeo.rotateZ(Math.PI / 2);
const stitches = new THREE.InstancedMesh(stitchGeo, new THREE.MeshStandardMaterial({ color: 0xc4572e, roughness: 0.6 }), STITCHES);
{
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(1, 0.35, 1);
  for (let i = 0; i < STITCHES; i++) {
    const a = (i / STITCHES) * Math.PI * 2;
    p.set(Math.cos(a) * 0.92, 0.001, Math.sin(a) * 0.92);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a + Math.PI / 2);
    stitches.setMatrixAt(i, m.compose(p, q, s));
  }
}
stitches.count = 0;
stitches.frustumCulled = false; // l'enveloppe est calculée à vide sinon
stage.add(stitches);

const shadowCatcher = new THREE.Mesh(new THREE.CircleGeometry(4, 64), new THREE.ShadowMaterial({ opacity: 0.12 }));
shadowCatcher.rotation.x = -Math.PI / 2;
shadowCatcher.position.y = -0.069;
shadowCatcher.receiveShadow = true;
stage.add(shadowCatcher);

// ---------- Mannequin ----------
const rig = new Rig(stage);

// ---------- Caméra : vues prédéfinies ----------
export const VIEWS = [
  { id: 'face', label: 'Face', az: 0, polar: 1.47, r: 4.9, ty: 0.92 },
  { id: 'trois-quarts', label: '3/4', az: 0.72, polar: 1.43, r: 4.9, ty: 0.92 },
  { id: 'profil', label: 'Profil', az: Math.PI / 2, polar: 1.47, r: 4.9, ty: 0.92 },
  { id: 'dos', label: 'Dos', az: Math.PI, polar: 1.43, r: 4.9, ty: 0.92 },
  { id: 'dessus', label: 'Plongée', az: 0.4, polar: 0.62, r: 4.2, ty: 0.85 },
  { id: 'buste', label: 'Gros plan', az: 0.3, polar: 1.42, r: 2.0, ty: 1.28 },
];
let cameraTween = null;
const sph = new THREE.Spherical();

function fitRadius(r) {
  // Recule la caméra sur les écrans étroits pour garder le mannequin entier.
  const a = camera.aspect;
  return a < 0.8 ? r * Math.min(1.7, 0.8 / a) ** 0.85 : r;
}

export function goToView(id, duration = 1.1) {
  const v = VIEWS.find((x) => x.id === id);
  if (!v) return;
  const s = rig.body?.scale ?? 1;
  sph.setFromVector3(camera.position.clone().sub(controls.target));
  let dAz = v.az - sph.theta;
  dAz = Math.atan2(Math.sin(dAz), Math.cos(dAz));
  cameraTween = {
    t: 0, d: duration,
    from: { az: sph.theta, polar: sph.phi, r: sph.radius, ty: controls.target.y, tx: controls.target.x, tz: controls.target.z },
    to: { az: sph.theta + dAz, polar: v.polar, r: fitRadius(v.r) * (0.4 + 0.6 * s), ty: v.ty * s, tx: 0, tz: 0 },
  };
}

export function orbitBy(dAz) {
  sph.setFromVector3(camera.position.clone().sub(controls.target));
  cameraTween = {
    t: 0, d: 0.6,
    from: { az: sph.theta, polar: sph.phi, r: sph.radius, ty: controls.target.y, tx: controls.target.x, tz: controls.target.z },
    to: { az: sph.theta + dAz, polar: sph.phi, r: sph.radius, ty: controls.target.y, tx: controls.target.x, tz: controls.target.z },
  };
}

function updateCameraTween(dt) {
  if (!cameraTween) return;
  const c = cameraTween;
  c.t = Math.min(1, c.t + dt / c.d);
  const e = 1 - Math.pow(1 - c.t, 3);
  const L = (k) => c.from[k] + (c.to[k] - c.from[k]) * e;
  controls.target.set(L('tx'), L('ty'), L('tz'));
  sph.set(L('r'), L('polar'), L('az'));
  camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph));
  if (c.t >= 1) cameraTween = null;
}

// ---------- Redimensionnement ----------
function resize() {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  renderer.setSize(w, h);
  labels.setSize(w, h);
  camera.aspect = w / h;
  // Décale l'image vers le haut pour laisser la place à la barre des vues.
  const lift = w <= 860 ? 70 : 42;
  camera.setViewOffset(w, h, 0, lift, w, h);
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewport);
resize();

// ---------- Intro : la surpiqûre se coud, le mannequin pivote ----------
let intro = { t: 0, d: 2.4 };

function capturePhoto() {
  renderer.render(scene, camera);
  const url = renderer.domElement.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = url;
  a.download = `essayage-${rig.poseId}.png`;
  a.click();
}

// ---------- Interface ----------
const ui = initUI({
  rig, POSES, VIEWS, PRESETS, controls,
  goToView, orbitBy, capturePhoto,
});

// ---------- Boucle ----------
const clock = new THREE.Clock();
let first = true;
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 1 / 20);
  if (intro) {
    intro.t = Math.min(1, intro.t + dt / intro.d);
    const e = 1 - Math.pow(1 - intro.t, 3);
    stitches.count = Math.floor(STITCHES * Math.min(1, intro.t * 1.4));
    if (rig.body) rig.body.root.rotation.y = -Math.PI * 1.2 * (1 - e);
    if (intro.t >= 1) intro = null;
  }
  updateCameraTween(dt);
  rig.update(dt);
  rig.faceRuler(camera);
  if (camera.position.y < 0.08) camera.position.y = 0.08;
  controls.update(dt);
  renderer.render(scene, camera);
  labels.render(scene, camera);
  if (first) { first = false; ui.ready(); }
});

// Démarrage : caméra éloignée qui vient se placer de face.
camera.position.set(-2.4, 2.2, 5.6);
goToView('face', 2.4);

// Accès pour les tests et la console.
window.__essayage = { rig, camera, controls, goToView, scene, renderer };
