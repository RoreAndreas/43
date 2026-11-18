// Pilote du mannequin : construction selon la morphologie et les mesures,
// affichage d'une pose (instantané, avec le tombé de robe pré-calculé quand il
// existe ; transition animée seulement pour le pré-calcul lui-même), regard au
// repos, rotation sur le socle, tenue, contact au sol, socle assis, rubans.
import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { buildMannequin, createSiliconeMaterial, PRESETS } from './mannequin.js';
import { POSES, expandPose } from './poses.js';
import { OUTFITS, buildOutfit, fabricUniforms } from './garments.js';
import { hasBake, loadBake } from './dress.js';

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3(), _v3 = new THREE.Vector3();
const _q = new THREE.Quaternion(), _m = new THREE.Matrix4(), _box = new THREE.Box3();

const _e = new THREE.Euler(), _qt = new THREE.Quaternion();
// Réactivité de chaque os (1/s) : le bassin répond vite, la tête et les mains avec souplesse.
const FOLLOW = {
  Hips: 16, Spine: 12, Neck: 9, Head: 7, LeftUpLeg: 16, RightUpLeg: 16, LeftLeg: 16, RightLeg: 16, LeftFoot: 14, RightFoot: 14,
  LeftArm: 10, RightArm: 10, LeftForeArm: 9, RightForeArm: 9, LeftHand: 8, RightHand: 8,
};
// Retard (s) de chaque os dans une transition de pose.
const LAG = {
  Hips: 0, LeftUpLeg: 0, RightUpLeg: 0, LeftLeg: 0.03, RightLeg: 0.03, LeftFoot: 0.06, RightFoot: 0.06,
  Spine: 0.05, Neck: 0.12, Head: 0.18, LeftArm: 0.1, RightArm: 0.1, LeftForeArm: 0.16, RightForeArm: 0.16, LeftHand: 0.22, RightHand: 0.22,
};

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
    // Ombres de contact sous les pieds (le pied posé « pèse » sur le sol)
    this.contact = ['Left', 'Right'].map(() => makeContactShadow());
    for (const c of this.contact) stage.add(c);
    this.ruler = makeRuler();
    this.ruler.group.visible = false;
    stage.add(this.ruler.group);
    this.basePose = null; // pose courante, avant le mouvement au repos
    this.idleOn = true;
    this.idleAmt = 1;
    this.time = 0;
    this.look = 0;
    this.lookTarget = 0;
    this.nextLook = 2.5;
    this.spinOn = false;
    this.spinSpeed = 0;
    this.outfitId = 'aucune';
    this.sizeId = null;
    // tombés pré-calculés : désactivés pendant le pré-calcul lui-même (?bake)
    this.bakes = !new URLSearchParams(location.search).has('bake');
    this.fabric = fabricUniforms();
    this.outfit = null;
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
  setBody(presetId, cm, { outfit = true } = {}) {
    const base = this.base(presetId);
    const s = cm.height / 100 / base.H;
    const k = {
      bust: cm.bust / 100 / (base.C.bust * s),
      waist: cm.waist / 100 / (base.C.waist * s),
      hip: cm.hip / 100 / (base.C.hip * s),
    };
    this.stopClip();
    const prev = this.body;
    const yaw = prev ? prev.root.rotation.y : 0;
    if (prev) { this.outfit?.dispose(); this.outfit = null; this.stage.remove(prev.root); disposeBody(prev); }

    const body = buildMannequin(PRESETS[presetId], k, this.material);
    body.root.scale.setScalar(s);
    body.root.rotation.y = yaw;
    body.scale = s;
    body.cm = { ...cm };
    this.stage.add(body.root);
    this.body = body;
    this.presetId = presetId;

    // Reprend la pose en cours sans animation (les cibles IK dépendent du corps).
    this.basePose = this.computePose(this.poseId);
    this.anim = null;
    this.applyBones(0);
    this.ground();
    // Pendant un réglage au curseur, la tenue n'est réajustée qu'au relâchement.
    if (outfit) {
      this.buildOutfit();
      // la pose s'adapte au volume de la tenue
      this.basePose = this.computePose(this.poseId);
      this.applyBones(0);
      this.ground();
      this.outfit?.reset();
    }
    this.buildTapes();
    this.ruler.setHeight(cm.height / 100);
    return body;
  }

  computePose(id) {
    const pose = POSES.find((p) => p.id === id) || POSES[0];
    const { bones, rest, root } = this.body;
    const saved = Object.fromEntries(Object.entries(bones).map(([n, b]) => [n, b.quaternion.clone()]));
    const rot = expandPose(pose);
    // Le corps s'adapte à la tenue : une jupe étroite raccourcit le pas.
    const free = this.outfit?.legFreedom ?? 1;
    if (free < 1 && !pose.stool) {
      for (const n of Object.keys(rot)) {
        if (!/UpLeg|Leg|Foot/.test(n)) continue;
        const [x, y, z] = rot[n];
        rot[n] = [x * (/Foot/.test(n) ? free : free), y * free, z];
      }
    }
    for (const [n, b] of Object.entries(bones)) {
      b.quaternion.copy(rest[n]);
      const r = rot[n];
      if (r) b.quaternion.multiply(_q.setFromEuler(new THREE.Euler(r[0], r[1], r[2])));
    }
    root.updateMatrixWorld(true);
    if (pose.ik) {
      for (const [side, spec] of Object.entries(pose.ik)) {
        const t = spec.target(this.body);
        let T;
        if (spec.frame) {
          // cible définie au repos, puis emmenée par l'os (le bassin) dans la pose
          const o = this.body.restJ[spec.frame];
          T = bones[spec.frame].localToWorld(new THREE.Vector3(t[0] - o.x, t[1] - o.y, t[2] - o.z));
        } else T = root.localToWorld(new THREE.Vector3(...t));
        const pole = new THREE.Vector3(...spec.pole).applyQuaternion(root.getWorldQuaternion(new THREE.Quaternion()));
        solveTwoBone(bones[`${side}Arm`], bones[`${side}ForeArm`], bones[`${side}Hand`], T, pole);
      }
    }
    // Les mains ne traversent jamais la tenue : si un point de la main ou de
    // l'avant-bras est dans la jupe, le bras s'écarte jusqu'à en sortir.
    if (this.outfit?.skirt) this.clearArms();
    const out = Object.fromEntries(Object.entries(bones).map(([n, b]) => [n, b.quaternion.clone()]));
    for (const [n, b] of Object.entries(bones)) b.quaternion.copy(saved[n]);
    root.updateMatrixWorld(true);
    return out;
  }

  clearArms() {
    const { bones, root } = this.body;
    const s = root.scale.x;
    const fwd = new THREE.Vector3(), p = new THREE.Vector3(), q = new THREE.Quaternion(), wq = new THREE.Quaternion();
    for (const side of ['Left', 'Right']) {
      const arm = bones[`${side}Arm`], fore = bones[`${side}ForeArm`], hand = bones[`${side}Hand`];
      const sign = side === 'Left' ? 1 : -1;
      for (let it = 0; it < 24; it++) {
        root.updateMatrixWorld(true);
        let worst = -1;
        const pts = [fore.getWorldPosition(new THREE.Vector3()).lerp(hand.getWorldPosition(new THREE.Vector3()), 0.6), hand.getWorldPosition(new THREE.Vector3())];
        hand.getWorldQuaternion(wq);
        for (const d of [0.07, 0.13, 0.18]) pts.push(hand.getWorldPosition(new THREE.Vector3()).add(p.set(0, -d * s, 0).applyQuaternion(wq)));
        for (const pt of pts) worst = Math.max(worst, this.outfit.penetration(pt, bones.Hips, s) + 0.02);
        if (worst <= 0) break;
        // abduction autour de l'axe avant du buste
        fwd.set(0, 0, 1).applyQuaternion(bones.Spine.getWorldQuaternion(q));
        const step = Math.min(0.08, 0.02 + worst * 1.2) * sign;
        arm.getWorldQuaternion(wq);
        wq.premultiply(q.setFromAxisAngle(fwd, step));
        setWorldQuat(arm, wq);
      }
    }
  }

  setPose(id, duration = 1.0) {
    const pose = POSES.find((p) => p.id === id);
    if (!pose || !this.body) return;
    this.stopClip();
    this.poseId = id;
    this.pose = pose;
    const from = Object.fromEntries(Object.entries(this.basePose).map(([n, q]) => [n, q.clone()]));
    const to = this.computePose(id);
    this.stoolTarget = pose.stool ? 1 : 0;
    if (duration <= 0) {
      this.basePose = to;
      this.anim = null;
      this.stoolT = this.stoolTarget;
      this.applyBones(0);
      this.ground();
      this.outfit?.reset();
      return;
    }
    this.anim = { from, to, t: 0, d: duration };
  }

  /**
   * Affiche une pose d'un coup (sans transition). Avec une robe dont le tombé a
   * été pré-calculé pour cette taille et cette pose, on charge ce tombé et la
   * pose exacte du corps ; sinon la robe est animée en direct.
   * Renvoie une promesse résolue quand tout est en place.
   */
  async showPose(id) {
    const pose = POSES.find((p) => p.id === id);
    if (!pose || !this.body) return;
    const token = (this.showToken = (this.showToken || 0) + 1);
    const o = this.outfit;
    const useBake = this.bakes && o?.mesh && hasBake(o.mesh, this.sizeId, id);
    const bake = useBake ? await loadBake(o.mesh, this.sizeId, id) : null;
    if (token !== this.showToken || o !== this.outfit) return; // une autre pose a été demandée entre-temps
    this.poseId = id;
    this.pose = pose;
    this.anim = null;
    this.stoolTarget = this.stoolT = pose.stool ? 1 : 0;
    this.stopClip();
    const clip = pose.clip && this.clipFrames(pose.clip);
    if (clip) {
      // Animation du modèle (défilé), en boucle ; robe au tombé animé pré-calculé
      // s'il existe (sinon animée en direct).
      this.clip = clip;
      this.clipT = 0;
      this.clipBake = bake?.meta.frames ? bake : null;
      this.spinOn = false;
      this.spinSpeed = 0;
      // parcours : 4 pas doubles vers l'avant, en passant par le centre (la caméra suit)
      const yaw = this.body.root.rotation.y, fx = Math.sin(yaw), fz = Math.cos(yaw);
      const D = 4 * clip.total * this.body.scale;
      this.walk = { x0: -fx * D * 0.45, z0: -fz * D * 0.45, fx, fz, D, fading: false };
      this.walkY = 0; // sur le sol (la plaque d'acier est retirée)
      this.applyClip(0);
      this.basePose = Object.fromEntries(Object.entries(this.body.bones).map(([n, b]) => [n, b.quaternion.clone()]));
      this.walkTo(0);
      this.onClipStart?.();
      this.body.root.updateMatrixWorld(true);
      if (this.clipBake) o.showBakedFrame(bake.pos, bake.meta.frames, 0);
      else if (o) o.showLive?.();
      return;
    }
    if (bake) {
      const q = bake.meta.quats;
      this.basePose = Object.fromEntries(Object.entries(this.body.bones).map(([n]) => [n, new THREE.Quaternion().fromArray(q[n])]));
    } else this.basePose = this.computePose(id);
    this.applyBones(0);
    this.ground();
    if (bake) o.showBaked(bake.pos);
    else if (o) o.showLive?.();
  }

  // ---------- Animation du modèle (défilé) ----------
  /** Rotations locales des os, image par image, pour le corps courant (mises en cache). */
  clipFrames(name) {
    const body = this.body, raw = body?.clips?.[name];
    if (!raw) return null;
    body.clipCache ||= {};
    if (body.clipCache[name]) return body.clipCache[name];
    const order = Object.keys(body.bones); // parents d'abord
    const parent = Object.fromEntries(order.map((n) => [n, body.bones[n].parent?.isBone ? body.bones[n].parent.name : null]));
    const frames = raw.frames.map((fr) => {
      const W = {}, L = {};
      for (const n of order) {
        W[n] = new THREE.Quaternion().fromArray(fr.q[n]).multiply(body.bindQ[n]);
        L[n] = parent[n] ? W[parent[n]].clone().invert().multiply(W[n]) : W[n].clone();
      }
      return { L, h: new THREE.Vector3(...fr.h) };
    });
    const clip = { name, fps: raw.fps, frames, speed: raw.speed, ground: 0, low: [], adv: [0], total: 0 };
    // Pieds posés : à chaque image, le pied le plus bas touche le sol (hauteur
    // du corps image par image) ; le corps avance de ce que recule le pied
    // d'appui (pas de glissement). Repère du mannequin, avant mise à l'échelle.
    const saved = this.clip, v = new THREE.Vector3(), ids = body.soleIds, rest = body.restPos;
    this.clip = clip;
    const soles = frames.map((_, i) => {
      this.applyClip(i / clip.fps);
      body.root.updateMatrixWorld(true);
      body.body.skeleton.update();
      const out = { Left: [Infinity, 0], Right: [Infinity, 0] };
      for (const id of ids) {
        body.body.getVertexPosition(id, v);
        const side = rest[id * 3] > 0 ? 'Left' : 'Right';
        if (v.y < out[side][0]) out[side] = [v.y, v.z];
      }
      return out;
    });
    const N = frames.length;
    for (let i = 0; i < N; i++) {
      const a = soles[i], b = soles[(i + 1) % N];
      const side = a.Left[0] < a.Right[0] ? 'Left' : 'Right';
      clip.low.push(Math.min(a.Left[0], a.Right[0]));
      const step = Math.max(0, a[side][1] - b[side][1]); // le pied d'appui recule : le corps avance
      clip.total += step;
      if (i < N - 1) clip.adv.push(clip.total);
    }
    clip.ground = Math.min(...clip.low);
    this.clip = saved;
    body.clipCache[name] = clip;
    return clip;
  }

  /** Pose du corps au temps t (s) de l'animation en cours ; renvoie l'image (fractionnaire). */
  applyClip(t) {
    const c = this.clip, N = c.frames.length;
    const f = (((t * c.fps) % N) + N) % N, i0 = Math.floor(f), i1 = (i0 + 1) % N, a = f - i0;
    const A = c.frames[i0], B = c.frames[i1];
    for (const [n, b] of Object.entries(this.body.bones)) b.quaternion.slerpQuaternions(A.L[n], B.L[n], a);
    this.body.bones.Hips.position.copy(this.body.lm.joints.Hips).add(_v1.lerpVectors(A.h, B.h, a));
    return f;
  }

  /** Défilé : position du corps au temps de l'animation (il avance, pieds posés). */
  walkTo(f) {
    const c = this.clip, N = c.frames.length, root = this.body.root, s = this.body.scale;
    const i0 = Math.floor(f), a = f - i0, i1 = (i0 + 1) % N;
    const lerp = (arr) => arr[i0] + ((i1 ? arr[i1] : (i0 === N - 1 ? c.total : arr[0])) - arr[i0]) * a;
    const cyc = Math.floor((this.clipT * c.fps) / N);
    const d = (cyc * c.total + (i1 === 0 ? c.adv[i0] + (c.total - c.adv[i0]) * a : lerp(c.adv))) * s;
    const w = this.walk;
    if (d > w.D) { // fin du parcours : on repart du début (sous un fondu)
      this.clipT = 0;
      w.fading = false;
      this.onClipWrap?.();
      return this.walkTo(this.applyClip(0));
    }
    if (!w.fading && d > w.D - 0.45 * c.speed * s) { w.fading = true; this.onClipFadeOut?.(); }
    root.position.x = w.x0 + w.fx * d;
    root.position.z = w.z0 + w.fz * d;
    root.position.y = this.walkY - (c.low[i0] + (c.low[i1] - c.low[i0]) * a) * s;
  }

  stopClip() {
    if (!this.clip) return;
    this.clip = null;
    this.clipBake = null;
    if (this.body) {
      this.body.bones.Hips.position.copy(this.body.lm.joints.Hips);
      this.body.root.position.x = this.body.root.position.z = 0;
    }
    this.onClipStop?.();
  }

  /** Pose de base × mouvement au repos → os. */
  applyBones(dt = 0) {
    const { bones } = this.body;
    const idle = this.idleOffsets();
    for (const [n, b] of Object.entries(bones)) {
      _qt.copy(this.basePose[n]);
      const o = idle[n];
      if (o) _qt.multiply(_q.setFromEuler(_e.set(o[0], o[1], o[2])));
      // Chaque os suit sa cible avec sa propre inertie : pas d'à-coups, même si
      // l'on change de pose en plein mouvement.
      if (dt > 0) b.quaternion.slerp(_qt, 1 - Math.exp(-dt * (FOLLOW[n] ?? 12)));
      else b.quaternion.copy(_qt);
    }
  }

  /** Mouvement au repos : seul le regard se promène (le corps reste immobile : la robe est figée). */
  idleOffsets() {
    const a = this.idleAmt;
    if (a < 0.001) return {};
    const lk = this.look, t = this.time;
    return {
      Neck: [0, 0.35 * lk * a, 0],
      Head: [0.02 * Math.sin(t * 0.41) * a, 0.6 * lk * a, -0.06 * lk * a],
    };
  }

  setIdle(on) { this.idleOn = on; }
  setSpin(on) { this.spinOn = on; }

  // ---------- Tenue ----------
  outfitsFor(presetId = this.presetId) { return OUTFITS[presetId] || []; }

  /** Change de tenue ; appeler ensuite showPose() pour l'afficher dans la pose. */
  setOutfit(id) {
    this.outfitId = id;
    this.buildOutfit();
  }

  buildOutfit() {
    this.outfit?.dispose();
    this.outfit = null;
    if (this.body) this.body.garmentHalfWidthAt = null;
    const spec = this.outfitsFor().find((o) => o.id === this.outfitId);
    if (!spec || spec.id === 'aucune' || !this.body) return;
    this.body.root.updateMatrixWorld(true);
    this.outfit = buildOutfit(this.body, spec, this.fabric, this.stage);
    this.body.garmentHalfWidthAt = (y) => this.outfit?.halfWidthAt(y) ?? 0;
  }

  setFabric(texture, scale) {
    if (texture !== undefined) { this.fabric.uMap.value = texture; this.fabric.uHasMap.value = texture ? 1 : 0; }
    if (scale !== undefined) this.fabric.uScale.value = scale;
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
    this.time += dt;
    // Regard : change de direction toutes les quelques secondes.
    this.nextLook -= dt;
    if (this.nextLook <= 0) {
      const r = Math.random();
      this.lookTarget = r < 0.3 ? 0 : (r < 0.65 ? -1 : 1) * (0.25 + Math.random() * 0.35);
      this.nextLook = 2.5 + Math.random() * 3.5;
    }
    this.look += (this.lookTarget - this.look) * (1 - Math.exp(-dt * 1.8));
    this.idleAmt += ((this.idleOn ? 1 : 0) - this.idleAmt) * (1 - Math.exp(-dt * 2.5));
    if (this.clip) {
      // Défilé : l'animation pilote les os ; le tissu suit son tombé animé.
      this.clipT += dt;
      const f = this.applyClip(this.clipT);
      this.walkTo(f);
      this.stool.visible = false;
      this.body.root.updateMatrixWorld(true);
      if (this.outfit) {
        if (this.clipBake) {
          const b = this.clipBake;
          this.outfit.showBakedFrame(b.pos, b.meta.frames, (f / this.clip.frames.length) * b.meta.frames);
        } else this.outfit.update(dt, { floorY: this.groundY, box: null, seated: false, spin: this.spinSpeed });
      }
      this.updateContact();
      this.updateTapes(dt);
      return;
    }
    if (this.anim) {
      // Chaîne de mouvement : le bassin et les jambes partent, le buste suit,
      // puis la tête et les bras, légèrement en retard (mouvement plus naturel).
      const a = this.anim;
      a.t += dt;
      let done = true;
      for (const n of Object.keys(this.basePose)) {
        const lag = LAG[n] ?? 0;
        const u = Math.min(1, Math.max(0, (a.t - lag) / a.d));
        if (u < 1) done = false;
        this.basePose[n].slerpQuaternions(a.from[n], a.to[n], ease(u));
      }
      if (done) this.anim = null;
    }
    // Rotation du mannequin sur son socle (la jupe s'évase sous l'effet).
    this.spinSpeed += ((this.spinOn ? 0.9 : 0) - this.spinSpeed) * (1 - Math.exp(-dt * 1.5));
    if (Math.abs(this.spinSpeed) > 1e-4) this.body.root.rotation.y += this.spinSpeed * dt;
    this.applyBones(dt);
    this.ground();
    // Socle cubique : sort du sol sous le bassin dans la pose assise.
    const st = this.stoolTarget ?? 0;
    this.stoolT += Math.sign(st - this.stoolT) * Math.min(Math.abs(st - this.stoolT), dt * 2.2);
    if (this.stoolT > 0.001) {
      const pelvisBottom = this.body.lowestSeat();
      // avec une tenue, le tissu passe entre le corps et le socle (1,2 cm)
      const top = Math.max(0.05, pelvisBottom + (this.outfit ? -0.012 : 0.01) * this.body.scale);
      this.stool.visible = true;
      this.stool.scale.set(1, Math.max(0.001, top * ease(this.stoolT)), 1);
      const hp = this.body.bones.Hips.getWorldPosition(_v1);
      this.stool.position.set(hp.x, 0, hp.z - 0.06 * this.body.scale);
    } else this.stool.visible = false;
    // Tenue : le tissu simulé suit le corps.
    if (this.outfit) {
      const st = this.stool;
      const box = st.visible && this.stoolT > 0.5 ? {
        x0: st.position.x - 0.22, x1: st.position.x + 0.22, z0: st.position.z - 0.22, z1: st.position.z + 0.22, top: st.scale.y,
      } : null;
      this.body.root.updateMatrixWorld(true);
      this.outfit.update(dt, { floorY: this.groundY, box, seated: !!this.pose?.stool, spin: this.spinSpeed });
    }
    this.body.root.updateMatrixWorld(true);
    this.updateContact();
    this.updateTapes(dt);
  }

  /** Ombres de contact : sous chaque pied, d'autant plus nettes qu'il est près du sol. */
  updateContact() {
    const body = this.body, ids = body.soleIds, rest = body.restPos, v = _v2;
    const floor = this.clip ? this.walkY : this.groundY;
    body.body.skeleton.update();
    const acc = { Left: [Infinity, 0, 0, 0], Right: [Infinity, 0, 0, 0] };
    for (const id of ids) {
      body.body.getVertexPosition(id, v);
      v.applyMatrix4(body.body.matrixWorld);
      const a = acc[rest[id * 3] > 0 ? 'Left' : 'Right'];
      a[0] = Math.min(a[0], v.y); a[1] += v.x; a[2] += v.z; a[3]++;
    }
    ['Left', 'Right'].forEach((side, k) => {
      const a = acc[side], m = this.contact[k];
      if (!a[3] || this.stoolT > 0.5) { m.visible = false; return; }
      const h = Math.max(0, a[0] - floor);
      m.visible = true;
      m.position.set(a[1] / a[3], floor + 0.0015, a[2] / a[3]);
      m.rotation.y = body.root.rotation.y;
      m.scale.setScalar(body.scale * (1 + h * 4));
      m.material.opacity = 0.65 * Math.max(0, 1 - h / 0.07);
    });
  }

  updateTapes(dt) {
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

/** Ombre de contact : tache douce elliptique posée au sol. */
function makeContactShadow() {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(0.45, 'rgba(0,0,0,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0)');
  x.fillStyle = g; x.fillRect(0, 0, 64, 64);
  const geo = new THREE.PlaneGeometry(0.11, 0.26);
  geo.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, opacity: 0.5 }));
  m.renderOrder = 1;
  m.visible = false;
  return m;
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
