// Décor de la cabine : salon circulaire tendu de velours, parquet, podium
// incrusté de wax, faisceau de lumière poussiéreux, psyché (miroir sur pied)
// et portant de pagnes.
import * as THREE from 'three';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { PALETTES, waxTile, waxTexture } from './pattern.js';

export const FLOOR_Y = -0.1;
const BG = 0x171c2c;

export function buildDecor(scene, renderer, { lite = false } = {}) {
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 8, 19);
  const group = new THREE.Group();
  scene.add(group);

  // ---------- Lumières ----------
  scene.add(new THREE.HemisphereLight(0xfff4e6, 0x2a2230, 0.42));
  const spot = new THREE.SpotLight(0xfff0dc, 3.4, 0, 0.36, 0.6, 0);
  spot.position.set(0.9, 5.8, 2.6);
  spot.target.position.set(0, 0.85, 0);
  spot.castShadow = true;
  spot.shadow.mapSize.set(lite ? 1024 : 2048, lite ? 1024 : 2048);
  spot.shadow.camera.near = 2;
  spot.shadow.camera.far = 12;
  spot.shadow.bias = -0.0002;
  spot.shadow.normalBias = 0.025;
  spot.shadow.radius = 6;
  scene.add(spot, spot.target);
  const rim = new THREE.DirectionalLight(0xc6d4ff, 1.25);
  rim.position.set(-1.2, 3.2, -4);
  scene.add(rim);
  const fill = new THREE.DirectionalLight(0xffd9b0, 0.45);
  fill.position.set(-3.5, 1.8, 2);
  scene.add(fill);
  // Lumières d'ambiance qui caressent le velours.
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2 + 0.9;
    const p = new THREE.PointLight(0xffc98f, 0.7, 8, 0);
    p.position.set(Math.cos(a) * 6.2, 3.6, Math.sin(a) * 6.2);
    group.add(p);
  }

  // ---------- Parquet ----------
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(10, 96),
    new THREE.MeshStandardMaterial({ map: parquetTexture(), roughness: 0.55, metalness: 0 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = FLOOR_Y;
  floor.receiveShadow = true;
  group.add(floor);

  // ---------- Rideaux de velours tout autour ----------
  const curtain = new THREE.Mesh(curtainRing(8.6, 7, 120), new THREE.MeshPhysicalMaterial({
    color: 0x2a3866, roughness: 0.9, sheen: 1, sheenRoughness: 0.42, sheenColor: new THREE.Color(0x8ea2e0), side: THREE.DoubleSide,
  }));
  curtain.position.y = FLOOR_Y + 3.5;
  group.add(curtain);

  // ---------- Podium ----------
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(1.12, 1.15, 0.035, 128),
    new THREE.MeshStandardMaterial({ color: 0xb8893f, metalness: 0.85, roughness: 0.32 }),
  );
  base.position.y = FLOOR_Y + 0.0175;
  base.receiveShadow = true;
  const top = new THREE.Mesh(
    new THREE.CylinderGeometry(1.0, 1.02, 0.065, 128),
    [
      new THREE.MeshPhysicalMaterial({ color: 0x1f2a44, roughness: 0.35, clearcoat: 0.6, clearcoatRoughness: 0.25 }),
      new THREE.MeshStandardMaterial({ map: podiumTexture(), roughness: 0.6 }),
      new THREE.MeshStandardMaterial({ color: 0x1f2a44 }),
    ],
  );
  top.position.y = -0.0325;
  top.receiveShadow = true;
  top.castShadow = true;
  group.add(base, top);

  const STITCHES = 150;
  const stitchGeo = new THREE.CapsuleGeometry(0.0045, 0.02, 3, 8);
  stitchGeo.rotateZ(Math.PI / 2);
  const stitches = new THREE.InstancedMesh(stitchGeo, new THREE.MeshStandardMaterial({ color: 0xe0a33a, roughness: 0.5 }), STITCHES);
  {
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(1, 0.35, 1);
    for (let i = 0; i < STITCHES; i++) {
      const a = (i / STITCHES) * Math.PI * 2;
      p.set(Math.cos(a) * 0.815, 0.001, Math.sin(a) * 0.815);
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a + Math.PI / 2);
      stitches.setMatrixAt(i, m.compose(p, q, s));
    }
  }
  stitches.count = 0;
  stitches.frustumCulled = false;
  group.add(stitches);

  // ---------- Faisceau lumineux + poussière ----------
  const from = spot.position.clone();
  const to = new THREE.Vector3(0, FLOOR_Y, 0.15);
  const len = from.distanceTo(to);
  const beam = new THREE.Mesh(
    new THREE.ConeGeometry(1.45, len, 64, 1, true),
    new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false,
      uniforms: { uColor: { value: new THREE.Color(0xffe2b8) }, uStrength: { value: 0.16 } },
      vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
        void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position,1.0);
        vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform vec3 uColor; uniform float uStrength; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
        void main(){ float f = abs(dot(vN, vV)); f = f*f;
        float h = smoothstep(0.0, 0.45, vUv.y) * (1.0 - smoothstep(0.9, 1.0, vUv.y));
        gl_FragColor = vec4(uColor * f * h * uStrength, 1.0); }`,
    }),
  );
  beam.position.copy(from).add(to).multiplyScalar(0.5);
  beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), from.clone().sub(to).normalize());
  beam.renderOrder = 10;
  group.add(beam);

  const N = lite ? 140 : 320;
  const dustPos = new Float32Array(N * 3);
  const dust = [];
  const axis = to.clone().sub(from).normalize();
  const side1 = new THREE.Vector3().crossVectors(axis, new THREE.Vector3(1, 0, 0)).normalize();
  const side2 = new THREE.Vector3().crossVectors(axis, side1).normalize();
  for (let i = 0; i < N; i++) {
    dust.push({ t: 0.2 + Math.random() * 0.75, a: Math.random() * Math.PI * 2, r: Math.sqrt(Math.random()), sp: 0.004 + Math.random() * 0.01, ph: Math.random() * 10 });
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3));
  const dustPts = new THREE.Points(dustGeo, new THREE.PointsMaterial({
    size: 0.016, map: dotTexture(), transparent: true, opacity: 0.7, depthWrite: false, blending: THREE.AdditiveBlending, color: 0xffe9c9,
  }));
  dustPts.frustumCulled = false;
  group.add(dustPts);
  const placeDust = (time) => {
    const p = new THREE.Vector3();
    dust.forEach((d, i) => {
      const along = from.clone().addScaledVector(axis, d.t * len);
      const rad = 1.45 * d.t * d.r * 0.92;
      const a = d.a + Math.sin(time * 0.2 + d.ph) * 0.3;
      p.copy(along).addScaledVector(side1, Math.cos(a) * rad).addScaledVector(side2, Math.sin(a) * rad);
      p.y += Math.sin(time * 0.5 + d.ph) * 0.03;
      dustPos.set([p.x, p.y, p.z], i * 3);
    });
    dustGeo.attributes.position.needsUpdate = true;
  };

  // ---------- Psyché : le miroir montre le dos du mannequin ----------
  const psyche = new THREE.Group();
  const shape = new THREE.Shape();
  shape.absellipse(0, 0, 0.42, 0.86, 0, Math.PI * 2, false, 0);
  const res = lite ? 512 : 1024;
  const mirror = new Reflector(new THREE.ShapeGeometry(shape, 64), {
    textureWidth: res, textureHeight: Math.round(res * 2), color: 0xb7bcc4, clipBias: 0.003,
  });
  const brass = new THREE.MeshStandardMaterial({ color: 0xc19446, metalness: 0.9, roughness: 0.28 });
  const ell = new THREE.EllipseCurve(0, 0, 0.44, 0.88, 0, Math.PI * 2);
  const frame = new THREE.Mesh(
    new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ell.getPoints(96).map((p) => new THREE.Vector3(p.x, p.y, 0.005)), true), 160, 0.026, 12, true),
    brass,
  );
  const back = new THREE.Mesh(new THREE.ShapeGeometry(shape, 64), new THREE.MeshStandardMaterial({ color: 0x3b2a1e, roughness: 0.7 }));
  back.scale.setScalar(1.04);
  back.position.z = -0.012;
  back.rotation.y = Math.PI;
  const glassGroup = new THREE.Group();
  glassGroup.add(mirror, frame, back);
  glassGroup.position.y = 1.08;
  glassGroup.rotation.x = -0.04;
  psyche.add(glassGroup);
  for (const sx of [-1, 1]) {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.02, 1.62, 16), brass);
    post.position.set(sx * 0.5, 0.81, -0.04);
    const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.5, 12), brass);
    foot.rotation.x = Math.PI / 2;
    foot.position.set(sx * 0.5, 0.015, -0.04);
    const knob = new THREE.Mesh(new THREE.SphereGeometry(0.032, 16, 12), brass);
    knob.position.set(sx * 0.5, 1.64, -0.04);
    const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.08, 12), brass);
    pin.rotation.z = Math.PI / 2;
    pin.position.set(sx * 0.465, 1.08, -0.02);
    psyche.add(post, foot, knob, pin);
  }
  psyche.traverse((o) => { if (o.isMesh && o !== mirror) { o.castShadow = true; o.receiveShadow = true; } });
  psyche.position.set(-1.5, FLOOR_Y, -2.15);
  psyche.rotation.y = 0.45;
  group.add(psyche);

  // ---------- Portant de pagnes ----------
  const rack = new THREE.Group();
  for (const sx of [-1, 1]) {
    const up = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 1.78, 12), brass);
    up.position.set(sx * 0.82, 0.89, 0);
    const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.013, 0.013, 0.46, 12), brass);
    foot.rotation.x = Math.PI / 2;
    foot.position.set(sx * 0.82, 0.015, 0);
    rack.add(up, foot);
  }
  const rail = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, 1.72, 12), brass);
  rail.rotation.z = Math.PI / 2;
  rail.position.y = 1.76;
  rack.add(rail);
  [PALETTES[1], PALETTES[2], PALETTES[3], PALETTES[4]].forEach((pal, i) => {
    const cloth = new THREE.Mesh(hangingCloth(0.5, 1.42, i), new THREE.MeshStandardMaterial({
      map: waxTexture(pal, [1.4, 4]), roughness: 0.82, side: THREE.DoubleSide,
    }));
    cloth.position.set(-0.56 + i * 0.37, 1.76, (i % 2) * 0.05 - 0.02);
    cloth.rotation.y = (i % 2 ? -0.18 : 0.14);
    cloth.castShadow = true;
    cloth.receiveShadow = true;
    rack.add(cloth);
  });
  rack.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  rack.position.set(1.75, FLOOR_Y, -2.35);
  rack.rotation.y = -0.42;
  group.add(rack);

  // ---------- Animation ----------
  let time = 0;
  let intro = 0;
  placeDust(0);
  return {
    stitches,
    spot,
    update(dt) {
      time += dt;
      if (intro < 1) {
        intro = Math.min(1, intro + dt / 1.8);
        stitches.count = Math.floor(STITCHES * intro);
        beam.material.uniforms.uStrength.value = 0.16 * intro;
        spot.intensity = 3.4 * (0.25 + 0.75 * intro);
      }
      if (!lite || Math.floor(time * 30) % 2 === 0) placeDust(time);
      dust.forEach((d) => { d.t += d.sp * dt * 0.6; if (d.t > 0.97) d.t = 0.2; });
    },
  };
}

// ---------- Fabrication des textures et géométries ----------
function parquetTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 1024;
  const x = c.getContext('2d');
  const tones = ['#7a4e2f', '#86573a', '#6f4529', '#8e603e', '#7d5032', '#694227'];
  const W = 128;
  let seed = 3;
  const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let col = 0; col < 8; col++) {
    let y = -r() * 400;
    while (y < 1024) {
      const L = 300 + r() * 360;
      x.fillStyle = tones[Math.floor(r() * tones.length)];
      x.fillRect(col * W, y, W, L);
      x.globalAlpha = 0.18;
      for (let g = 0; g < 14; g++) {
        x.strokeStyle = r() > 0.5 ? '#3d2414' : '#b07d55';
        x.lineWidth = 1 + r() * 1.5;
        const gx = col * W + r() * W;
        x.beginPath(); x.moveTo(gx, y);
        x.bezierCurveTo(gx + (r() - 0.5) * 20, y + L * 0.3, gx + (r() - 0.5) * 20, y + L * 0.7, gx + (r() - 0.5) * 10, y + L);
        x.stroke();
      }
      x.globalAlpha = 1;
      x.fillStyle = '#2a170c';
      x.fillRect(col * W, y, W, 3);
      y += L;
    }
    x.fillStyle = '#2a170c';
    x.fillRect(col * W, 0, 3, 1024);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(7, 7);
  t.anisotropy = 8;
  return t;
}

function podiumTexture() {
  const S = 1024;
  const c = document.createElement('canvas');
  c.width = c.height = S;
  const x = c.getContext('2d');
  const R = S / 2;
  const g = x.createRadialGradient(R, R, 0, R, R, R);
  g.addColorStop(0, '#f1eadf');
  g.addColorStop(0.7, '#e6dccb');
  g.addColorStop(1, '#d8cbb6');
  x.fillStyle = g; x.fillRect(0, 0, S, S);
  // Bande de wax incrustée
  const pat = x.createPattern(waxTile(PALETTES[0], 160), 'repeat');
  x.save();
  x.beginPath(); x.arc(R, R, R * 0.985, 0, Math.PI * 2); x.arc(R, R, R * 0.855, 0, Math.PI * 2, true);
  x.fillStyle = pat; x.fill();
  x.restore();
  x.strokeStyle = '#c19446'; x.lineWidth = 6;
  for (const k of [0.855, 0.985]) { x.beginPath(); x.arc(R, R, R * k, 0, Math.PI * 2); x.stroke(); }
  // Rosace centrale discrète
  x.globalAlpha = 0.12; x.strokeStyle = '#1f2a44'; x.lineWidth = 3;
  for (let i = 0; i < 12; i++) {
    x.save(); x.translate(R, R); x.rotate((i / 12) * Math.PI * 2);
    x.beginPath(); x.ellipse(0, -R * 0.2, R * 0.07, R * 0.2, 0, 0, Math.PI * 2); x.stroke();
    x.restore();
  }
  x.globalAlpha = 1;
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function dotTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.35, 'rgba(255,255,255,0.5)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  return t;
}

/** Cylindre de rideau aux plis plus profonds vers le bas. */
function curtainRing(R, H, folds) {
  const geo = new THREE.CylinderGeometry(R, R, H, folds * 6, 10, true);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const a = Math.atan2(z, x);
    const v = (y + H / 2) / H;
    const amp = 0.07 + 0.11 * (1 - v);
    const r = R + amp * Math.sin(a * folds) + 0.035 * Math.sin(a * folds * 2.37 + 1.3) * (1 - v * 0.5);
    p.setXYZ(i, Math.cos(a) * r, y, Math.sin(a) * r);
  }
  geo.computeVertexNormals();
  return geo;
}

/** Pagne suspendu : plis souples, plus marqués en bas. */
function hangingCloth(W, H, seed) {
  const geo = new THREE.PlaneGeometry(W, H, 40, 30);
  geo.translate(0, -H / 2, 0);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i);
    const v = -y / H; // 0 en haut, 1 en bas
    const amp = 0.012 + 0.03 * v;
    const z = amp * Math.sin((x / W) * Math.PI * 5 + seed * 1.7) + 0.01 * Math.sin((x / W) * 17 + seed);
    p.setXYZ(i, x * (1 - 0.06 * v * Math.cos(seed)), y, z);
  }
  geo.computeVertexNormals();
  return geo;
}
