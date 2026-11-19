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
HOLD = 20               # images au repos avant le mouvement (les jambes reprennent leur volume, le tissu se pose)
STEP_CUR = STEP
Q = 16000.0             # quantification (unités par mètre)
CYCLES = 5              # défilé : cycles de marche simulés (on garde le dernier)
CLIP_STEP = 2           # défilé : une image sur deux enregistrée (interpolée dans le site)


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


def animate_sequence(ob, frames, times):
    """Formes successives en clés de forme : frames[0] = forme de base, frames[i] à l'image times[i]."""
    ob.shape_key_add(name='Basis')
    for i in range(1, len(frames)):
        k = ob.shape_key_add(name=f'f{i}', from_mix=False)
        k.data.foreach_set('co', frames[i].ravel())
        prev_t, t = times[i - 1], times[i]
        next_t = times[i + 1] if i + 1 < len(times) else None
        for ff, v in ((prev_t, 0.0), (t, 1.0)):
            k.value = v
            k.keyframe_insert('value', frame=ff)
        if next_t is not None:
            k.value = 0.0
            k.keyframe_insert('value', frame=next_t)


def animate_timeline(ob, shapes, timeline):
    """Clés de forme jouées selon `timeline` : liste (image, indice de forme).

    shapes[0] = forme de base ; une forme peut revenir plusieurs fois (cycle de
    marche répété). Entre deux entrées, mélange linéaire des deux formes.
    """
    ob.shape_key_add(name='Basis')
    keys = [None] + [ob.shape_key_add(name=f'f{i}', from_mix=False) for i in range(1, len(shapes))]
    for i in range(1, len(shapes)):
        keys[i].data.foreach_set('co', shapes[i].ravel())
    for p, (t, i) in enumerate(timeline):
        if i == 0:
            continue
        k = keys[i]
        k.value = 1.0
        k.keyframe_insert('value', frame=t)
        for q in (p - 1, p + 1):
            if 0 <= q < len(timeline) and timeline[q][1] != i:
                k.value = 0.0
                k.keyframe_insert('value', frame=timeline[q][0])


def animate_forward(obs, t0, t1, dist):
    """Avance des objets (le long de -y Blender = vers l'avant du mannequin), à vitesse constante."""
    for ob in obs:
        for t in range(t0, t1 + 1):
            ob.location.y = -dist * (t - t0) / max(1, t1 - t0)
            ob.keyframe_insert('location', index=1, frame=t)


def simulate(src, out_dir):
    d = json.loads(pathlib.Path(src).read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    fr = d['target']['frames']
    clip = d.get('clip')
    global STEP_CUR
    STEP_CUR = STEP_SIT if d.get('stool') else STEP
    if clip:
        # repos, transition vers la marche, puis CYCLES cycles de marche (le
        # corps avance réellement : le tissu traîne et se balance)
        start, L = clip['start'], clip['len']
        tl = [(1 + HOLD + k * clip['step'], k) for k in range(start)]
        t_cs = tl[-1][0] + clip['step']
        tl += [(t_cs + n, start + n % L) for n in range(CYCLES * L)]
        FRAMES = tl[-1][0]
        last0 = t_cs + (CYCLES - 1) * L  # dernier cycle : celui qu'on garde
        prev0 = last0 - L                # cycle précédent : pour boucler sans saut
    else:
        FRAMES = 1 + HOLD + (len(fr) - 1) * STEP_CUR + SETTLE
    scene.frame_start, scene.frame_end = 1, FRAMES

    # Mannequin : collisionneur animé du repos à la pose.
    times = [1 + HOLD + i * STEP_CUR for i in range(len(fr))]
    # le corps part avec des jambes amincies, qui reprennent leur volume pendant le repos
    body = mesh_object('mannequin', to_blender(d['target']['thin']), d['bodyIndex'])
    if clip:
        animate_timeline(body, [to_blender(d['target']['thin'])] + [to_blender(f['body']) for f in fr],
                         [(1, 0)] + [(t, i + 1) for t, i in tl])
    else:
        animate_sequence(body, [to_blender(d['target']['thin'])] + [to_blender(f['body']) for f in fr], [1] + times)
    body.modifiers.new('collision', 'COLLISION')
    body.collision.thickness_outer = 0.002  # zone de contact plus fine que l'aisance de la robe (8 mm)
    body.collision.thickness_inner = 0.02
    body.collision.cloth_friction = 6 if not clip else 1.5  # en marche, le tissu glisse sur les jambes (sinon il remonte)

    # Sol.
    bpy.ops.mesh.primitive_plane_add(size=8 if not clip else 40, location=(0, 0 if not clip else -15, d['floorY']))
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
    if clip:
        animate_timeline(dress, [to_blender(f['dress']) for f in fr], tl)
        animate_forward([body, dress], t_cs, FRAMES, clip['speed'] * (FRAMES - t_cs) / clip['fps'])
    else:
        animate_sequence(dress, [to_blender(f['dress']) for f in fr], times)  # cible du bustier épinglé
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
    cc.distance_min = 0.004
    cc.use_self_collision = True
    cc.self_distance_min = 0.004
    cc.self_friction = 5
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, FRAMES

    t0 = time.time()

    def grab():
        dg = bpy.context.evaluated_depsgraph_get()
        ev = dress.evaluated_get(dg).to_mesh()
        co = np.empty(len(ev.vertices) * 3)
        ev.vertices.foreach_get('co', co)
        return from_blender(co.reshape(-1, 3))  # repère de l'objet : sans l'avancée
    caps = {}
    for f in range(1, FRAMES + 1):
        scene.frame_set(f)
        if clip and f >= prev0:
            caps[f] = grab()
    if clip:
        # dernier cycle, fondu vers le cycle précédent sur les dernières images :
        # la dernière image enchaîne exactement sur la première (boucle sans saut)
        W = 10
        seq = []
        for j in range(0, L, CLIP_STEP):
            w = min(1.0, max(0.0, (j - (L - 1 - W)) / W))
            w = w * w * (3 - 2 * w)
            seq.append(caps[last0 + j] * (1 - w) + caps[prev0 + j] * w)
        pos = np.concatenate(seq)
    else:
        pos = grab()

    # Repère du mannequin : racine au sol, hauteur de base.
    tgt = d['target']
    pos[:, 1] -= tgt['rootY']
    pos /= tgt['scale']
    q = np.clip(np.round(pos * Q), -32767, 32767).astype('<i2')
    size, pose = d['size']['id'], d['pose']
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{size}-{pose}.bin').write_bytes(q.tobytes())
    meta = {'particles': int(len(q) // (len(seq) if clip else 1)), 'quant': Q, 'quats': tgt['quats'], 'stool': bool(st)}
    if clip:
        meta.update(frames=len(seq), fps=clip['fps'] / CLIP_STEP)
    (out / f'{size}-{pose}.json').write_text(json.dumps(meta))
    print(f'{size}-{pose} : {time.time() - t0:.1f} s', flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    *sources, out_dir = argv
    for src in sources:
        simulate(src, out_dir)
