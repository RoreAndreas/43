#!/usr/bin/env bash
# Pré-calcul complet des tombés d'une robe : export puis simulation Blender en parallèle.
# Usage : tools/bake/run.sh <robe> [tailles séparées par des virgules] [poses] [processus parallèles]
# Prérequis : Node + Playwright, et un Python avec le module « bpy » (variable BPY_PYTHON).
set -euo pipefail
cd "$(dirname "$0")/../.."
DRESS=${1:-aveline}
SIZES=${2:-36,38,40,42,44,46}
POSES=${3:-neutre,hanchement,mains-hanches,bras-ouverts,defile,photo,assise}
JOBS=${4:-3}
PY=${BPY_PYTHON:-python3}
WORK=${BAKE_WORK:-$(mktemp -d)}
OUT=assets/garments/bakes/$DRESS
node tools/bake/export.mjs "$DRESS" "$WORK" "$SIZES" "$POSES"
# Une simulation par fichier ; chaque taille garde son propre fichier d'index.
ls "$WORK"/"$DRESS"-*.json | xargs -P "$JOBS" -I{} "$PY" tools/bake/simulate.py -- {} "$OUT"

# Index des tombés disponibles (lu par le site au démarrage)
python3 - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
names = sorted(p.stem for p in out.glob('*.bin'))
(out / 'index.json').write_text(json.dumps(names))
print(len(names), 'tombés dans', out / 'index.json')
PY
