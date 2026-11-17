// Pilote du mannequin : construction selon la morphologie et les mesures,
// transitions de pose (avec IK pour poser les mains), contact au sol,
// tabouret de la pose assise et mètres rubans.
import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { buildMannequin, createSiliconeMaterial, PRESETS } from './mannequin.js';
import { POSES, expandPose } from './poses.js';

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3(), _v3 = new THREE.Vector3();
const _q = new THREE.Quaternion(), _m = new THREE.Matrix4(), _box = new THREE.Box3();

export const TAPE_LABELS = { bust: 'Poitrine', waist: 'Taille', hip: 'Hanches' };

export class Rig {
  constructor(stage, { groundY = 0 } = {}) {
    this.stage = stage;
    this.groundY = groundY;
    this.material = createSiliconeMaterial();
    this.body = null;
    this.baseCache = {};
    this.poseId = 'neutre';
    this.anim = null;
    this.showTapes = false;
    this.tapeObjs = [];
    this.stool = makeStool();
    this.stool.visible = false;
    this.stool.scale.setScalar(0.001);
    this.stoolT = 0;
    stage.add(this.stool);
    this.ruler = makeRuler();
    this.ruler.group.visible = false;
    stage.add(this.ruler.group);
  }

  /** Mesures de base (cm) d'une morphologie, calculées une fois. */
  base(presetId) {
    if (this.baseCache[presetId]) return this.baseCache[presetId];
    const b = buildMannequin(PRESETS[presetId], undefined, this.material);
    b.root.updateMatrixWorld(true);
    _box.makeEmpty();
    for (const m of b.meshes) _box.expandByObject(m, true);
    const H = _box.max.y - _box.min.y;
    const res = {
      H,
      C: { bust: b.tapes.bust.length, waist: b.tapes.waist.length, hip: b.tapes.hip.length },
      cm: {
        height: Math.round(H * PRESETS[presetId].scale * 100),
        bust: Math.round(b.tapes.bust.length * PRESETS[presetId].scale * 100),
        waist: Math.round(b.tapes.waist.length * PRESETS[presetId].scale * 100),
        hip: Math.round(b.tapes.hip.length * PRESETS[presetId].scale * 100),
      },
    };
    disposeBody(b);
    this.baseCache[presetId] = res;
    return res;
  }

  /** (Re)construit le mannequin pour une morphologie et des mesures en cm. */
  setBody(presetId, cm) {
    const base = this.base(presetId);
    const s = cm.height / 100 / base.H;
    const k = {
      bust: cm.bust / 100 / (base.C.bust * s),
      waist: cm.waist / 100 / (base.C.waist * s),
      hip: cm.hip / 100 / (base.C.hip * s),
    };
    const prev = this.body;
    const yaw = prev ? prev.root.rotation.y : 0;
    const quats = prev ? Object.fromEntries(Object.entries(prev.bones).map(([n, b]) => [n, b.quaternion.clone()])) : null;
    if (prev) { this.stage.remove(prev.root); disposeBody(prev); }

    const body = buildMannequin(PRESETS[presetId], k, this.material);
    body.root.scale.setScalar(s);
    body.root.rotation.y = yaw;
    body.scale = s;
    body.cm = { ...cm };
    this.stage.add(body.root);
    this.body = body;
    this.presetId = presetId;

    // Reprend la pose en cours sans animation (les cibles IK dépendent du corps).
    const target = this.computePose(this.poseId);
    for (const [n, q] of Object.entries(target)) body.bones[n].quaternion.copy(q);
    if (this.anim) this.anim.to = target;
    else if (quats) { /* pose instantanée déjà appliquée */ }
    this.buildTapes();
    this.ground();
    this.ruler.setHeight(cm.height / 100);
    return body;
  }

  computePose(id) {
    const pose = POSES.find((p) => p.id === id) || POSES[0];
    const { bones, rest, root } = this.body;
    const saved = Object.fromEntries(Object.entries(bones).map(([n, b]) => [n, b.quaternion.clone()]));
    const rot = expandPose(pose);
    for (const [n, b] of Object.entries(bones)) {
      b.quaternion.copy(rest[n]);
      const r = rot[n];
      if (r) b.quaternion.multiply(_q.setFromEuler(new THREE.Euler(r[0], r[1], r[2])));
    }
    root.updateMatrixWorld(true);
    if (pose.ik) {
      for (const [side, spec] of Object.entries(pose.ik)) {
        const t = spec.target(this.body);
        const T = root.localToWorld(new THREE.Vector3(...t));
        const pole = new THREE.Vector3(...spec.pole).applyQuaternion(root.getWorldQuaternion(new THREE.Quaternion()));
        solveTwoBone(bones[`${side}Arm`], bones[`${side}ForeArm`], bones[`${side}Hand`], T, pole);
      }
    }
    const out = Object.fromEntries(Object.entries(bones).map(([n, b]) => [n, b.quaternion.clone()]));
    for (const [n, b] of Object.entries(bones)) b.quaternion.copy(saved[n]);
    root.updateMatrixWorld(true);
    return out;
  }

