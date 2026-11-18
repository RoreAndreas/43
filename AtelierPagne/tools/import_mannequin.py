#!/usr/bin/env python3
"""Importe un mannequin rigué Mixamo (FBX ou .blend) au format du site.

Sert pour la silhouette femme, à partir du modèle du tutoriel « Cloth
Simulation » (Female_with_Dress.fbx) : un seul maillage fermé en quadrangles,
sans visage, conçu pour la simulation de tissu.

Le script (module Python de Blender, « pip install bpy ») :
1. remet le squelette dans sa position de liaison (sans animation) ;
2. oriente bras, avant-bras, mains et jambes comme le mannequin MakeHuman
   précédent (position de repos commune : les poses de poses.js restent
   valables), paumes tournées vers les cuisses, pieds à plat ;
3. regroupe les os Mixamo sur les 16 os du site (Hips, Spine, LeftArm…) ;
4. met à l'échelle (hauteur totale HEIGHT), pose les pieds au sol ;
5. écrit assets/mannequin/<nom>.bin et <nom>.json, comme build_mannequin.py,
   en gardant la tête du modèle (déjà lisse et sans visage).

Usage :
    python tools/import_mannequin.py -- <modèle.fbx|.blend> [nom=femme]
"""
import json
import math
import pathlib
import sys

import bpy  # noqa: I001
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from build_mannequin import BONES, hull_perimeter  # noqa: E402

OUT = ROOT / 'assets' / 'mannequin'
HEIGHT = 1.81  # m, tête comprise (comme le mannequin précédent)

# Directions des segments au repos (repère du site : y vers le haut, z vers
# l'avant, x vers la gauche du mannequin), relevées sur le mannequin MakeHuman.
AIM_DIRS = {
    'Arm': (0.677, -0.736, 0.029),
    'ForeArm': (0.509, -0.563, 0.651),
    'Hand': (0.426, -0.536, 0.728),
    'UpLeg': (0.086, -0.993, 0.081),
    'Leg': (0.058, -0.996, -0.066),
}
# Os du site → os Mixamo dont on reprend la rotation dans les animations
# (le buste suit le haut du dos : Spine2).
ANIM_MAP = {
    'Hips': 'Hips', 'Spine': 'Spine2', 'Neck': 'Neck', 'Head': 'Head',
    **{s + p: s + p for s in ('Left', 'Right') for p in ('Arm', 'ForeArm', 'Hand', 'UpLeg', 'Leg', 'Foot')},
}
CHILD = {'Arm': 'ForeArm', 'ForeArm': 'Hand', 'Hand': 'HandMiddle1', 'UpLeg': 'Leg', 'Leg': 'Foot', 'Foot': 'ToeBase'}


SMOOTH_ITER = 40


def neighbours(n, faces):
    rows, cols = [], []
    for f in faces:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            rows += [a, b]
            cols += [b, a]
    nb = [set() for _ in range(n)]
    for a, b in zip(rows, cols):
        nb[a].add(b)
    return [np.fromiter(x, int) for x in nb]


def taubin(V, faces, mask, iters, lam=0.5, mu=-0.53):
    nb = neighbours(len(V), faces)
    deg = np.array([len(x) for x in nb])
    flat = np.concatenate(nb)
    owner = np.repeat(np.arange(len(V)), deg)
    V = V.copy()
    for _ in range(iters):
        for k in (lam, mu):
            avg = np.zeros_like(V)
            np.add.at(avg, owner, V[flat])
            avg /= deg[:, None]
            V += (avg - V) * (k * mask)[:, None]
    return V


def smooth_mask(V, Wn, J):
    """1 sur le tronc, 0 sur la tête, les mains, les pieds ; fondu entre les deux."""
    idx = {b: i for i, b in enumerate(BONES)}
    torso = Wn[:, idx['Hips']] + Wn[:, idx['Spine']] + 0.6 * (Wn[:, idx['LeftArm']] + Wn[:, idx['RightArm']])
    legs = Wn[:, idx['LeftUpLeg']] + Wn[:, idx['RightUpLeg']]
    knee = J['LeftLeg'][1]
    fade = np.clip((V[:, 1] - knee) / (J['LeftUpLeg'][1] - knee), 0, 1)
    m = np.clip(torso + legs * fade, 0, 1)
    m *= np.clip((J['Neck'][1] + 0.04 - V[:, 1]) / 0.06, 0, 1)  # pas la tête
    return m


