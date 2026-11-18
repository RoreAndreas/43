// Salle d'essayage : scène 3D, caméra, interface.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
import { Rig } from './rig.js';
import { POSES } from './poses.js';
import { PRESETS, loadMannequins } from './mannequin.js';
import { initUI } from './ui.js';
import { buildDecor, PLATE_TOP } from './decor.js';
import { loadDresses, loadBakeIndex } from './dress.js';

const viewport = document.getElementById('viewport');

// ---------- Rendu ----------
// Mode téléphone : résolution, ombres et anticrénelage allégés.
const lite = Math.min(window.innerWidth, window.innerHeight) < 700 || window.matchMedia('(pointer: coarse)').matches;
const renderer = new THREE.WebGLRenderer({ antialias: !lite || window.devicePixelRatio < 2, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, lite ? 1.5 : 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
// Tonemapping « neutre » : couleurs fidèles (indispensable pour les pagnes).
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = lite ? THREE.PCFSoftShadowMap : THREE.VSMShadowMap;
viewport.appendChild(renderer.domElement);

const labels = new CSS2DRenderer();
labels.domElement.className = 'labels-layer';
viewport.appendChild(labels.domElement);

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.35;

const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 60);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.95, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 1.2;
controls.maxDistance = 8;
controls.maxPolarAngle = Math.PI * 0.56;
controls.minPolarAngle = 0.2;
controls.enablePan = false;
controls.autoRotateSpeed = 1.4;
controls.addEventListener('start', () => { cameraTween = null; ui?.onUserOrbit(); });

// ---------- Décor et mannequin ----------
const DRESSES = ['aveline', 'bretelles'];
await Promise.all([loadMannequins(), loadDresses(DRESSES), ...DRESSES.map((d) => loadBakeIndex(d))]);
const decor = buildDecor(scene, renderer, { lite });
const stage = new THREE.Group();
scene.add(stage);
const rig = new Rig(stage, { groundY: PLATE_TOP });

// ---------- Caméra : vues prédéfinies ----------
export const VIEWS = [
  { id: 'face', label: 'Face', az: 0, polar: 1.48, r: 5.2, ty: 0.95 },
  { id: 'trois-quarts', label: '3/4', az: 0.7, polar: 1.46, r: 5.2, ty: 0.95 },
  { id: 'profil', label: 'Profil', az: Math.PI / 2, polar: 1.48, r: 5.2, ty: 0.95 },
  { id: 'dos', label: 'Dos', az: Math.PI, polar: 1.46, r: 5.2, ty: 0.95 },
];
let cameraTween = null;
const follow = new THREE.Vector3(); // position suivie par la caméra (le mannequin, pendant le défilé)
const sph = new THREE.Spherical();

function fitRadius(r) {
  // Recule la caméra sur les écrans étroits pour garder le mannequin entier.
  const a = camera.aspect;
  return a < 0.8 ? r * Math.min(1.7, 0.8 / a) ** 0.85 : r;
}

function tweenTo(to, d) {
  sph.setFromVector3(camera.position.clone().sub(controls.target));
  cameraTween = {
    t: 0, d,
    from: { az: sph.theta, polar: sph.phi, r: sph.radius, ty: controls.target.y },
    to: { az: sph.theta + Math.atan2(Math.sin(to.az - sph.theta), Math.cos(to.az - sph.theta)), polar: to.polar ?? sph.phi, r: to.r ?? sph.radius, ty: to.ty ?? controls.target.y },
  };
}

export function goToView(id, duration = 1.1) {
  const v = VIEWS.find((x) => x.id === id);
  if (!v) return;
  const s = rig.body?.scale ?? 1;
  tweenTo({ az: v.az, polar: v.polar, r: fitRadius(v.r) * (0.4 + 0.6 * s), ty: v.ty * s }, duration);
}

export function orbitBy(dAz) {
  sph.setFromVector3(camera.position.clone().sub(controls.target));
  tweenTo({ az: sph.theta + dAz }, 0.6);
}

function updateCameraTween(dt) {
  if (!cameraTween) return;
  const c = cameraTween;
  c.t = Math.min(1, c.t + dt / c.d);
  const e = 1 - Math.pow(1 - c.t, 3);
  const L = (k) => c.from[k] + (c.to[k] - c.from[k]) * e;
  controls.target.set(follow.x, L('ty'), follow.z);
  sph.set(L('r'), L('polar'), L('az'));
  camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph));
  if (c.t >= 1) cameraTween = null;
}