  setPose(id, duration = 0.9) {
    const pose = POSES.find((p) => p.id === id);
    if (!pose || !this.body) return;
    this.poseId = id;
    const from = Object.fromEntries(Object.entries(this.body.bones).map(([n, b]) => [n, b.quaternion.clone()]));
    const to = this.computePose(id);
    this.stoolTarget = pose.stool ? 1 : 0;
    if (duration <= 0) {
      for (const [n, q] of Object.entries(to)) this.body.bones[n].quaternion.copy(q);
      this.anim = null;
      this.stoolT = this.stoolTarget;
      this.ground();
      return;
    }
    this.anim = { from, to, t: 0, d: duration };
  }

  ground() {
    const { root } = this.body;
    root.position.y = 0;
    root.updateMatrixWorld(true);
    root.position.y = this.groundY - this.body.lowestSole();
    root.updateMatrixWorld(true);
  }

  update(dt) {
    if (!this.body) return;
    if (this.anim) {
      const a = this.anim;
      a.t = Math.min(1, a.t + dt / a.d);
      const e = ease(a.t);
      for (const [n, b] of Object.entries(this.body.bones)) b.quaternion.slerpQuaternions(a.from[n], a.to[n], e);
      if (a.t >= 1) this.anim = null;
      this.ground();
    }
    // Socle cubique : sort du sol sous le bassin dans la pose assise.
    const st = this.stoolTarget ?? 0;
    this.stoolT += Math.sign(st - this.stoolT) * Math.min(Math.abs(st - this.stoolT), dt * 2.2);
    if (this.stoolT > 0.001) {
      const pelvisBottom = this.body.lowestSeat();
      const top = Math.max(0.05, pelvisBottom + 0.01 * this.body.scale);
      this.stool.visible = true;
      this.stool.scale.set(1, Math.max(0.001, top * ease(this.stoolT)), 1);
      const hp = this.body.bones.Hips.getWorldPosition(_v1);
      this.stool.position.set(hp.x, 0, hp.z - 0.06 * this.body.scale);
    } else this.stool.visible = false;
    // Mètres rubans : tracé progressif.
    for (const t of this.tapeObjs) {
      const goal = this.showTapes ? 1 : 0;
      t.p += Math.sign(goal - t.p) * Math.min(Math.abs(goal - t.p), dt * 1.6);
      const e2 = ease(t.p);
      t.mesh.geometry.setDrawRange(0, Math.floor(t.count * e2 / 6) * 6);
      t.mesh.visible = t.p > 0.001;
      t.label.visible = t.p > 0.6;
      t.label.element.style.opacity = String(Math.max(0, (t.p - 0.6) / 0.4));
    }
    this.ruler.group.visible = this.showTapes || this.ruler.p > 0.001;
    this.ruler.p += Math.sign((this.showTapes ? 1 : 0) - this.ruler.p) * Math.min(Math.abs((this.showTapes ? 1 : 0) - this.ruler.p), dt * 2);
    this.ruler.group.scale.y = Math.max(0.001, ease(this.ruler.p));
    this.ruler.label.element.style.opacity = String(this.ruler.p > 0.9 ? 1 : 0);
  }

  faceRuler(camera) {
    const g = this.ruler.group;
    g.rotation.y = Math.atan2(camera.position.x - g.position.x, camera.position.z - g.position.z);
  }

  buildTapes() {
    for (const t of this.tapeObjs) { t.mesh.parent.remove(t.mesh); t.mesh.geometry.dispose(); t.label.parent?.remove(t.label); t.label.element.remove(); }
    this.tapeObjs = [];
    const mat = this.tapeMat || (this.tapeMat = new THREE.MeshStandardMaterial({ color: 0x1c1c1c, roughness: 0.5 }));
    for (const [key, tape] of Object.entries(this.body.tapes)) {
      const pts = tape.hull.map(([x, z]) => new THREE.Vector3(x * 1.012, tape.y - tape.yOffset, z * 1.012 + (z > 0 ? 0.002 : -0.002)));
      const curve = new THREE.CatmullRomCurve3(pts, true, 'centripetal');
      const geo = new THREE.TubeGeometry(curve, 160, 0.0028, 6, true);
      const mesh = new THREE.Mesh(geo, mat);
      mesh.visible = false;
      tape.bone.add(mesh);
      // Étiquette posée à l'avant-gauche du ruban.
      let best = pts[0], score = -Infinity;
      for (const p of pts) { const s = p.x * 0.75 + p.z * 0.66; if (s > score) { score = s; best = p; } }
      const el = document.createElement('div');
      el.className = 'tape-label';
      el.innerHTML = `<span>${TAPE_LABELS[key]}</span><strong>${this.body.cm[key]} cm</strong>`;
      const label = new CSS2DObject(el);
      label.position.copy(best).multiplyScalar(1.02);
      label.center.set(-0.08, 0.5);
      tape.bone.add(label);
      const prev = this.tapeP?.[key] ?? 0;
      this.tapeObjs.push({ key, mesh, label, count: geo.index.count, p: prev });
    }
    this.tapeP = Object.fromEntries(this.tapeObjs.map((t) => [t.key, t.p]));
  }

