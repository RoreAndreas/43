#!/usr/bin/env python3
"""Fabrique les mannequins de vitrine (femme, homme) à partir de MakeHuman.

Le maillage de base, les cibles de morphologie et les poids du squelette
MakeHuman sont publiés sous licence CC0 (domaine public). Ce script :

1. télécharge ces fichiers (mis en cache dans tools/.cache) ;
2. applique une « recette » de cibles : silhouette femme ou homme, mince,
   élancée, proportions idéales (allure mannequin de vitrine) ;
3. retire la tête (le visage) : le site la remplace par une tête ovale lisse ;
4. regroupe les 163 os MakeHuman sur les 16 os du site (Hips, Spine, LeftArm…) ;
5. écrit assets/mannequin/<nom>.bin (géométrie + poids) et <nom>.json
   (articulations, repères de mesure, points de contact).

Usage : python3 tools/build_mannequin.py
"""
import json
import pathlib
import urllib.request

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / 'tools' / '.cache'
OUT = ROOT / 'assets' / 'mannequin'
MH = 'https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/'

RACES = ['african', 'asian', 'caucasian']
RECIPES = {
    # Silhouette galbée, d'après le modèle de référence fourni (hanches et
    # fessiers marqués, taille fine, poitrine ronde).
    'femme': [
        *[(f'targets/macrodetails/{r}-female-young.target', 1 / 3) for r in RACES],
        ('targets/macrodetails/universal-female-young-averagemuscle-minweight.target', 0.05),
        ('targets/macrodetails/height/female-young-averagemuscle-averageweight-maxheight.target', 0.3),
        ('targets/macrodetails/proportions/female-young-averagemuscle-averageweight-idealproportions.target', 1.0),
        ('targets/breast/female-young-averagemuscle-averageweight-maxcup-maxfirmness.target', 0.35),
        ('targets/breast/nipple-point-decr.target', 1.0),
        ('targets/breast/nipple-size-decr.target', 1.0),
        ('targets/hip/hip-scale-horiz-incr.target', 0.45),
        ('targets/hip/hip-scale-depth-incr.target', 0.3),
        ('targets/buttocks/buttocks-volume-incr.target', 0.8),
        ('targets/armslegs/l-upperleg-fat-incr.target', 0.2),
        ('targets/armslegs/r-upperleg-fat-incr.target', 0.2),
        ('targets/torso/torso-vshape-decr.target', 0.3),
    ],
    'homme': [
        *[(f'targets/macrodetails/{r}-male-young.target', 1 / 3) for r in RACES],
        ('targets/macrodetails/universal-male-young-averagemuscle-minweight.target', 0.2),
        ('targets/macrodetails/universal-male-young-maxmuscle-averageweight.target', 0.2),
        ('targets/macrodetails/height/male-young-averagemuscle-averageweight-maxheight.target', 0.45),
        ('targets/macrodetails/proportions/male-young-averagemuscle-averageweight-idealproportions.target', 1.0),
    ],
}

