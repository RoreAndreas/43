#!/usr/bin/env python3
"""Reporte une marche animée (fichier .blend rigué) sur les 16 os du site.

Source : « Rigged Man With Walk Cycle » par brightonpiers (Blend Swap,
CC BY 3.0 : crédit obligatoire). Le cycle (sur place) est repéré, puis pour
chaque image on calcule l'orientation monde de chaque os du site :
  - membres : la direction du segment suit celle de la source ;
  - tronc, tête, pieds : la rotation de la source depuis sa position de repos.
Écrit assets/mannequin/<nom>-defile.json et le déclare dans <nom>.json.

Usage : python tools/import_walk.py -- "walking man.blend" [noms=femme,homme] [début=0] [longueur=40]
"""
import json
import pathlib
import sys

import bpy  # noqa: I001
import numpy as np
from mathutils import Quaternion, Vector

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets' / 'mannequin'
# os du site → os de la source ; « limb » : on suit la direction du segment
MAP = {
    'Hips': ('hips', False), 'Spine': ('ribs', False), 'Neck': ('neck', False), 'Head': ('head', False),
    **{f'{S}Arm': (f'upper_arm.{s}', True) for S, s in (('Left', 'L'), ('Right', 'R'))},
    **{f'{S}ForeArm': (f'forearm.{s}', True) for S, s in (('Left', 'L'), ('Right', 'R'))},
    **{f'{S}Hand': (f'hand.{s}', True) for S, s in (('Left', 'L'), ('Right', 'R'))},
    **{f'{S}UpLeg': (f'thigh.{s}', True) for S, s in (('Left', 'L'), ('Right', 'R'))},
    **{f'{S}Leg': (f'shin.{s}', True) for S, s in (('Left', 'L'), ('Right', 'R'))},
    **{f'{S}Foot': (f'foot.{s}', False) for S, s in (('Left', 'L'), ('Right', 'R'))},
}


def site_v(v):
    return Vector((v[0], v[2], -v[1]))


def site_q(q):
    return Quaternion((q.w, q.x, q.z, -q.y))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    src = argv[0]
    names = (argv[1] if len(argv) > 1 else 'femme,homme').split(',')
    start = int(argv[2]) if len(argv) > 2 else 0
    length = int(argv[3]) if len(argv) > 3 else 40
    bpy.ops.wm.open_mainfile(filepath=src, load_ui=False, use_scripts=False)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    sc = bpy.context.scene
    mw = arm.matrix_world
    mq = mw.to_quaternion()
    # repos de la source
    rest = {}
    for n, (b, _) in MAP.items():
        bone = arm.data.bones[b]
        rest[n] = (mq @ bone.matrix_local.to_quaternion(), site_v(mw.to_3x3() @ (bone.tail_local - bone.head_local)).normalized())
    hips0 = site_v(mw @ arm.data.bones['hips'].head_local)
    leg_src = (arm.data.bones['thigh.L'].length + arm.data.bones['shin.L'].length) * mw.to_scale()[0]

    meta0 = json.loads((OUT / f'{names[0]}.json').read_text())
    J = {k: Vector(v) for k, v in meta0['joints'].items()}
    leg_dst = (J['LeftLeg'] - J['LeftUpLeg']).length + (J['LeftFoot'] - J['LeftLeg']).length
    k = leg_dst / leg_src

    down = Vector((0, -1, 0))
    frames, hs = [], []
    for f in range(start, start + length):
        sc.frame_set(f)
        q = {}
        for n, (b, limb) in MAP.items():
            pb = arm.pose.bones[b]
            Rf = mq @ pb.matrix.to_quaternion()
            if limb:
                d = site_v(mw.to_3x3() @ (pb.tail - pb.head)).normalized()
                W = down.rotation_difference(d)  # le segment (bras, jambe…) pointe comme celui de la source
            else:
                W = site_q(Rf @ rest[n][0].inverted())
                if n == 'Neck':  # cou de la source plus court : on garde la moitié de son hochement
                    W = Quaternion().slerp(W, 0.5)
            q[n] = [round(W.x, 5), round(W.y, 5), round(W.z, 5), round(W.w, 5)]
        h = (site_v(mw @ arm.pose.bones['hips'].head) - hips0) * k
        hs.append(h)
        frames.append({'q': q, 'h': [round(c, 5) for c in h]})
    # le cycle est sur place : on retire une éventuelle dérive horizontale
    drift = (hs[-1] - hs[0]) / max(1, len(hs) - 1)
    for i, fr in enumerate(frames):
        fr['h'][0] = round(fr['h'][0] - drift.x * i, 5)
        fr['h'][2] = round(fr['h'][2] - drift.z * i, 5)
    data = {'fps': sc.render.fps, 'world': True, 'source': 'Rigged Man With Walk Cycle — brightonpiers (Blend Swap, CC BY 3.0)', 'frames': frames}
    for name in names:
        (OUT / f'{name}-defile.json').write_text(json.dumps(data))
        meta = json.loads((OUT / f'{name}.json').read_text())
        meta['clips'] = ['defile']
        (OUT / f'{name}.json').write_text(json.dumps(meta, indent=1))
    print(f'marche : {len(frames)} images à {sc.render.fps} i/s, échelle {k:.3f} → {names}')


if __name__ == '__main__':
    main()
