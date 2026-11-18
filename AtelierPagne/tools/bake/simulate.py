#!/usr/bin/env python3
"""Étape 2 du pré-calcul : simulation du tissu dans Blender, pour une taille et une pose.

Pour chaque fichier exporté par tools/bake/export.mjs :
- le mannequin (collisionneur) refait lentement le vrai mouvement du repos à la
  pose ; pour s'asseoir, il part debout devant le socle et recule, pieds posés ;
- la robe part ajustée au repos ; le bustier reste épinglé au corps et le suit,
  le reste du tissu est libre : il tombe, glisse sur les jambes, se pose sur le
  socle et au sol, avec ses propres collisions ;
- on enregistre la forme finale, dans le repère du mannequin.

Usage (module Python de Blender, « pip install bpy ») :
    python tools/bake/simulate.py -- <export.json>... <dossier de sortie>
Écrit <dossier>/<taille>-<pose>.bin (positions du tissu, Int16 au 1/16000 m, repère
du mannequin avant mise à l'échelle de la hauteur) et <taille>-<pose>.json
(orientation des os du mannequin dans la pose, présence du socle).
"""
import json
import pathlib
import sys
import time

import bpy  # noqa: I001
import numpy as np

STEP_SIT, STEP = 9, 6    # images entre deux instantanés du mouvement (s'asseoir : plus lent)
SETTLE = 45             # images pour que le tissu se pose à la fin
STEP_CUR = STEP
Q = 16000.0             # quantification (unités par mètre)


def to_blender(a):
    a = np.asarray(a, dtype=np.float64).reshape(-1, 3)
    return np.stack([a[:, 0], -a[:, 2], a[:, 1]], axis=1)


def from_blender(a):
    return np.stack([a[:, 0], a[:, 2], -a[:, 1]], axis=1)


def mesh_object(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], np.asarray(faces).reshape(-1, 3).tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def animate_sequence(ob, frames):
    """Instantanés successifs en clés de forme, enchaînés image après image."""
    ob.shape_key_add(name='Basis')
    keys = []
    for i, co in enumerate(frames[1:], start=1):
        k = ob.shape_key_add(name=f'f{i}', from_mix=False)
        k.data.foreach_set('co', co.ravel())
        keys.append((i, k))
    for i, k in keys:
        f = 1 + i * STEP_CUR
        last = i == len(frames) - 1
        for ff, v in ((f - STEP_CUR, 0.0), (f, 1.0), (f + STEP_CUR, 1.0 if last else 0.0)):
            k.value = v
            k.keyframe_insert('value', frame=ff)


def simulate(src, out_dir):
    d = json.loads(pathlib.Path(src).read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    fr = d['target']['frames']
    global STEP_CUR
    STEP_CUR = STEP_SIT if d.get('stool') else STEP
    FRAMES = 1 + (len(fr) - 1) * STEP_CUR + SETTLE
    scene.frame_start, scene.frame_end = 1, FRAMES

    # Mannequin : collisionneur animé du repos à la pose.
    body = mesh_object('mannequin', to_blender(fr[0]['body']), d['bodyIndex'])
    animate_sequence(body, [to_blender(f['body']) for f in fr])
    body.modifiers.new('collision', 'COLLISION')
    body.collision.thickness_outer = 0.008
    body.collision.thickness_inner = 0.05
    body.collision.cloth_friction = 6

    # Sol.
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, d['floorY']))
    floor = bpy.context.active_object
    floor.modifiers.new('collision', 'COLLISION')
    floor.collision.cloth_friction = 5

    # Socle de la pose assise.
    st = d.get('stool')
    if st:
        h = st['top'] - d['floorY']
        bpy.ops.mesh.primitive_cube_add(size=1, location=(st['x'], -st['z'], d['floorY'] + h / 2))
        cube = bpy.context.active_object
        cube.scale = (st['half'] * 2, st['half'] * 2, h)
        cube.modifiers.new('collision', 'COLLISION')
        cube.collision.cloth_friction = 20  # le tissu sur lequel on est assis ne glisse pas

    # Robe : épinglée au bustier, libre ailleurs.
    dress = mesh_object('robe', to_blender(fr[0]['dress']), d['tris'])
    animate_sequence(dress, [to_blender(f['dress']) for f in fr])  # cible du bustier épinglé
    vg = dress.vertex_groups.new(name='pin')
    pin = np.asarray(d['pin'])
    for w in np.unique(pin[pin > 0]):
        vg.add([int(i) for i in np.where(pin == w)[0]], float(w), 'REPLACE')
    cloth = dress.modifiers.new('tissu', 'CLOTH')
    cs = cloth.settings
    cs.quality = 12
    cs.mass = 0.25
    cs.air_damping = 1.5
    cs.tension_stiffness = cs.compression_stiffness = 60  # le tissu ne s'étire presque pas
    cs.shear_stiffness = 15
    cs.bending_stiffness = 1.2      # pagne en coton ciré : assez ferme
    cs.tension_damping = cs.compression_damping = 5
    cs.vertex_group_mass = 'pin'
    cs.pin_stiffness = 1
    cc = cloth.collision_settings
    cc.collision_quality = 6
    cc.distance_min = 0.005
    cc.use_self_collision = True
    cc.self_distance_min = 0.004
    cc.self_friction = 5
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, FRAMES

    t0 = time.time()
    for f in range(1, FRAMES + 1):
        scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = dress.evaluated_get(dg).to_mesh()
    co = np.empty(len(ev.vertices) * 3)
    ev.vertices.foreach_get('co', co)
    pos = from_blender(co.reshape(-1, 3))

    # Repère du mannequin : racine au sol, hauteur de base.
    tgt = d['target']
    pos[:, 1] -= tgt['rootY']
    pos /= tgt['scale']
    q = np.clip(np.round(pos * Q), -32767, 32767).astype('<i2')
    size, pose = d['size']['id'], d['pose']
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{size}-{pose}.bin').write_bytes(q.tobytes())
    meta = {'particles': int(len(q)), 'quant': Q, 'quats': tgt['quats'], 'stool': bool(st)}
    (out / f'{size}-{pose}.json').write_text(json.dumps(meta))
    print(f'{size}-{pose} : {time.time() - t0:.1f} s', flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    *sources, out_dir = argv
    for src in sources:
        simulate(src, out_dir)