BONES = ['Hips', 'Spine', 'Neck', 'Head',
         'LeftArm', 'LeftForeArm', 'LeftHand', 'RightArm', 'RightForeArm', 'RightHand',
         'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'RightUpLeg', 'RightLeg', 'RightFoot']


def fetch(rel):
    path = CACHE / rel
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print('téléchargement', rel)
        urllib.request.urlretrieve(MH + rel, path)
    return path


def load_obj():
    verts, groups, cur = [], {}, None
    for line in fetch('3dobjs/base.obj').read_text().splitlines():
        if line.startswith('v '):
            verts.append([float(t) for t in line.split()[1:4]])
        elif line.startswith('g '):
            cur = line.split()[1]
            groups.setdefault(cur, [])
        elif line.startswith('f '):
            groups[cur].append([int(t.split('/')[0]) - 1 for t in line.split()[1:]])
    return np.array(verts), groups


def load_target(rel):
    idx, d = [], []
    for line in fetch(rel).read_text().splitlines():
        if line.startswith('#') or not line.strip():
            continue
        p = line.split()
        idx.append(int(p[0]))
        d.append([float(t) for t in p[1:4]])
    return np.array(idx, dtype=int), np.array(d)


def map_bone(name):
    base = name.split('.')[0]
    side = 'Left' if name.endswith('.L') else 'Right' if name.endswith('.R') else ''
    if base in ('root', 'spine05', 'spine04', 'pelvis'):
        return 'Hips'
    if base in ('spine03', 'spine02', 'spine01', 'breast', 'clavicle'):
        return 'Spine'
    if base.startswith('neck'):
        return 'Neck'
    if base in ('shoulder01', 'upperarm01', 'upperarm02'):
        return side + 'Arm'
    if base.startswith('lowerarm'):
        return side + 'ForeArm'
    if base == 'wrist' or base.startswith('metacarpal') or base.startswith('finger'):
        return side + 'Hand'
    if base.startswith('upperleg'):
        return side + 'UpLeg'
    if base.startswith('lowerleg'):
        return side + 'Leg'
    if base == 'foot' or base.startswith('toe'):
        return side + 'Foot'
    return 'Head'


def hull_perimeter(pts):
    pts = sorted(map(tuple, pts))
    if len(pts) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    h = np.array(lo[:-1] + up[:-1])
    return float(np.sum(np.linalg.norm(h - np.roll(h, -1, axis=0), axis=1)))


def build(name, recipe, V0, groups, skel, weights):
    V = V0.copy()
    for rel, w in recipe:
        i, d = load_target(rel)
        V[i] += w * d
    V = V / 10.0  # décimètres → mètres

    def joint(jname):
        return V[skel['joints'][jname]].mean(axis=0)

    def head(b):
        return joint(skel['bones'][b]['head'])

    # Sol à y = 0, axe vertical passant par le bassin.
    body = np.array(groups['body'])
    used = np.unique(body)
    floor = V[used, 1].min()
    origin = np.array([0.0, floor, head('spine05')[2]])
    V = V - origin

    J = {
        'Hips': head('spine05'), 'Spine': head('spine03'), 'Neck': head('neck01'), 'Head': head('head'),
    }
    for s, S in (('L', 'Left'), ('R', 'Right')):
        J[S + 'Arm'] = head(f'upperarm01.{s}')
        J[S + 'ForeArm'] = head(f'lowerarm01.{s}')
        J[S + 'Hand'] = head(f'wrist.{s}')
        J[S + 'HandTip'] = head(f'finger3-1.{s}')
        J[S + 'UpLeg'] = head(f'upperleg01.{s}')
        J[S + 'Leg'] = head(f'lowerleg01.{s}')
        J[S + 'Foot'] = head(f'foot.{s}')

    # Poids : 163 os MakeHuman → 16 os du site, 4 influences au plus.
    W = np.zeros((len(V0), len(BONES)))
    for bname, lst in weights.items():
        k = BONES.index(map_bone(bname))
        for vi, w in lst:
            W[vi, k] += w

    # Mannequin lisse : on efface tétons et nombril par lissage local.
    nbr = [set() for _ in range(len(V0))]
    for f in body:
        for a in range(4):
            nbr[f[a]].update((f[a - 1], f[(a + 1) % 4]))
    bv = V[used]
    spot = []
    for sx in (1, -1):
        m = (bv[:, 0] * sx > 0.03) & (bv[:, 1] > J['Spine'][1] + 0.12) & (bv[:, 1] < J['LeftArm'][1] - 0.04)
        spot.append((bv[m][np.argmax(bv[m][:, 2])], 0.05))
    m = (np.abs(bv[:, 0]) < 0.012) & (bv[:, 1] > J['Hips'][1] + 0.02) & (bv[:, 1] < J['Spine'][1] + 0.06) & (bv[:, 2] > 0)
    front = bv[m]
    navel = front[np.argmin(front[:, 2] - 0.4 * np.abs(front[:, 1] - front[:, 1].mean()))]
    spot.append((navel, 0.03))
    for c, R in spot:
        d = np.linalg.norm(V[used] - c, axis=1)
        region = used[d < R]
        fall = (1 - d[d < R] / R) ** 1.5
        for _ in range(70):
            avg = np.array([V[list(nbr[i])].mean(axis=0) for i in region])
            V[region] += (avg - V[region]) * (0.8 * fall)[:, None]

    # Découpe du cou, à plat, juste au-dessus de la base du cou. Seul le
    # cylindre du cou est coupé : les trapèzes (plus larges) restent intacts.
    hw_all = W[:, BONES.index('Head')]
    front_head = V[used][(hw_all[used] > 0.5) & (V[used, 2] > J['Head'][2] + 0.04)]
    y_cut = min(J['Neck'][1] + 0.022, front_head[:, 1].min() - 0.03)  # sous la mâchoire
    axis_z = J['Neck'][2] + 0.02
    r_xz = np.hypot(V[:, 0], (V[:, 2] - axis_z) * 0.9)
    gone = ((V[:, 1] > y_cut) & ((r_xz < 0.085) | (np.abs(V[:, 0]) < 0.075))) | (V[:, 1] > J['Head'][1] - 0.02)
    keep = ~np.any(gone[body] & (V[body, 1] > y_cut + 0.002), axis=1)
    faces = body[keep]
    kept = np.unique(faces)
    flat = kept[gone[kept]]
    # Section du cou à la hauteur de coupe (maillage intact), pour le raccord.
    sl = V[used][(np.abs(V[used, 1] - y_cut) < 0.005) & (r_xz[used] < 0.072)]
    V[flat, 1] = y_cut
    remap = -np.ones(len(V0), dtype=int)
    remap[kept] = np.arange(len(kept))
    tris = []
    for a, b, c, d in remap[faces]:
        tris += [(a, b, c), (a, c, d)]
    tris = np.array(tris, dtype=np.uint16)
    P = V[kept].astype(np.float32)
    Wk = W[kept]
    order = np.argsort(-Wk, axis=1)[:, :4]
    wsel = np.take_along_axis(Wk, order, axis=1)
    wsel = np.where(wsel.sum(1, keepdims=True) > 0, wsel / np.maximum(wsel.sum(1, keepdims=True), 1e-9), [1, 0, 0, 0])
    wq = np.round(wsel * 255).astype(int)
    wq[:, 0] += 255 - wq.sum(1)  # somme exacte à 255
    skin_i = order.astype(np.uint8)
    skin_w = np.clip(wq, 0, 255).astype(np.uint8)

    # Anneau de coupe (pour raccorder le cou procédural) et gabarit de la tête retirée.
    ring = sl
    hw = W[used, BONES.index('Head')]
    head_v = V[used][(hw > 0.5) & (V[used, 1] > y_cut)]
    head_core = head_v[np.abs(head_v[:, 0]) < 0.065]  # sans les oreilles
    jaw = head_core[head_core[:, 2] > J['Head'][2] + 0.04]
    neck_cut = {
        'y': float(y_cut), 'cz': float((ring[:, 2].max() + ring[:, 2].min()) / 2),
        'rx': float(np.abs(ring[:, 0]).max()), 'rz': float((ring[:, 2].max() - ring[:, 2].min()) / 2),
    }
    head_dims = {
        'top': float(head_v[:, 1].max()), 'chin': float(jaw[:, 1].min()),
        'rx': float(np.abs(head_v[:, 0][np.abs(head_v[:, 0]) < 0.085]).max()),
        'zf': float(head_core[:, 2].max()), 'zb': float(head_core[:, 2].min()),
    }

    # Repères de mesure (hauteurs du tour de poitrine, taille, hanches).
    torso_w = Wk[:, BONES.index('Hips')] + Wk[:, BONES.index('Spine')]
    torso = P[torso_w > 0.6]

    def perim(y):
        s = torso[np.abs(torso[:, 1] - y) < 0.006]
        return hull_perimeter(s[:, [0, 2]]) if len(s) > 8 else 0.0
    hip_j = J['LeftUpLeg'][1]
    ys = np.linspace(hip_j - 0.12, hip_j + 0.1, 45)
    hip_y = float(ys[np.argmax([perim(y) for y in ys])])
    ys = np.linspace(J['Spine'][1] - 0.02, J['Spine'][1] + 0.16, 40)
    waist_y = float(ys[np.argmin([perim(y) for y in ys])])
    spine_v = P[Wk[:, BONES.index('Spine')] > 0.6]
    chest = spine_v[(spine_v[:, 1] > waist_y + 0.12) & (spine_v[:, 1] < J['LeftArm'][1] - 0.03)]
    bust_y = float(chest[np.argmax(chest[:, 2]), 1])

    # Points de contact : semelles (pour poser au sol) et fessiers (pour s'asseoir).
    soles, seat = [], []
    for side in ('Left', 'Right'):
        fk = BONES.index(side + 'Foot')
        f = np.where((Wk[:, fk] > 0.5) & (P[:, 1] < 0.012))[0]
        soles += f[np.linspace(0, len(f) - 1, min(40, len(f))).astype(int)].tolist()
    sk = [BONES.index(b) for b in ('Hips', 'LeftUpLeg', 'RightUpLeg')]
    s = np.where((Wk[:, sk].sum(1) > 0.6) & (P[:, 1] > hip_j - 0.2) & (P[:, 1] < hip_j + 0.05) & (P[:, 2] < 0))[0]
    seat = s[np.linspace(0, len(s) - 1, min(160, len(s))).astype(int)].tolist()

    OUT.mkdir(parents=True, exist_ok=True)
    blob = P.tobytes() + skin_i.tobytes() + skin_w.tobytes() + tris.tobytes()
    (OUT / f'{name}.bin').write_bytes(blob)
    meta = {
        'source': 'MakeHuman base mesh hm08, targets & default rig — CC0 1.0 (makehumancommunity.org)',
        'vertexCount': int(len(P)), 'indexCount': int(tris.size), 'bones': BONES,
        'joints': {k: [round(float(c), 5) for c in v] for k, v in J.items()},
        'neckCut': neck_cut, 'head': head_dims,
        'landmarks': {'bust': bust_y, 'waist': waist_y, 'hip': hip_y},
        'soles': soles, 'seat': seat,
    }
    (OUT / f'{name}.json').write_text(json.dumps(meta, indent=1))
    h = P[:, 1].max()
    print(f'{name}: {len(P)} sommets, {len(tris)} triangles, {len(blob) // 1024} Ko, '
          f'hauteur sans tête {h:.3f} m, rapports à la hauteur (tête comprise) : hanches {perim(hip_y) / (meta["head"]["top"]):.3f}, '
          f'taille {perim(waist_y) / (meta["head"]["top"]):.3f} ; poitrine {perim(bust_y):.3f} / taille {perim(waist_y):.3f} / hanches {perim(hip_y):.3f} m')


def main():
    V0, groups = load_obj()
    skel = json.loads(fetch('rigs/default.mhskel').read_text())
    weights = json.loads(fetch('rigs/default_weights.mhw').read_text())['weights']
    for name, recipe in RECIPES.items():
        build(name, recipe, V0, groups, skel, weights)


if __name__ == '__main__':
    main()
