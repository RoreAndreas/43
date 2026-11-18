#!/usr/bin/env python3
"""Importe le mannequin articulé unisexe (Mannequin-Rig.blend, P2Design) au format du site.

Le modèle est utilisé tel quel : maillage du fichier (symétrie et une
subdivision appliquées), position de liaison du rig (bras en T), poids des os
« DEF- » regroupés sur les 16 os du site. Le site met lui-même bras et jambes
le long du corps (position de repos commune : les poses restent valables).

Usage (module Python de Blender) :
    python tools/import_rig_mannequin.py -- Mannequin-Rig.blend [noms=femme,homme]
"""
import json
import pathlib
import sys

import bpy  # noqa: I001
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from build_mannequin import BONES, hull_perimeter  # noqa: E402

OUT = ROOT / 'assets' / 'mannequin'
HEIGHT = 1.81


def site_bone(name):
    n = name[4:] if name.startswith('DEF-') else name
    side = 'Left' if n.endswith('.L') else 'Right' if n.endswith('.R') else ''
    b = n.split('.')[0]
    if b == 'HIPS':
        return 'Hips'
    if b.startswith(('SPINE', 'CHEST', 'SHOULDER')):
        return 'Spine'
    if b == 'NECK':
        return 'Neck'
    if b == 'HEAD':
        return 'Head'
    if b.startswith('ARM'):
        return side + 'Arm'
    if b.startswith('FORARM'):
        return side + 'ForeArm'
    if b.startswith(('HAND', 'PALM', 'FINGER', 'THUMB')):
        return side + 'Hand'
    if b.startswith('THIGH'):
        return side + 'UpLeg'
    if b.startswith('SHIN'):
        return side + 'Leg'
    if b.startswith(('FOOT', 'TOE')):
        return side + 'Foot'
    return None


def to_site(v):
    return np.array([v[0], v[2], -v[1]], dtype=np.float64)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    src = argv[0]
    names = (argv[1] if len(argv) > 1 else 'femme,homme').split(',')
    bpy.ops.wm.open_mainfile(filepath=src, load_ui=False, use_scripts=False)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    ob = next(o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers))
    arm.data.pose_position = 'REST'
    for m in ob.modifiers:
        if m.type == 'MASK':
            m.show_viewport = False
        if m.type == 'SUBSURF':
            m.levels = 1
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    V = np.array([to_site(mw @ v.co) for v in me.vertices])
    faces = [list(p.vertices) for p in me.polygons]
    fmat = [p.material_index for p in me.polygons]  # 0 : blanc, 1 : rouge (pièces du mannequin)
    gname = {g.index: site_bone(g.name) for g in ob.vertex_groups}
    W = np.zeros((len(V), len(BONES)))
    for v in me.vertices:
        for g in v.groups:
            b = gname.get(g.group)
            if b and g.weight > 0:
                W[v.index, BONES.index(b)] += g.weight
    ev.to_mesh_clear()

    def head(n):
        return to_site(arm.matrix_world @ arm.data.bones[n].head_local)
    J = {'Hips': head('DEF-HIPS'), 'Spine': head('DEF-SPINE01'), 'Neck': head('DEF-NECK'), 'Head': head('DEF-HEAD')}
    for s, x in (('Left', 'L'), ('Right', 'R')):
        J[s + 'Arm'] = head(f'DEF-ARM01.{x}')
        J[s + 'ForeArm'] = head(f'DEF-FORARM01.{x}')
        J[s + 'Hand'] = head(f'DEF-HAND.{x}')
        J[s + 'HandTip'] = head(f'DEF-FINGER-B-01.{x}')
        J[s + 'UpLeg'] = head(f'DEF-THIGH01.{x}')
        J[s + 'Leg'] = head(f'DEF-SHIN01.{x}')
        J[s + 'Foot'] = head(f'DEF-FOOT.{x}')

    scale = HEIGHT / (V[:, 1].max() - V[:, 1].min())
    origin = np.array([0.0, V[:, 1].min(), J['Hips'][2]])
    V = (V - origin) * scale
    J = {k: (v - origin) * scale for k, v in J.items()}

    order = np.argsort(-W, axis=1)[:, :4]
    wsel = np.take_along_axis(W, order, axis=1)
    wsel = np.where(wsel.sum(1, keepdims=True) > 0, wsel / np.maximum(wsel.sum(1, keepdims=True), 1e-9), [1, 0, 0, 0])
    wq = np.round(wsel * 255).astype(int)
    wq[:, 0] += 255 - wq.sum(1)
    skin_i = order.astype(np.uint8)
    skin_w = np.clip(wq, 0, 255).astype(np.uint8)
    Wn = W / np.maximum(W.sum(1, keepdims=True), 1e-9)

    tris, groups = [], []
    for mat in (0, 1):  # triangles rangés par matière
        n0 = len(tris)
        for f, fm in zip(faces, fmat):
            if (fm != 0) == bool(mat):
                for k in range(1, len(f) - 1):
                    tris.append((f[0], f[k], f[k + 1]))
        groups.append((len(tris) - n0) * 3)
    tris = np.array(tris, dtype=np.uint16)
    Pf = V.astype(np.float32)

    torso = Pf[(Wn[:, BONES.index('Hips')] + Wn[:, BONES.index('Spine')]) > 0.6]

    def perim(y):
        s = torso[np.abs(torso[:, 1] - y) < 0.008]
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

    blob = Pf.tobytes() + skin_i.tobytes() + skin_w.tobytes() + tris.tobytes()
    meta = {
        'source': f'{pathlib.Path(src).name} (mannequin articulé P2Design), unisexe',
        'vertexCount': int(len(Pf)), 'indexCount': int(tris.size), 'bones': BONES,
        'joints': {k: [round(float(c), 5) for c in v] for k, v in J.items()},
        'ownHead': True, 'rest': {}, 'groups': groups,
        'landmarks': {'bust': bust_y, 'waist': waist_y, 'hip': hip_y},
        'soles': soles, 'seat': seat,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        (OUT / f'{name}.bin').write_bytes(blob)
        (OUT / f'{name}.json').write_text(json.dumps(meta, indent=1))
    print(f'{names}: {len(Pf)} sommets, {len(tris)} triangles, {len(blob) // 1024} Ko ; poitrine {perim(bust_y):.3f} / '
          f'taille {perim(waist_y):.3f} / hanches {perim(hip_y):.3f} m ; semelles {len(soles)}, assise {len(seat)}')


if __name__ == '__main__':
    main()
