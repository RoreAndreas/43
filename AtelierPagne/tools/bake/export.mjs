#!/usr/bin/env node
// Étape 1 du pré-calcul des robes : pour chaque taille et chaque pose, la salle
// d'essayage (dans un navigateur sans écran) exporte le corps du mannequin au
// repos et dans la pose, la robe ajustée au repos, sa position de départ dans
// la pose et l'emplacement du socle. Blender simule ensuite le tissu
// (tools/bake/simulate.py).
//
// Usage : node tools/bake/export.mjs <robe> <dossier de sortie> [tailles] [poses]
//   ex. : node tools/bake/export.mjs aveline /tmp/bake 38 assise,neutre
// Nécessite Playwright (npm i -D playwright ; npx playwright install chromium).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { SIZES } from '../../js/essayage/sizes.js';

const { chromium } = createRequire(import.meta.url)('playwright');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const [dress = 'aveline', out = 'bake-export', sizesArg, posesArg] = process.argv.slice(2);
const sizes = sizesArg ? sizesArg.split(',') : SIZES.femme.map((s) => s.id);
const POSES = ['neutre', 'hanchement', 'mains-hanches', 'bras-ouverts', 'defile', 'photo', 'assise'];
const poses = posesArg ? posesArg.split(',') : POSES;
fs.mkdirSync(out, { recursive: true });

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.bin': 'application/octet-stream' };
const server = http.createServer((req, res) => {
  const file = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 320, height: 240 } });
page.on('pageerror', (e) => console.error('erreur page :', e.message));
await page.addInitScript(() => localStorage.setItem('atelier-pagne:guide-vu', 'true'));
await page.goto(`http://localhost:${port}/essayage.html?bake=1`, { timeout: 120000 });
await page.waitForFunction(() => document.body.classList.contains('is-ready'), null, { timeout: 120000 });