// ---------- Cadrage : laisse la place à l'interface (barre du bas, tiroir) ----------
const inset = { right: 0, bottom: 0, tRight: 0, tBottom: 0 };
export function setInsets({ right = 0, bottom = 0 }) { inset.tRight = right; inset.tBottom = bottom; }

function applyViewOffset() {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  const dock = document.querySelector('.dock')?.offsetHeight ?? 0;
  const top = document.querySelector('.top')?.offsetHeight ?? 0;
  // Centre le mannequin dans l'espace libre entre la barre du haut, le dock et le tiroir.
  const offX = inset.right / 2;
  const offY = (dock + inset.bottom - top) / 2;
  camera.setViewOffset(w, h, offX, offY, w, h);
  camera.updateProjectionMatrix();
}

function resize() {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  renderer.setSize(w, h);
  labels.setSize(w, h);
  camera.aspect = w / h;
  applyViewOffset();
}
new ResizeObserver(resize).observe(viewport);
resize();

function capturePhoto() {
  renderer.render(scene, camera);
  const a = document.createElement('a');
  a.href = renderer.domElement.toDataURL('image/png');
  a.download = `essayage-${rig.poseId}.png`;
  a.click();
}

// ---------- Défilé : fondu bref quand le parcours recommence ----------
const fadeEl = document.getElementById('fade');
rig.onClipFadeOut = () => { document.getElementById('fade-label').textContent = ''; fadeEl.classList.add('is-on'); };
rig.onClipWrap = () => setTimeout(() => fadeEl.classList.remove('is-on'), 60);

// ---------- Interface ----------
const ui = initUI({ rig, POSES, VIEWS, PRESETS, controls, goToView, orbitBy, capturePhoto, setInsets });

// ---------- Boucle ----------
let intro = { t: 0, d: 1.8 };
const clock = new THREE.Clock();
let first = true;
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 1 / 20);
  if (intro) {
    intro.t = Math.min(1, intro.t + dt / intro.d);
    const e = 1 - Math.pow(1 - intro.t, 3);
    if (rig.body) rig.body.root.rotation.y = -0.6 * Math.PI * (1 - e);
    if (intro.t >= 1) intro = null;
  }
  // Cadrage animé quand le tiroir s'ouvre ou se ferme.
  if (Math.abs(inset.tRight - inset.right) > 0.5 || Math.abs(inset.tBottom - inset.bottom) > 0.5) {
    const k = 1 - Math.exp(-dt * 10);
    inset.right += (inset.tRight - inset.right) * k;
    inset.bottom += (inset.tBottom - inset.bottom) * k;
    applyViewOffset();
  }
  updateCameraTween(dt);
  decor.update(dt);
  rig.update(dt);
  // Défilé : le mannequin avance, la caméra le suit (comme un travelling).
  const rp = rig.body?.root.position;
  if (rp && (rp.x !== follow.x || rp.z !== follow.z)) {
    const dx = rp.x - follow.x, dz = rp.z - follow.z;
    camera.position.x += dx; camera.position.z += dz;
    controls.target.x += dx; controls.target.z += dz;
    follow.set(rp.x, 0, rp.z);
  }
  decor.plate.visible = !rig.clip;
  rig.faceRuler(camera);
  controls.update(dt);
  renderer.render(scene, camera);
  labels.render(scene, camera);
  if (first) { first = false; ui.ready(); }
});

// Démarrage : la caméra s'approche doucement.
camera.position.set(-1.6, 1.6, 7);
goToView('face', 1.8);

// Accès pour les tests et la console.
window.__essayage = { rig, camera, controls, goToView, scene, renderer, skipIntro: () => { if (intro) intro.t = 0.999; } };
