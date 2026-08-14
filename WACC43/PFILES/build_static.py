"""
Construction de la page statique.

    python build_static.py

Télécharge les bases Damodaran et les taux US Treasury, les condense, puis
écrit `site/index.html` : un fichier autonome qui recalcule le CMPC dans le
navigateur, sans serveur. À relancer quand Damodaran publie sa mise à jour
annuelle (janvier), ou trimestriellement pour figer un taux Treasury plus frais
sur l'exercice en cours.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

import wacc_core
from wacc_html import render_page

SITE = Path(__file__).parent / "site"


def main():
    parser = argparse.ArgumentParser(description="Génère la page statique du CMPC")
    parser.add_argument("--out", default=str(SITE), help="dossier de sortie (défaut : site/)")
    parser.add_argument("--years", type=int, default=10, help="profondeur d'historique des taux")
    parser.add_argument("--keep-data", action="store_true", help="écrit aussi data.json à côté")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    current = datetime.now().year
    years = list(range(current, current - args.years, -1))

    started = time.time()
    step = {"n": 0}

    def progress(message):
        step["n"] += 1
        print(f"  [{step['n']:>2}] {message}")

    print("Téléchargement des sources...")
    dataset = wacc_core.build_dataset(years=years, progress=progress)

    page = render_page(dataset)
    target = out / "index.html"
    target.write_text(page, encoding="utf-8")

    if args.keep_data:
        (out / "data.json").write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    payload = len(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print()
    print(f"  pays        : {len(dataset['pays'])}")
    print(f"  industries  : {len(dataset['industries'])}")
    print(f"  taux        : {len(dataset['rf'])} couples (année, maturité)")
    print(f"  données     : {payload / 1024:.1f} Ko")
    print(f"  page        : {target} — {target.stat().st_size / 1024:.1f} Ko")
    print(f"  durée       : {time.time() - started:.0f} s")
    print()
    print("Ouvre le fichier dans un navigateur, ou dépose le dossier sur un")
    print("hébergement statique (Cloudflare Pages, GitHub Pages, Netlify).")


if __name__ == "__main__":
    main()