for (const sizeId of sizes) {
  for (const poseId of poses) {
    const size = SIZES.femme.find((s) => s.id === sizeId);
    const data = await page.evaluate(([size, poseId, dress]) => {
      const e = window.__essayage, rig = e.rig;
      e.skipIntro();
      rig.setIdle(false); rig.idleAmt = 0; rig.setSpin(false); rig.spinSpeed = 0;
      const H = rig.base('femme').cm.height;
      rig.outfitId = dress;
      rig.setPose('neutre', 0);
      rig.setBody('femme', { height: H, bust: size.bust, waist: size.waist, hip: size.hip });
      const body = rig.body, root = body.root, cloth = rig.outfit.skirt;
      root.rotation.y = 0;
      const V = root.position.constructor;
      const v = new V();
      const meshPos = (mesh) => {
        mesh.updateMatrixWorld(true);
        const n = mesh.geometry.attributes.position.count, a = new Array(n * 3);
        for (let i = 0; i < n; i++) {
          mesh.getVertexPosition(i, v); v.applyMatrix4(mesh.matrixWorld);
          a[i * 3] = +v.x.toFixed(5); a[i * 3 + 1] = +v.y.toFixed(5); a[i * 3 + 2] = +v.z.toFixed(5);
        }
        return a;
      };
      const particles = (renderPos) => {
        const n = cloth.P.length / 3, a = new Array(n * 3).fill(0);
        for (let r = 0; r < cloth.rv.length; r++) { const p = cloth.rv[r]; for (let c = 0; c < 3; c++) a[p * 3 + c] = renderPos[r * 3 + c]; }
        return a;
      };
      // 1) corps et robe au repos
      for (const [n, b] of Object.entries(body.bones)) b.quaternion.copy(body.rest[n]);
      rig.ground();
      root.updateMatrixWorld(true);
      const rest = { rootY: root.position.y, body: meshPos(body.body) };
      const s = root.scale.x;
      rest.dress = Array.from(cloth.P, (x, i) => +(i % 3 === 1 ? x * s + root.position.y : x * s).toFixed(5));
      // 2) le mouvement réel, du repos à la pose, échantillonné tous les 0,1 s.
      //    Pour s'asseoir, les pieds restent posés : le mannequin part debout
      //    devant le socle et recule en s'asseyant, comme une vraie personne.
      const frames = [];
      rig.basePose = Object.fromEntries(Object.entries(body.rest).map(([n, q]) => [n, q.clone()]));
      // Les bras partent déjà hors de la jupe (comme dans la pose Debout) : au repos
      // strict, les mains pendent contre les hanches, dans le tissu, et
      // l'entraîneraient en sortant (fente qui s'ouvre, pans retroussés).
      const armsOut = rig.computePose('neutre');
      for (const n of ['LeftArm', 'LeftForeArm', 'LeftHand', 'RightArm', 'RightForeArm', 'RightHand']) rig.basePose[n] = armsOut[n].clone();
      rig.applyBones(0);
      rig.ground();
      cloth.reset(); // la jupe repart de sa forme de repos
      rig.stoolT = 0;
      rig.setPose(poseId, 1.0);
      const st = rig.stool;
      const feet = () => {
        const a = body.bones.LeftFoot.getWorldPosition(new V()), b = body.bones.RightFoot.getWorldPosition(new V());
        return [(a.x + b.x) / 2, (a.z + b.z) / 2];
      };
      const snap = () => {
        root.rotation.y = 0;
        root.updateMatrixWorld(true);
        cloth.mesh.skeleton.update();
        frames.push({ body: meshPos(body.body), dress: particles(meshPos(cloth.mesh)), feet: feet() });
      };
      snap();
      // Jambes amincies (30 % autour de l'axe des os), au repos : au début de la
      // simulation elles reprennent leur volume et poussent le tissu du bon côté.
      const thin = frames[0].body.slice();
      {
        const geo = body.body.geometry, SI = geo.attributes.skinIndex, SW = geo.attributes.skinWeight;
        const bi = body.bi, segs = { [bi.LeftUpLeg]: ['LeftUpLeg', 'LeftLeg'], [bi.LeftLeg]: ['LeftLeg', 'LeftFoot'], [bi.RightUpLeg]: ['RightUpLeg', 'RightLeg'], [bi.RightLeg]: ['RightLeg', 'RightFoot'] };
        const P = (name) => body.bones[name].getWorldPosition(new V());
        for (let i = 0; i < SI.count; i++) {
          let best = -1, bw = 0;
          for (let c = 0; c < 4; c++) { const b2 = SI.getComponent(i, c), w = SW.getComponent(i, c); if (segs[b2] && w > bw) { bw = w; best = b2; } }
          if (best < 0 || bw < 0.5) continue;
          const [a, b2] = segs[best].map(P);
          const p = new V(thin[i * 3], thin[i * 3 + 1], thin[i * 3 + 2]);
          const ab = b2.clone().sub(a), t = Math.max(0, Math.min(1, p.clone().sub(a).dot(ab) / ab.lengthSq()));
          const c = a.clone().addScaledVector(ab, t);
          const q = c.addScaledVector(p.clone().sub(c), 0.3);
          thin[i * 3] = +q.x.toFixed(5); thin[i * 3 + 1] = +q.y.toFixed(5); thin[i * 3 + 2] = +q.z.toFixed(5);
        }
      }
      for (let f = 1; f < 18; f++) { for (let i = 0; i < 6; i++) rig.update(1 / 60); snap(); }
      for (let i = 0; i < 150; i++) rig.update(1 / 60);
      snap();
      const last = frames[frames.length - 1];
      const planted = rig.pose?.stool;
      if (planted) {
        for (const f of frames) {
          const dx = last.feet[0] - f.feet[0], dz = last.feet[1] - f.feet[1];
          const arrs = f === frames[0] ? [f.body, f.dress, thin] : [f.body, f.dress];
          for (const arr of arrs) for (let i = 0; i < arr.length; i += 3) { arr[i] = +(arr[i] + dx).toFixed(5); arr[i + 2] = +(arr[i + 2] + dz).toFixed(5); }
        }
      }
      for (const f of frames) delete f.feet;
      const pose = {
        rootY: root.position.y, scale: s, body: last.body, dress: last.dress, frames, thin,
        quats: Object.fromEntries(Object.entries(body.bones).map(([n, b]) => [n, b.quaternion.toArray().map((x) => +x.toFixed(6))])),
      };
      const stool = st.visible && rig.stoolT > 0.5 ? { x: st.position.x, z: st.position.z, half: 0.22, top: st.scale.y } : null;
      // points tenus par le corps (bustier, bandeau) : au-dessus de la taille basse ;
      // sous les hanches le tissu est libre (il passe sur les fesses, les cuisses)
      const hip = body.lm.hip, ss = (x, a, b) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
      const pin = [];
      const waist = body.lm.waist;
      for (let i = 0; i < cloth.P.length / 3; i++) pin.push(+ss(cloth.P[i * 3 + 1], hip + 0.01, (hip + waist) / 2 + 0.01).toFixed(3));
      const tris = [];
      for (let t = 0; t < cloth.tris.length; t += 3) {
        const a = cloth.rv[cloth.tris[t]], b = cloth.rv[cloth.tris[t + 1]], c = cloth.rv[cloth.tris[t + 2]];
        if (a !== b && b !== c && a !== c) tris.push(a, b, c);
      }
      return {
        size, pose: poseId, rest, target: pose, stool, pin, tris,
        bodyIndex: Array.from(body.body.geometry.index.array), floorY: rig.groundY,
      };
    }, [size, poseId, dress]);
    const file = path.join(out, `${dress}-${sizeId}-${poseId}.json`);
    fs.writeFileSync(file, JSON.stringify(data));
    console.log('exporté', file);
  }
}
await browser.close();
server.close();
