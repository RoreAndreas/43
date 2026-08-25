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

RACINE = Path(__file__).parents[1]
SITE = RACINE / "site"          # dossier publié par Cloudflare Pages
DONNEES = RACINE / "donnees"    # jeu de données lisible, hors du dossier publié

# Seuils de vraisemblance du jeu de données extrait (référence : 157 pays,
# 94 industries). En dessous, la source a probablement changé de format.
MIN_COUNTRIES = 100
MIN_INDUSTRIES = 60


# En deçà de ce nombre de sociétés, une médiane de zone ne décrit plus un
# secteur : sur les 126 couples zone x secteur, 40 % n'en comptent aucune et un
# tiers une seule. La page reprend alors la médiane du continent, et l'écrit.
SEUIL_ECHANTILLON = 3


def main():
    parser = argparse.ArgumentParser(description="Génère la page statique du CMPC")
    parser.add_argument("--out", default=str(SITE), help="dossier de sortie (défaut : site/)")
    parser.add_argument("--years", type=int, default=10, help="profondeur d'historique des taux")
    parser.add_argument("--keep-data", action="store_true", help="écrit aussi donnees/data.json")
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

    # Garde-fou : si Damodaran change de format ou renvoie une page d'erreur,
    # l'extraction se vide silencieusement. Mieux vaut échouer que publier
    # automatiquement une page sans données.
    if len(dataset["pays"]) < MIN_COUNTRIES:
        raise SystemExit(f"Seulement {len(dataset['pays'])} pays extraits (minimum {MIN_COUNTRIES}) — page non écrite.")
    if len(dataset["industries"]) < MIN_INDUSTRIES:
        raise SystemExit(f"Seulement {len(dataset['industries'])} industries extraites (minimum {MIN_INDUSTRIES}) — page non écrite.")
    if not dataset["rf"]:
        raise SystemExit("Aucun taux US Treasury récupéré — page non écrite.")

    # Le découpage géographique se rapproche sur le libellé exact. Damodaran
    # republie chaque janvier, et une retouche d'orthographe sortirait un pays du
    # découpage sans erreur visible. On ne bloque pas la publication pour autant :
    # le pays reste sélectionnable, il apparaît seulement sous « Autres ».
    inclassables = dataset.get("inclassables") or []
    if inclassables:
        print(f"  /!\\ {len(inclassables)} pays sans zone, à rattacher dans zones.py :")
        for nom in inclassables:
            print(f"       - {nom}")

    import comparables as _comparables
    import zones as _zones

    # Univers de comparables : l'export S&P déposé dans le dossier du projet.
    # Il donne la nomenclature d'industries, le gearing sectoriel observé, et
    # une couverture continentale que la seule place d'Abidjan ne permettait pas.
    # L'export est déposé à la racine de WACC43, un niveau au-dessus de PFILES.
    univers = _comparables.construire(RACINE.parent, progress=progress)
    if univers is None:
        # Échec franc plutôt qu'avertissement : la nomenclature d'industries, le
        # gearing sectoriel et les effectifs de la carte en dépendent tous. Sans
        # cet univers, la page se construit sans erreur mais publie une version
        # dégradée — ce qui est arrivé, et n'a été vu qu'en inspectant le site.
        raise SystemExit(
            "Aucun export SPGlobal_Export_*.xlsx trouvé autour de "
            f"{RACINE.parent} — page non écrite."
        )
    else:
        index, orphelins = _comparables.indexer_par_zone(univers, _zones.classer)
        societes = _comparables.payload_page(univers, _zones.classer)
        secteurs = _comparables.secteurs_par_perimetre(univers["societes"], _zones.classer)
        dataset["comparables"] = {
            "source": univers["source"],
            "seuil": SEUIL_ECHANTILLON,
            # La page refait cette sélection sur les mêmes données pour marquer
            # les sociétés retenues : embarquer les identifiants coûterait trois
            # cent cinquante kilooctets pour une règle qui tient en une ligne.
            "echantillon": _comparables.ECHANTILLON_MAX,
            # Le menu se peuple de tous les secteurs de l'univers, peuplés ou non
            # dans la zone retenue : masquer ceux qui manquent ici priverait
            # l'utilisateur de la vue continentale, qui reste calculable.
            "industries": [{"nom": nom, "societes": stats["univers"]["societes"]}
                           for nom, stats in sorted(secteurs.items())],
            # Médianes aux trois échelles : la page prend la plus étroite qui
            # atteigne le seuil et écrit laquelle a servi.
            "secteurs": secteurs,
            "zones": index,
            # Les sociétés elles-mêmes, et pas seulement leur décompte : c'est
            # cette population que l'onglet Sociétés doit lister, la même que
            # celle que chiffre le cadrage.
            "societes": societes,
        }

        # Garde-fou : les effectifs de la carte et la liste des sociétés sortent
        # de deux parcours différents du même univers. S'ils divergent, la page
        # annoncera des sociétés qu'elle ne sait pas montrer — le défaut qu'on
        # vient de corriger. Autant que la construction s'arrête ici.
        attendu = sum(bloc["total"] for bloc in index.values())
        sans_zone = sum(1 for s in societes.values() if s["zone"] is None)
        if len(societes) != attendu + sans_zone:
            raise SystemExit(
                f"Incohérence : {len(societes)} sociétés embarquées, mais "
                f"{attendu} comptées en zone et {sans_zone} sans zone — page non écrite."
            )
        dataset["zones_societes"] = index
        if orphelins:
            print(f"  /!\\ pays de comparables sans zone : {', '.join(orphelins)}")

    page = render_page(dataset)
    target = out / "index.html"
    target.write_text(page, encoding="utf-8")

    if args.keep_data:
        DONNEES.mkdir(parents=True, exist_ok=True)
        (DONNEES / "data.json").write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    payload = len(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print()
    print(f"  pays        : {len(dataset['pays'])}")
    for continent, membres in dataset["options"]["countries_grouped"]:
        print(f"     {continent:<12}: {len(membres)}")
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