def soften_bands(V, Wn, J, sigma=0.035):
    """Adoucit les « bandes » horizontales du tronc (raccords des sphères).

    En coordonnées cylindriques autour de l'axe du tronc, le rayon moyen r(θ, y)
    est lissé le long de y ; chaque sommet est corrigé du rapport lissé/brut.
    La forme de chaque section est gardée ; la poitrine n'est pas touchée.
    """
    idx = {b: i for i, b in enumerate(BONES)}
    tw = Wn[:, idx['Hips']] + Wn[:, idx['Spine']]
    y0, y1 = J['LeftUpLeg'][1] - 0.06, J['LeftArm'][1] - 0.04
    cz = np.interp(V[:, 1], [J['Hips'][1], J['Spine'][1], J['Neck'][1]], [J['Hips'][2], J['Spine'][2], J['Neck'][2]])
    th = np.arctan2(V[:, 0], V[:, 2] - cz)
    r = np.hypot(V[:, 0], V[:, 2] - cz)
    sel = (tw > 0.5) & (V[:, 1] > y0 - 0.1) & (V[:, 1] < y1 + 0.1)
    NT, dy = 72, 0.01
    ys = np.arange(y0 - 0.1, y1 + 0.1 + dy, dy)
    ti = ((th + np.pi) / (2 * np.pi) * NT).astype(int) % NT
    yi = np.clip(((V[:, 1] - ys[0]) / dy).astype(int), 0, len(ys) - 1)
    S = np.zeros((NT, len(ys))); C = np.zeros((NT, len(ys)))
    np.add.at(S, (ti[sel], yi[sel]), r[sel]); np.add.at(C, (ti[sel], yi[sel]), 1)
    k = np.exp(-0.5 * (np.arange(-12, 13) * dy / sigma) ** 2)
    conv = lambda a: np.apply_along_axis(lambda row: np.convolve(row, k, mode='same'), 1, a)  # noqa: E731
    kt = np.array([0.25, 0.5, 0.25])
    convt = lambda a: sum(w * np.roll(a, o, axis=0) for w, o in zip(kt, (-1, 0, 1)))  # noqa: E731
    raw = convt(S) / np.maximum(convt(C), 1e-9)
    smooth = convt(conv(S)) / np.maximum(convt(conv(C)), 1e-9)
    ok = convt(C) > 0
    ratio = np.where(ok, smooth / np.maximum(raw, 1e-9), 1.0)
    # interpolation bilinéaire (pas de marches entre les cases)
    tf = (th + np.pi) / (2 * np.pi) * NT - 0.5
    yf = np.clip((V[:, 1] - ys[0]) / dy - 0.5, 0, len(ys) - 1.001)
    t0 = np.floor(tf).astype(int); at = tf - t0; t0 %= NT; t1 = (t0 + 1) % NT
    y0i = np.floor(yf).astype(int); ay = yf - y0i; y1i = np.minimum(y0i + 1, len(ys) - 1)
    f = ((ratio[t0, y0i] * (1 - at) + ratio[t1, y0i] * at) * (1 - ay)
         + (ratio[t0, y1i] * (1 - at) + ratio[t1, y1i] * at) * ay)
    # poids : tronc, dans la plage de hauteur ; devant, pas au-dessus de la taille (poitrine)
    w = np.clip(tw, 0, 1) * np.clip((V[:, 1] - y0) / 0.05, 0, 1) * np.clip((y1 - V[:, 1]) / 0.05, 0, 1)
    front = np.clip((np.cos(th) - 0.35) / 0.3, 0, 1) * np.clip((V[:, 1] - (J['Spine'][1] + 0.08)) / 0.06, 0, 1)
    w *= 1 - front
    f = 1 + (f - 1) * w * sel
    out = V.copy()
    out[:, 0] = V[:, 0] * f
    out[:, 2] = cz + (V[:, 2] - cz) * f
    return out, np.clip(w * sel * 3, 0, 1)


def site_bone(name):
    """Os Mixamo → os du site."""
    n = name.split(':')[-1]
    side = 'Left' if n.startswith('Left') else 'Right' if n.startswith('Right') else ''
    part = n[len(side):]
    if n == 'Hips':
        return 'Hips'
    if n.startswith('Spine') or part == 'Shoulder':
        return 'Spine'
    if n == 'Neck':
        return 'Neck'
    if n.startswith('Head'):
        return 'Head'
    if part == 'Arm':
        return side + 'Arm'
    if part == 'ForeArm':
        return side + 'ForeArm'
    if part.startswith('Hand'):
        return side + 'Hand'
    if part == 'UpLeg':
        return side + 'UpLeg'
    if part == 'Leg':
        return side + 'Leg'
    if part.startswith(('Foot', 'Toe')):
        return side + 'Foot'
    return 'Spine'


