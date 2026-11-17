#!/usr/bin/env python3
"""Convertit un vêtement Blender (.blend) en fichier léger pour la salle d'essayage.

Nécessite le module Python de Blender :  pip install bpy  (dans un venv)
Usage :
    python tools/convert_garment.py <fichier.blend> <nom> [objet]

Écrit assets/garments/<nom>.bin et <nom>.json :
- sommets uniques (les « particules » du tissu, en mètres, Y vers le haut) ;
- sommets de rendu (dupliqués le long des coutures du patron) avec leurs UV
  convertis en mètres, pour plaquer le pagne à l'échelle réelle ;
- triangles.
L'ajustement au mannequin et le rig se font dans le navigateur
(js/essayage/dress.js), pour suivre les mesures de la cliente.
"""
import json
import pathlib
import sys

import bpy  # noqa: I001  (bpy doit être importé avant bmesh)
import bmesh
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    src, name = sys.argv[1], sys.argv[2]
    obj_name = sys.argv[3] if len(sys.argv) > 3 else None
    bpy.ops.wm.open_mainfile(filepath=src)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    o = next(m for m in meshes if m.name == obj_name) if obj_name else max(meshes, key=lambda m: len(m.data.vertices))
    dg = bpy.context.evaluated_depsgraph_get()
    m = o.evaluated_get(dg).to_mesh()
    bm = bmesh.new()
    bm.from_mesh(m)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.active
    mw = o.matrix_world

    uniq = np.array([(mw @ v.co)[:] for v in bm.verts], dtype=np.float64)
    uniq = np.stack([uniq[:, 0], uniq[:, 2], -uniq[:, 1]], axis=1)  # Z-up -> Y-up, face avant vers +Z
    rv, ruv, key, tris = [], [], {}, []
    for f in bm.faces:
        tri = []
        for loop in f.loops:
            uv = (round(loop[uvl].uv[0], 6), round(loop[uvl].uv[1], 6)) if uvl else (0.0, 0.0)
            k = (loop.vert.index, uv)
            if k not in key:
                key[k] = len(rv)
                rv.append(loop.vert.index)
                ruv.append(uv)
            tri.append(key[k])
        tris.append(tri)
    rv = np.array(rv, dtype=np.uint32)
    ruv = np.array(ruv, dtype=np.float64)
    tris = np.array(tris, dtype=np.uint32)

    # Échelle des UV : médiane du rapport longueur 3D / longueur UV sur les arêtes.
    ratios = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        p = np.linalg.norm(uniq[rv[tris[:, a]]] - uniq[rv[tris[:, b]]], axis=1)
        u = np.linalg.norm(ruv[tris[:, a]] - ruv[tris[:, b]], axis=1)
        ok = u > 1e-9
        ratios.append(p[ok] / u[ok])
    uv_m = (ruv - ruv.min(axis=0)) * float(np.median(np.concatenate(ratios)))

    out = ROOT / 'assets' / 'garments'
    out.mkdir(parents=True, exist_ok=True)
    blob = (uniq.astype(np.float32).tobytes() + rv.astype(np.uint32).tobytes()
            + uv_m.astype(np.float32).tobytes() + tris.astype(np.uint32).tobytes())
    (out / f'{name}.bin').write_bytes(blob)
    meta = {
        'name': o.name, 'source': pathlib.Path(src).name,
        'particles': int(len(uniq)), 'renderVertices': int(len(rv)), 'triangles': int(len(tris)),
        'min': uniq.min(axis=0).round(4).tolist(), 'max': uniq.max(axis=0).round(4).tolist(),
    }
    (out / f'{name}.json').write_text(json.dumps(meta, indent=1))
    print(f"{name}: {meta['particles']} particules, {meta['triangles']} triangles, {len(blob) // 1024} Ko")


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    sys.argv = [sys.argv[0], *argv]
    main()