  setTapesVisible(v) { this.showTapes = v; }
}

/** IK à deux segments : épaule-coude-poignet, coude orienté vers `pole`. */
function solveTwoBone(A, B, C, T, pole) {
  A.parent.updateWorldMatrix(true, false);
  const S = A.getWorldPosition(new THREE.Vector3());
  const E0 = B.getWorldPosition(new THREE.Vector3());
  const W0 = C.getWorldPosition(new THREE.Vector3());
  const l1 = S.distanceTo(E0), l2 = E0.distanceTo(W0);
  const d = T.clone().sub(S);
  const dist = THREE.MathUtils.clamp(d.length(), Math.abs(l1 - l2) + 1e-3, l1 + l2 - 1e-3);
  const dh = d.normalize();
  const cosA = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist);
  const sinA = Math.sqrt(Math.max(0, 1 - cosA * cosA));
  const perp = pole.clone().sub(dh.clone().multiplyScalar(pole.dot(dh))).normalize();
  const E = S.clone().addScaledVector(dh, l1 * cosA).addScaledVector(perp, l1 * sinA);
  const W = S.clone().addScaledVector(dh, dist);

  const yA = _v1.copy(S).sub(E).normalize();
  const fwd = _v2.copy(W).sub(E);
  const zA = fwd.sub(yA.clone().multiplyScalar(fwd.dot(yA)));
  if (zA.lengthSq() < 1e-8) zA.copy(perp).multiplyScalar(-1);
  zA.normalize();
  const xA = _v3.crossVectors(yA, zA).normalize();
  const qA = new THREE.Quaternion().setFromRotationMatrix(_m.makeBasis(xA, yA, zA));
  setWorldQuat(A, qA);

  const yB = E.clone().sub(W).normalize();
  const xB = xA.clone();
  const zB = new THREE.Vector3().crossVectors(xB, yB).normalize();
  const xB2 = new THREE.Vector3().crossVectors(yB, zB).normalize();
  const qB = new THREE.Quaternion().setFromRotationMatrix(_m.makeBasis(xB2, yB, zB));
  setWorldQuat(B, qB);
}

function setWorldQuat(obj, qWorld) {
  const pq = obj.parent.getWorldQuaternion(new THREE.Quaternion());
  obj.quaternion.copy(pq.invert().multiply(qWorld));
  obj.updateMatrixWorld(true);
}

function disposeBody(b) {
  const seen = new Set();
  b.root.traverse((o) => { if (o.isMesh && !seen.has(o.geometry)) { seen.add(o.geometry); o.geometry.dispose(); } });
  b.root.traverse((o) => { if (o.isCSS2DObject) o.element.remove(); if (o.isSkinnedMesh) o.skeleton.dispose(); });
}

/** Socle en béton (hauteur unitaire, mis à l'échelle en y). */
function makeStool() {
  const geo = new THREE.BoxGeometry(0.44, 1, 0.44);
  geo.translate(0, 0.5, 0);
  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0xd2cfca, roughness: 0.92 }));
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

/** Toise façon mètre ruban de couturière, avec repère de hauteur. */
function makeRuler() {
  const H = 2.0;
  const c = document.createElement('canvas');
  c.width = 96; c.height = 2048;
  const x = c.getContext('2d');
  x.fillStyle = '#fbfaf8'; x.fillRect(0, 0, c.width, c.height);
  x.fillStyle = '#1c1c1c';
  x.font = '500 20px system-ui, sans-serif';
  x.textAlign = 'right';
  for (let cm = 0; cm <= 200; cm++) {
    const y = c.height - (cm / 200) * c.height;
    const len = cm % 10 === 0 ? 46 : cm % 5 === 0 ? 30 : 16;
    x.fillRect(0, y - 1, len, 2);
    if (cm % 10 === 0 && cm > 0 && cm < 200) {
      x.save(); x.translate(88, y + 8); x.fillText(String(cm), 0, 0); x.restore();
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const group = new THREE.Group();
  group.position.set(-0.6, 0, 0.1);
  const strip = new THREE.Mesh(new THREE.PlaneGeometry(0.05, H), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.7, side: THREE.DoubleSide }));
  strip.position.y = H / 2;
  strip.castShadow = true;
  group.add(strip);
  const marker = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.006, 0.006), new THREE.MeshStandardMaterial({ color: 0x1c1c1c }));
  group.add(marker);
  const el = document.createElement('div');
  el.className = 'tape-label tape-label--height';
  const label = new CSS2DObject(el);
  label.center.set(1.08, 0.5);
  group.add(label);
  const api = {
    group, label, p: 0,
    setHeight(h) {
      marker.position.set(0.08, h, 0);
      label.position.set(-0.03, h, 0);
      el.innerHTML = `<span>Hauteur</span><strong>${Math.round(h * 100)} cm</strong>`;
    },
  };
  return api;
}