def to_site(v):
    """Blender (z vers le haut, avant = -y) → site (y vers le haut, avant = +z)."""
    return np.array([v[0], v[2], -v[1]])


def to_blender(v):
    return Vector((v[0], -v[2], v[1]))


def load(path):
    if path.endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    body = max((o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)),
               key=lambda o: len(o.data.vertices))
    return arm, body


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    src, name = argv[0], (argv[1] if len(argv) > 1 else 'femme')
    arm, body = load(src)
    pfx = next(b.name for b in arm.data.bones if b.name.endswith('Hips'))[:-4]  # « mixamorig: »
    P = lambda n: arm.pose.bones[pfx + n]  # noqa: E731
    mw = arm.matrix_world
    rq = mw.to_quaternion()

    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    def head(n):
        return mw @ P(n).head

    def rotate_world(n, q):
        """Tourne l'os n (et ses enfants) de q (repère monde) autour de sa tête."""
        pb = P(n)
        qa = rq.inverted() @ q @ rq
        h = pb.head.copy()
        pb.matrix = Matrix.Translation(h) @ qa.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
        bpy.context.view_layer.update()

    def aim(n, child, target):
        d = (head(child) - head(n)).normalized()
        rotate_world(n, d.rotation_difference(target.normalized()))

    foot_dir = {s: (head(s + 'ToeBase') - head(s + 'Foot')).normalized() for s in ('Left', 'Right')}
    for s, sx in (('Left', 1), ('Right', -1)):
        # jambes, puis pied remis à plat (même direction qu'avant)
        for part in ('UpLeg', 'Leg'):
            dx, dy, dz = AIM_DIRS[part]
            aim(s + part, s + CHILD[part], to_blender((dx * sx, dy, dz)))
        aim(s + 'Foot', s + 'ToeBase', foot_dir[s])
        # bras, avant-bras, main
        for part in ('Arm', 'ForeArm', 'Hand'):
            dx, dy, dz = AIM_DIRS[part]
            aim(s + part, s + CHILD[part], to_blender((dx * sx, dy, dz)))

        # paume vers la cuisse : on tourne l'avant-bras sur son axe
        def palm():
            hd = (head(s + 'HandMiddle1') - head(s + 'Hand')).normalized()
            across = head(s + 'HandPinky1') - head(s + 'HandIndex1')
            n = across.cross(hd) if sx > 0 else hd.cross(across)
            return n.normalized()
        inward = Vector((-sx, 0, 0))

        def best_twist(bone, axis):
            best, best_a = -2, 0.0
            for k in range(72):
                a = -math.pi + k * math.pi / 36
                rotate_world(bone, Quaternion(axis, a))
                v = palm().dot(inward)
                rotate_world(bone, Quaternion(axis, -a))
                if v > best:
                    best, best_a = v, a
            return best_a
        # la torsion se répartit entre le bras et l'avant-bras (coude moins vrillé)
        fa = (head(s + 'Hand') - head(s + 'ForeArm')).normalized()
        a = best_twist(s + 'ForeArm', fa)
        rotate_world(s + 'Arm', Quaternion((head(s + 'ForeArm') - head(s + 'Arm')).normalized(), a * 0.4))
        aim(s + 'ForeArm', s + 'Hand', to_blender((AIM_DIRS['ForeArm'][0] * sx, *AIM_DIRS['ForeArm'][1:])))
        fa = (head(s + 'Hand') - head(s + 'ForeArm')).normalized()
        rotate_world(s + 'ForeArm', Quaternion(fa, best_twist(s + 'ForeArm', fa)))
        aim(s + 'Hand', s + 'HandMiddle1', to_blender((AIM_DIRS['Hand'][0] * sx, *AIM_DIRS['Hand'][1:])))
        print(f'{s} : paume vers la cuisse ({palm().dot(inward):.2f})')

    # Orientation des os Mixamo dans cette position (référence des animations).
    ref_q = {n: (mw @ P(m).matrix).to_quaternion() for n, m in ANIM_MAP.items()}
    ref_hips = head('Hips').copy()

    # Maillage déformé dans cette position de repos.
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    V = np.array([to_site(ev.matrix_world @ v.co) for v in me.vertices])
    faces = [list(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()

    # Articulations (têtes d'os) dans le repère du site.
    J = {
        'Hips': head('Hips'), 'Spine': head('Spine'), 'Neck': head('Neck'), 'Head': head('Head'),
    }
    for s in ('Left', 'Right'):
        J[s + 'Arm'] = head(s + 'Arm')
        J[s + 'ForeArm'] = head(s + 'ForeArm')
        J[s + 'Hand'] = head(s + 'Hand')
        J[s + 'HandTip'] = head(s + 'HandMiddle1')
        J[s + 'UpLeg'] = head(s + 'UpLeg')
        J[s + 'Leg'] = head(s + 'Leg')
        J[s + 'Foot'] = head(s + 'Foot')
    J = {k: to_site(v) for k, v in J.items()}

    # Échelle, sol à y = 0, axe vertical passant par le bassin.
    scale = HEIGHT / (V[:, 1].max() - V[:, 1].min())
    origin = np.array([0.0, V[:, 1].min(), J['Hips'][2]])
    V = (V - origin) * scale
    J = {k: (v - origin) * scale for k, v in J.items()}

    # Poids : os Mixamo → 16 os du site, 4 influences au plus.
    gname = {g.index: site_bone(g.name) for g in body.vertex_groups}
    W = np.zeros((len(V), len(BONES)))
    for v in body.data.vertices:
        for g in v.groups:
            if g.group in gname and g.weight > 0:
                W[v.index, BONES.index(gname[g.group])] += g.weight
    order = np.argsort(-W, axis=1)[:, :4]
    wsel = np.take_along_axis(W, order, axis=1)
    wsel = np.where(wsel.sum(1, keepdims=True) > 0, wsel / np.maximum(wsel.sum(1, keepdims=True), 1e-9), [1, 0, 0, 0])
    wq = np.round(wsel * 255).astype(int)
    wq[:, 0] += 255 - wq.sum(1)
    skin_i = order.astype(np.uint8)
    skin_w = np.clip(wq, 0, 255).astype(np.uint8)
    Wn = W / np.maximum(W.sum(1, keepdims=True), 1e-9)

    # Le modèle a été assemblé à partir de sphères : les raccords laissent des
    # plis (ceinture à la taille, bande sur le bassin, épaules en boule).
    # Lissage de Taubin (sans perte de volume) sur le tronc, les épaules et le
    # haut des cuisses ; mains, pieds et tête restent intacts.
    V = taubin(V, faces, smooth_mask(V, Wn, J), SMOOTH_ITER)
    V, touched = soften_bands(V, Wn, J)
    V = taubin(V, faces, touched, 12)  # finition : retire le grain laissé par la correction

    tris = []
    for f in faces:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    tris = np.array(tris, dtype=np.uint16)
    Pf = V.astype(np.float32)

    # Repères de mesure (comme build_mannequin.py).
    torso_w = Wn[:, BONES.index('Hips')] + Wn[:, BONES.index('Spine')]
    torso = Pf[torso_w > 0.6]

    def perim(y):
        s = torso[np.abs(torso[:, 1] - y) < 0.006]
        return hull_perimeter(s[:, [0, 2]]) if len(s) > 8 else 0.0
    hip_j = J['LeftUpLeg'][1]
    ys = np.linspace(hip_j - 0.12, hip_j + 0.1, 45)
    hip_y = float(ys[np.argmax([perim(y) for y in ys])])
    ys = np.linspace(J['Spine'][1] - 0.02, J['Spine'][1] + 0.2, 45)
    waist_y = float(ys[np.argmin([perim(y) for y in ys])])
    spine_v = Pf[Wn[:, BONES.index('Spine')] > 0.6]
    chest = spine_v[(spine_v[:, 1] > waist_y + 0.12) & (spine_v[:, 1] < J['LeftArm'][1] - 0.03)]
    bust_y = float(chest[np.argmax(chest[:, 2]), 1])

    soles, seat = [], []
    for side in ('Left', 'Right'):
        fk = BONES.index(side + 'Foot')
        f = np.where((Wn[:, fk] > 0.5) & (Pf[:, 1] < 0.012))[0]
        soles += f[np.linspace(0, len(f) - 1, min(40, len(f))).astype(int)].tolist()
    sk = [BONES.index(b) for b in ('Hips', 'LeftUpLeg', 'RightUpLeg')]
    s = np.where((Wn[:, sk].sum(1) > 0.6) & (Pf[:, 1] > hip_j - 0.2) & (Pf[:, 1] < hip_j + 0.05) & (Pf[:, 2] < 0))[0]
    seat = s[np.linspace(0, len(s) - 1, min(160, len(s))).astype(int)].tolist()

    OUT.mkdir(parents=True, exist_ok=True)
    blob = Pf.tobytes() + skin_i.tobytes() + skin_w.tobytes() + tris.tobytes()
    (OUT / f'{name}.bin').write_bytes(blob)
    meta = {
        'source': f'{pathlib.Path(src).name} (tutoriel « Blender Cloth Simulation »), rig Mixamo',
        'vertexCount': int(len(Pf)), 'indexCount': int(tris.size), 'bones': BONES,
        'joints': {k: [round(float(c), 5) for c in v] for k, v in J.items()},
        'ownHead': True, 'rest': {},
        # passage repère Blender du fichier source → repère du site (pour les vêtements
        # modélisés sur ce corps : tools/convert_garment.py --native)
        'sourceTransform': {'origin': [round(float(c), 6) for c in origin], 'scale': round(float(scale), 8)},
        'landmarks': {'bust': bust_y, 'waist': waist_y, 'hip': hip_y},
        'soles': soles, 'seat': seat,
    }
    (OUT / f'{name}.json').write_text(json.dumps(meta, indent=1))
    print(f'{name}: {len(Pf)} sommets, {len(tris)} triangles, {len(blob) // 1024} Ko, échelle {scale:.4f} ; '
          f'poitrine {perim(bust_y):.3f} / taille {perim(waist_y):.3f} / hanches {perim(hip_y):.3f} m '
          f'(à {bust_y:.3f} / {waist_y:.3f} / {hip_y:.3f}) ; semelles {len(soles)}, assise {len(seat)}')
    if export_animations(arm, P, mw, ref_q, ref_hips, origin, scale, name):
        meta['clips'] = ['defile']
        (OUT / f'{name}.json').write_text(json.dumps(meta, indent=1))
    return scale, origin


def export_animations(arm, P, mw, ref_q, ref_hips, origin, scale, name):
    """Animations du fichier → rotations des 16 os du site, image par image.

    Pour chaque os : rotation (repère du site) depuis la position de liaison du
    maillage exporté, et déplacement du bassin. Le site en déduit la pose (voir
    rig.js, playClip). Seul le cycle de marche en boucle est gardé (« défilé »).
    """
    sc = bpy.context.scene
    acts = [a for a in bpy.data.actions if a.name.startswith(arm.name) or 'mixamo' in a.name]
    cycle = min(acts, key=lambda a: a.frame_range[1] - a.frame_range[0], default=None)
    if not cycle:
        return False
    ad = arm.animation_data_create()
    ad.action = cycle
    if hasattr(ad, 'action_slot') and ad.action_slot is None and len(getattr(cycle, 'slots', [])):
        ad.action_slot = cycle.slots[0]  # Blender ≥ 4.4 : actions à « emplacements »
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    f0, f1 = map(int, cycle.frame_range)
    frames = []
    for f in range(f0, f1):  # la dernière image est la première (boucle)
        sc.frame_set(f)
        bpy.context.view_layer.update()
        q = {}
        for n, m in ANIM_MAP.items():
            d = (mw @ P(m).matrix).to_quaternion() @ ref_q[n].inverted()
            # Blender → site : (x, y, z) → (x, z, -y) ; quaternion (x, y, z, w) pour three.js
            q[n] = [round(d.x, 5), round(d.z, 5), round(-d.y, 5), round(d.w, 5)]
        h = (to_site(mw @ P('Hips').head) - to_site(ref_hips)) * scale
        frames.append({'h': [round(float(c), 5) for c in h], 'q': q})
    # vitesse de marche (pied posé qui recule) : sert à la simulation du tissu
    out = OUT / f'{name}-defile.json'
    out.write_text(json.dumps({'fps': sc.render.fps, 'source': cycle.name, 'speed': walk_speed(arm, P, mw, cycle, scale), 'frames': frames}))
    print(f'animation « défilé » : {len(frames)} images à {sc.render.fps} i/s → {out.name}')
    return True


def walk_speed(arm, P, mw, act, scale):
    """Vitesse (m/s) du pied posé au sol, dans le cycle sur place."""
    sc = bpy.context.scene
    f0, f1 = map(int, act.frame_range)
    pts = []
    for f in range(f0, f1):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        for s in ('Left', 'Right'):
            p = to_site(mw @ P(s + 'Foot').head) * scale
            pts.append((f, s, p))
    v = []
    for s in ('Left', 'Right'):
        ps = [(f, p) for f, s2, p in pts if s2 == s]
        low = min(p[1] for f, p in ps)
        for (fa, a), (fb, b) in zip(ps, ps[1:]):
            if a[1] < low + 0.01 and b[1] < low + 0.01:  # pied au sol
                v.append((a[2] - b[2]) * sc.render.fps)
    return round(float(np.median(v)), 4) if v else 0.0


if __name__ == '__main__':
    main()
